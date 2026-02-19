import time
from flask import Blueprint, request, jsonify, current_app
from app import whatsapp_service, db_handler

message_bp = Blueprint('messages', __name__)

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
    """Envío masivo a pendientes."""
    try:
        data = request.get_json() or {}
        template_name = data.get('template_name', 'prueba_matricula')
        language_code = data.get('language_code', 'es')
        
        current_app.logger.info(f"[BATCH] Iniciando envío masivo con template: {template_name}")
        
        # Obtener estudiantes con opt_in activo
        opt_in_students = db_handler.get_estudiantes_opt_in()
        
        current_app.logger.info(f"[BATCH] Estudiantes opt_in encontrados: {len(opt_in_students)}")
        
        if not opt_in_students:
            stats = db_handler.get_estadisticas()
            current_app.logger.info(f"[BATCH] No hay estudiantes opt_in. Stats: {stats}")
            return jsonify({'success': True, 'message': 'No hay estudiantes con opt_in', 'stats': stats}), 200
        
        # Crear campaña implícita de tipo MATRICULA
        from datetime import datetime
        campana_nombre = f"Matrícula Batch {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        success_c, campana_id = db_handler.insert_campana(
            nombre=campana_nombre,
            tipo='MATRICULA',
            plantilla_whatsapp=template_name
        )
        
        if not success_c:
            return jsonify({'success': False, 'error': f'Error creando campaña: {campana_id}'}), 500
        
        # Agregar miembros
        estudiante_ids = [int(s['id']) for s in opt_in_students if s.get('id')]
        db_handler.insert_campana_miembros(campana_id, estudiante_ids)
        
        # Enviar a todos los miembros pendientes
        pendientes = db_handler.get_miembros_pendientes_envio(campana_id)
        
        current_app.logger.info(f"[SEND] Batch iniciado - {len(pendientes)} pendientes")
        
        results = []
        delay = current_app.config.get('DELAY_SECONDS', 1.5)
        
        for i, miembro in enumerate(pendientes):
            phone = miembro.get('telefono_e164')
            if not phone: continue
            
            # Construir parámetros con datos JOINed del nuevo esquema
            params = [
                str(miembro.get('nombre', '')),
                str(miembro.get('modalidad', '')),
                str(miembro.get('bootcamp_nombre', '')),
                str(miembro.get('fecha_inicio_ingles', '')),
                '',  # ingles_fin deprecated
                str(miembro.get('fecha_inicio_tecnica', '')),
                str(miembro.get('horario', '')),
                str(miembro.get('lugar', ''))
            ]
            
            current_app.logger.info(f"[BATCH] Enviando a {phone} con params: {params[:2]}...")
            
            success, result = whatsapp_service.send_template_message(
                phone, template_name, params, language_code
            )
            
            current_app.logger.info(f"[BATCH] Resultado {phone}: success={success}, result={result}")
            
            # Actualizar estado en campana_miembros
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
            'stats': {'processed': len(results), 'sent': enviados, 'errors': errores}
        }), 200

    except Exception as e:
        current_app.logger.error(f"[BATCH] Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500