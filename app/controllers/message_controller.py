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
    Envío masivo SEGURO.  Soporta 2 modos:

    ── Modo A: Campaña existente ──
        campana_id (int): ID de la campaña (ya debe tener miembros).

    ── Modo B: Crear campaña nueva + enviar ──
        campana_nombre (str): Nombre de la nueva campaña.
        tipo (str): MATRICULA | EVENTO | INFO
        estudiante_ids (list[int], REQUIRED): IDs de estudiantes a enviar.
            Viene del upload (/api/google/upload → response.estudiante_ids).

    Campos comunes (opcionales):
        plantilla_whatsapp (str): Override del template de Meta.
        language_code (str): Override del idioma.
        skip_already_sent (bool): Si true, filtra estudiantes que ya
            recibieron una campaña del mismo tipo (default: false).

    ⚠️  SEGURIDAD: En modo B, los miembros se toman EXCLUSIVAMENTE de
    estudiante_ids. NUNCA se agregan todos los estudiantes de la BD.
    """
    try:
        data = request.get_json() or {}
        campana_id = data.get('campana_id')
        campana_nombre = data.get('campana_nombre')
        plantilla_override = data.get('plantilla_whatsapp')
        estudiante_ids = data.get('estudiante_ids')  # lista de IDs del upload
        skip_already_sent = data.get('skip_already_sent', False)

        # ─── MODO B: Crear campaña nueva ───
        if not campana_id and campana_nombre:
            tipo_param = (data.get('tipo') or 'MATRICULA').upper()

            if not estudiante_ids or not isinstance(estudiante_ids, list) or len(estudiante_ids) == 0:
                return jsonify({
                    'success': False,
                    'error': 'estudiante_ids es requerido al crear campaña nueva. '
                             'Sube estudiantes primero (upload) y pasa los IDs devueltos.'
                }), 400

            # ─── FILTRO skip_already_sent ───
            # Si está activo, eliminar de estudiante_ids los que ya recibieron
            # una campaña del mismo tipo con estado_envio='sent'.
            ids_filtrados = [int(x) for x in estudiante_ids]
            skipped_ids = []

            if skip_already_sent and tipo_param != 'INFO':
                # Obtener set de IDs que NO tienen campaña enviada de este tipo
                elegibles = db_handler.get_estudiantes_sin_campana_enviada(tipo_param)
                elegibles_ids = {int(e['id']) for e in elegibles}

                ids_originales = ids_filtrados[:]
                ids_filtrados = [eid for eid in ids_filtrados if eid in elegibles_ids]
                skipped_ids = [eid for eid in ids_originales if eid not in elegibles_ids]

                current_app.logger.info(
                    f"[BATCH] skip_already_sent: {len(ids_originales)} originales → "
                    f"{len(ids_filtrados)} elegibles, {len(skipped_ids)} omitidos"
                )

                if not ids_filtrados:
                    return jsonify({
                        'success': True,
                        'message': f'Todos los {len(skipped_ids)} estudiantes ya fueron '
                                   f'enviados en otra campaña de tipo {tipo_param}. '
                                   'No se creó la campaña.',
                        'stats': {
                            'processed': 0, 'sent': 0, 'errors': 0,
                            'skipped': len(skipped_ids)
                        }
                    }), 200

            # Crear la campaña
            ok, result = db_handler.insert_campana(
                nombre=campana_nombre,
                tipo=tipo_param,
                plantilla_whatsapp=plantilla_override or ''
            )
            if not ok:
                return jsonify({'success': False, 'error': f'Error creando campaña: {result}'}), 400

            campana_id = int(result)
            current_app.logger.info(
                f"[BATCH] Campaña nueva creada: #{campana_id} '{campana_nombre}' "
                f"tipo={tipo_param}, estudiantes={len(ids_filtrados)}"
                f"{f', omitidos={len(skipped_ids)}' if skipped_ids else ''}"
            )

            # Agregar SOLO los estudiantes filtrados como miembros
            ok, msg = db_handler.insert_campana_miembros(campana_id, ids_filtrados)
            if not ok:
                return jsonify({'success': False, 'error': f'Error agregando miembros: {msg}'}), 400

        # ─── MODO A: Campaña existente ───
        elif not campana_id:
            return jsonify({
                'success': False,
                'error': 'campana_id o (campana_nombre + estudiante_ids) es requerido.'
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