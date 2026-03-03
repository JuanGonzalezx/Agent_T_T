import time
from flask import Blueprint, request, jsonify, current_app
from app import whatsapp_service, db_handler
from app.controllers.campaign_controller import _build_template_params

message_bp = Blueprint('messages', __name__)

# ─── Plantillas por defecto según tipo de campaña ───
TEMPLATE_DEFAULTS = {
    'MATRICULA': {'plantilla': 'prueba_matricula', 'language': 'es'},
    'EVENTO': {'plantilla': 'confirmacion_evento_quindio', 'language': 'es_CO'},
    'INFO': {'plantilla': 'confirmacion_evento_quindio', 'language': 'es_CO'},
}

@message_bp.route('/send-simple', methods=['POST'])
def send_simple_message():
    """Envía un mensaje simple o de plantilla."""
    try:
        data = request.get_json() or {}
        phone = data.get('phone')
        
        if not phone:
            return jsonify({'success': False, 'error': 'Campo phone requerido'}), 400
        
        template_name = data.get('template_name')
        
        if template_name:
            # Envío de plantilla
            success, result = whatsapp_service.send_template_message(
                phone, 
                template_name, 
                data.get('parameters', []), 
                data.get('language_code', 'es')
            )
            resp_type = 'template'
        else:
            # Envío de texto
            msg_text = data.get('message')
            if not msg_text:
                return jsonify({'success': False, 'error': 'Message o template_name requerido'}), 400
            success, result = whatsapp_service.send_text_message(phone, msg_text)
            resp_type = 'text'

        if success:
            return jsonify({'success': True, 'message_id': result, 'type': resp_type}), 200
        return jsonify({'success': False, 'error': result}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@message_bp.route('/send-template', methods=['POST'])
def send_template_route():
    """Wrapper específico para plantillas (legacy support)."""
    return send_simple_message()

@message_bp.route('/send-batch', methods=['POST'])
def send_batch_messages():
    """
    Envío masivo SEGURO.  Solo envía a miembros YA asignados a una campaña.

    ⚠️  REGLA DE SEGURIDAD: Este endpoint NUNCA agrega miembros automáticamente.
    Los miembros deben ser agregados previamente vía:
      - POST /api/campaigns/{id}/members  (panel de campaña)
      - El frontend al crear campaña desde el Dashboard

    Body JSON:
        campana_id (int, REQUIRED): ID de la campaña a enviar.
            La campaña debe existir y tener miembros asignados.
        plantilla_whatsapp (str, optional): Override del template de Meta.
        skip_already_sent (bool, optional): Si true, solo envía a pendientes
            (default: true — es decir, nunca reenvía a quien ya recibió).

    Flujo:
        1. Valida que la campaña exista y tenga miembros
        2. Resuelve plantilla/language desde la campaña o override
        3. Obtiene SOLO los miembros pendientes de ESTA campaña
        4. Envía y actualiza estado de cada miembro
    """
    try:
        data = request.get_json() or {}
        campana_id = data.get('campana_id')
        plantilla_override = data.get('plantilla_whatsapp')

        # ─── 1. VALIDAR: campana_id es OBLIGATORIO ───
        if not campana_id:
            return jsonify({
                'success': False,
                'error': 'campana_id es requerido. Crea una campaña y agrega miembros antes de enviar.'
            }), 400

        campana = db_handler.get_campana_by_id(int(campana_id))
        if not campana:
            return jsonify({'success': False, 'error': f'Campaña {campana_id} no encontrada'}), 404

        campana_id = int(campana['id'])
        tipo = campana.get('tipo', 'MATRICULA').upper()

        # ─── 2. VALIDAR: La campaña debe tener miembros ───
        total_miembros = db_handler.count_miembros_campana(campana_id)
        if total_miembros == 0:
            return jsonify({
                'success': False,
                'error': f'La campaña #{campana_id} no tiene miembros asignados. '
                         'Agrega miembros antes de enviar (POST /api/campaigns/{id}/members).'
            }), 400

        current_app.logger.info(
            f"[BATCH] Campaña #{campana_id} ({campana.get('nombre')}) "
            f"tipo={tipo}, miembros={total_miembros}"
        )

        # ─── 3. Resolver plantilla y language_code ───
        defaults = TEMPLATE_DEFAULTS.get(tipo, {'plantilla': 'confirmacion_evento_quindio', 'language': 'es_CO'})
        template_name = plantilla_override or campana.get('plantilla_whatsapp') or defaults['plantilla']
        language_code = defaults['language']

        current_app.logger.info(f"[BATCH] template={template_name}, lang={language_code}")

        # ─── 4. Obtener SOLO miembros pendientes de ESTA campaña ───
        pendientes = db_handler.get_miembros_pendientes_envio(campana_id)
        current_app.logger.info(f"[BATCH] {len(pendientes)} miembros pendientes de campaña #{campana_id}")

        if not pendientes:
            return jsonify({
                'success': True,
                'message': 'No hay miembros pendientes de envío en esta campaña',
                'campana_id': campana_id,
                'stats': {'processed': 0, 'sent': 0, 'errors': 0}
            }), 200

        # ─── 5. Enviar mensajes ───
        db_handler.update_campana_estado(campana_id, 'SENDING')

        results = []
        delay = current_app.config.get('DELAY_SECONDS', 1.5)

        for i, miembro in enumerate(pendientes):
            phone = miembro.get('telefono_e164')
            if not phone:
                continue

            params = _build_template_params(miembro, tipo)

            current_app.logger.info(f"[BATCH] [{i+1}/{len(pendientes)}] → {phone}")

            success, result = whatsapp_service.send_template_message(
                phone, template_name, params, language_code
            )

            miembro_id = miembro.get('miembro_id')
            status = 'sent' if success else 'error'
            db_handler.update_miembro_estado_envio(
                int(miembro_id), status, result if success else None
            )

            results.append({'phone': phone, 'success': success, 'result': result})

            if i < len(pendientes) - 1:
                time.sleep(delay)

        db_handler.update_campana_estado(campana_id, 'COMPLETED')

        enviados = sum(1 for r in results if r['success'])
        errores = sum(1 for r in results if not r['success'])

        return jsonify({
            'success': True,
            'message': f'Envío masivo completado: {enviados} enviados, {errores} errores',
            'campana_id': campana_id,
            'template': template_name,
            'tipo': tipo,
            'stats': {'processed': len(results), 'sent': enviados, 'errors': errores}
        }), 200

    except Exception as e:
        current_app.logger.error(f"[BATCH] Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500