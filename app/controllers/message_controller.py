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
        
        pending_students = db_handler.get_estudiantes_pendientes_envio()
        
        current_app.logger.info(f"[BATCH] Estudiantes pendientes encontrados: {len(pending_students)}")
        
        if not pending_students:
            stats = db_handler.get_estadisticas()
            current_app.logger.info(f"[BATCH] No hay pendientes. Stats: {stats}")
            return jsonify({'success': True, 'message': 'No hay pendientes', 'stats': stats}), 200
        
        current_app.logger.info(f"[SEND] Batch iniciado - {len(pending_students)} pendientes")
        
        results = []
        delay = current_app.config['DELAY_SECONDS']
        
        for i, student in enumerate(pending_students):
            phone = student.get('telefono_e164')
            if not phone: continue
            
            # Construir parámetros (Asegurar que coinciden con tu plantilla)
            params = [
                str(student.get('nombre', '')),
                str(student.get('modalidad', '')),
                str(student.get('bootcamp_nombre', '')),
                str(student.get('ingles_inicio', '')),
                str(student.get('ingles_fin', '')),
                str(student.get('inicio_formacion', '')),
                str(student.get('horario', '')),
                str(student.get('lugar', ''))
            ]
            
            current_app.logger.info(f"[BATCH] Enviando a {phone} con params: {params[:2]}...")
            
            success, result = whatsapp_service.send_template_message(
                phone, template_name, params, language_code
            )
            
            current_app.logger.info(f"[BATCH] Resultado {phone}: success={success}, result={result}")
            
            # Actualizar BD
            status = 'sent' if success else 'error'
            db_handler.update_estado_envio(phone, status, result if success else None)
            
            results.append({'phone': phone, 'success': success, 'result': result})
            
            if i < len(pending_students) - 1:
                time.sleep(delay)
                
        return jsonify({
            'success': True, 
            'message': 'Envío masivo completado',
            'stats': {'processed': len(results)}
        }), 200

    except Exception as e:
        current_app.logger.error(f"[BATCH] Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500