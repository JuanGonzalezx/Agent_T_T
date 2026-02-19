import time
from flask import Blueprint, request, jsonify, current_app
from app import whatsapp_service, db_handler
from app.controllers.campaign_controller import _build_template_params

message_bp = Blueprint('messages', __name__)

# ─── Plantillas por defecto según tipo de campaña ───
TEMPLATE_DEFAULTS = {
    'MATRICULA': 'prueba_matricula',
    'EVENTO': 'confirmacion_evento_quindio',
    'INFO': 'confirmacion_evento_quindio',
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
    Envío masivo dinámico.  Soporta múltiples tipos de campaña.

    Body JSON:
        tipo (str, required): MATRICULA | EVENTO | INFO
        campana_id (int, optional): Usar campaña existente (se traen datos de ella)
        campana_nombre (str, optional): Nombre para nueva campaña
        plantilla_whatsapp (str, optional): Override del template de Meta
        language_code (str, optional): Código de idioma (default: es)
        skip_already_sent (bool, optional): Omitir estudiantes ya enviados en
            otra campaña del mismo tipo (default: true)

    Flujo:
        1. Determina plantilla según tipo o override
        2. Crea campaña o usa la existente
        3. Filtra estudiantes (excluye ya enviados si aplica)
        4. Agrega miembros + envía usando _build_template_params
    """
    try:
        data = request.get_json() or {}
        tipo = (data.get('tipo') or 'MATRICULA').upper()
        campana_id = data.get('campana_id')
        campana_nombre = data.get('campana_nombre')
        plantilla_override = data.get('plantilla_whatsapp')
        language_code = data.get('language_code', 'es')
        skip_already_sent = data.get('skip_already_sent', True)

        # ─── 1. Resolver plantilla ───
        template_name = plantilla_override or TEMPLATE_DEFAULTS.get(tipo, 'confirmacion_evento_quindio')

        current_app.logger.info(f"[BATCH] Tipo={tipo}, template={template_name}, campana_id={campana_id}")

        # ─── 2. Resolver / crear campaña ───
        if campana_id:
            # Usar campaña existente
            campana = db_handler.get_campana_by_id(int(campana_id))
            if not campana:
                return jsonify({'success': False, 'error': f'Campaña {campana_id} no encontrada'}), 404
            # Traer tipo y plantilla de la campaña existente si no se pasaron
            tipo = campana.get('tipo', tipo)
            if not plantilla_override and campana.get('plantilla_whatsapp'):
                template_name = campana['plantilla_whatsapp']
            campana_id = int(campana['id'])
            current_app.logger.info(f"[BATCH] Usando campaña existente #{campana_id}: {campana.get('nombre')}")
        else:
            # Crear campaña nueva
            from datetime import datetime
            if not campana_nombre:
                campana_nombre = f"{tipo} Batch {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            success_c, result = db_handler.insert_campana(
                nombre=campana_nombre,
                tipo=tipo,
                plantilla_whatsapp=template_name
            )
            if not success_c:
                return jsonify({'success': False, 'error': f'Error creando campaña: {result}'}), 500
            campana_id = result
            current_app.logger.info(f"[BATCH] Campaña creada #{campana_id}: {campana_nombre}")

        # ─── 3. Obtener estudiantes (filtrando duplicados si aplica) ───
        if skip_already_sent:
            opt_in_students = db_handler.get_estudiantes_sin_campana_enviada(tipo)
        else:
            opt_in_students = db_handler.get_estudiantes_opt_in()

        current_app.logger.info(f"[BATCH] Estudiantes elegibles: {len(opt_in_students)}")

        if not opt_in_students:
            stats = db_handler.get_estadisticas()
            return jsonify({
                'success': True,
                'message': 'No hay estudiantes pendientes de envío para este tipo de campaña',
                'campana_id': campana_id,
                'stats': stats
            }), 200

        # ─── 4. Agregar miembros a la campaña ───
        estudiante_ids = [int(s['id']) for s in opt_in_students if s.get('id')]
        db_handler.insert_campana_miembros(campana_id, estudiante_ids)

        # ─── 5. Enviar mensajes ───
        pendientes = db_handler.get_miembros_pendientes_envio(campana_id)
        current_app.logger.info(f"[BATCH] Enviando a {len(pendientes)} miembros pendientes")

        # Actualizar estado de campaña a SENDING
        db_handler.update_campana_estado(campana_id, 'SENDING')

        results = []
        delay = current_app.config.get('DELAY_SECONDS', 1.5)

        for i, miembro in enumerate(pendientes):
            phone = miembro.get('telefono_e164')
            if not phone:
                continue

            # Construir parámetros dinámicos según tipo de campaña
            params = _build_template_params(miembro, tipo)

            current_app.logger.info(f"[BATCH] [{i+1}/{len(pendientes)}] → {phone} params={params[:2]}...")

            success, result = whatsapp_service.send_template_message(
                phone, template_name, params, language_code
            )

            # Actualizar estado del miembro
            miembro_id = miembro.get('miembro_id')
            status = 'sent' if success else 'error'
            db_handler.update_miembro_estado_envio(
                int(miembro_id), status, result if success else None
            )

            results.append({'phone': phone, 'success': success, 'result': result})

            if i < len(pendientes) - 1:
                time.sleep(delay)

        # Marcar campaña como completada
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