"""
API REST para el sistema de envío de mensajes WhatsApp.

Este servidor Flask expone endpoints para gestionar el envío de mensajes
a través de WhatsApp Business API, proporcionando una interfaz HTTP limpia
y bien documentada para integraciones externas.
"""

import os
import time
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from typing import Dict, Any

from services.whatsapp_service import WhatsAppService
from utils.csv_handler import CSVHandler


# Inicialización de la aplicación Flask
# __name__ permite a Flask localizar recursos relativos al módulo actual
app = Flask(__name__)

# CORS habilitado para permitir peticiones desde frontends en otros dominios
# En producción, configurar origins específicos para mayor seguridad
CORS(app)

# Configuración de la aplicación
# Estas constantes centralizan valores que podrían cambiar según el ambiente
CSV_PATH = os.getenv("CSV_PATH", "bd_envio.csv")
DELAY_SECONDS = float(os.getenv("DELAY_SECONDS", "1.5"))

# Inicialización de servicios
# Los servicios se instancian una sola vez para optimizar recursos
whatsapp_service = WhatsAppService()
csv_handler = CSVHandler(CSV_PATH)


@app.route('/health', methods=['GET'])
def health_check():
    """
    Endpoint de health check para monitoreo.
    
    Este endpoint permite a sistemas de monitoreo verificar que el
    servidor está activo y respondiendo correctamente.
    
    Returns:
        JSON: Estado del servidor y configuración básica
    """
    # Validar que las credenciales estén configuradas
    valid, msg = whatsapp_service.validate_credentials()
    
    return jsonify({
        'status': 'healthy' if valid else 'warning',
        'service': 'WhatsApp Messaging API',
        'credentials': msg,
        'csv_path': CSV_PATH
    }), 200 if valid else 503


@app.route('/api/messages/send-simple', methods=['POST'])
def send_simple_message():
    """
    Envía un mensaje simple o de plantilla a un número de teléfono.
    
    Este endpoint permite enviar tanto mensajes de texto como plantillas
    pre-aprobadas, útil para pruebas o envíos individuales.
    
    Request Body para mensaje de texto:
        {
            "phone": "+573001234567",
            "message": "Texto del mensaje"
        }
    
    Request Body para plantilla:
        {
            "phone": "+573001234567",
            "template_name": "prueba_matricula",
            "parameters": ["Juan", "Inteligencia Artificial", "Presencial", "24 de enero", "25 de enero", "26 de enero", "Lunes a viernes 6pm-10pm", "Moodle"],
            "language_code": "es"  // Opcional, default: "es"
        }
    
    Returns:
        JSON: Resultado del envío con el ID del mensaje o error
    """
    try:
        data = request.get_json()
        
        # Validación de entrada
        if not data:
            return jsonify({
                'success': False,
                'error': 'No se recibió JSON en el body'
            }), 400
        
        phone = data.get('phone')
        
        if not phone:
            return jsonify({
                'success': False,
                'error': 'Campo requerido: phone'
            }), 400
        
        # Determinar si es un mensaje de plantilla o texto simple
        template_name = data.get('template_name')
        
        if template_name:
            # Envío de plantilla
            parameters = data.get('parameters', [])
            language_code = data.get('language_code', 'es')
            
            success, result = whatsapp_service.send_template_message(
                phone, 
                template_name, 
                parameters, 
                language_code
            )
            
            if success:
                return jsonify({
                    'success': True,
                    'message_id': result,
                    'phone': phone,
                    'type': 'template',
                    'template_name': template_name
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': result
                }), 500
        else:
            # Envío de mensaje de texto simple
            message = data.get('message')
            
            if not message:
                return jsonify({
                    'success': False,
                    'error': 'Campo requerido: message (o template_name para plantillas)'
                }), 400
            
            success, result = whatsapp_service.send_text_message(phone, message)
            
            if success:
                return jsonify({
                    'success': True,
                    'message_id': result,
                    'phone': phone,
                    'type': 'text'
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': result
                }), 500
    
    except Exception as e:
        # Logging centralizado de errores para debugging
        app.logger.error(f"Error en send_simple_message: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500


@app.route('/api/messages/send-batch', methods=['POST'])
def send_batch_messages():
    """
    Envía mensajes masivos usando el CSV de contactos.
    
    Este endpoint procesa el CSV, filtra los contactos pendientes y
    envía mensajes usando plantillas de WhatsApp con los datos del CSV.
    
    Request Body:
        {
            "template_name": "prueba_matricula",  // Nombre de la plantilla
            "language_code": "es",  // Opcional, default: "es"
            "create_backup": true  // Opcional, default: true
        }
    
    Returns:
        JSON: Resumen del envío con estadísticas detalladas
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No se recibió JSON en el body'
            }), 400
        
        template_name = data.get('template_name', 'prueba_matricula')
        language_code = data.get('language_code', 'es')
        create_backup = data.get('create_backup', True)
        
        # Cargar CSV
        success, df, msg = csv_handler.load_csv()
        if not success:
            return jsonify({
                'success': False,
                'error': msg
            }), 400
        
        # Crear backup si se solicita
        # Los backups protegen contra pérdida de datos en caso de errores
        backup_path = None
        if create_backup:
            success, backup_path, backup_msg = csv_handler.create_backup(df)
            if not success:
                app.logger.warning(f"No se pudo crear backup: {backup_msg}")
        
        # Obtener contactos pendientes
        pending_contacts = csv_handler.get_pending_contacts(df)
        
        if not pending_contacts:
            return jsonify({
                'success': True,
                'message': 'No hay contactos pendientes de envío',
                'stats': csv_handler.get_statistics(df)
            }), 200
        
        # Procesar envíos
        results = []
        sent_count = 0
        error_count = 0
        
        for idx, row in pending_contacts:
            contact_info = csv_handler.get_contact_info(row)
            phone = contact_info['telefono']
            name = contact_info['nombre']
            
            # Extraer parámetros de la plantilla desde el CSV
            # IMPORTANTE: El orden DEBE coincidir con el orden de aparición en la plantilla
            # {{nombre}}, {{bootcamp}}, {{modalidad}}, {{ingles_inicio}}, {{ingles_fin}}, 
            # {{inicio_formacion}}, {{horario}}, {{lugar}}
            parameters = [
                str(row.get('nombre', '')),
                str(row.get('bootcamp', '')),
                str(row.get('modalidad', '')),
                str(row.get('ingles_inicio', '')),
                str(row.get('ingles_fin', '')),
                str(row.get('inicio_formacion', '')),
                str(row.get('horario', '')),
                str(row.get('lugar', ''))
            ]
            
            # Enviar mensaje usando plantilla
            success, result = whatsapp_service.send_template_message(
                phone, 
                template_name, 
                parameters,
                language_code
            )
            
            # Actualizar estado en el DataFrame
            df = csv_handler.update_send_status(df, idx, success, result)
            
            # Registrar resultado
            results.append({
                'name': name,
                'phone': phone,
                'success': success,
                'result': result if success else None,
                'error': result if not success else None
            })
            
            if success:
                sent_count += 1
            else:
                error_count += 1
            
            # Delay entre mensajes para respetar rate limits de la API
            # Esto previene bloqueos temporales por exceso de peticiones
            if idx < len(pending_contacts) - 1:
                time.sleep(DELAY_SECONDS)
        
        # Guardar cambios en el CSV
        csv_handler.save_csv(df)
        
        # Preparar respuesta con resumen completo
        return jsonify({
            'success': True,
            'message': 'Envío masivo completado',
            'template_name': template_name,
            'language_code': language_code,
            'stats': {
                'sent': sent_count,
                'errors': error_count,
                'total_processed': len(pending_contacts)
            },
            'backup_path': backup_path,
            'results': results
        }), 200
    
    except Exception as e:
        app.logger.error(f"Error en send_batch_messages: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500


@app.route('/api/contacts/stats', methods=['GET'])
def get_contacts_stats():
    """
    Obtiene estadísticas sobre los contactos en el CSV.
    
    Este endpoint proporciona métricas útiles para monitorear el
    progreso de las campañas de mensajería.
    
    Returns:
        JSON: Estadísticas detalladas de los contactos
    """
    try:
        # Cargar CSV
        success, df, msg = csv_handler.load_csv()
        if not success:
            return jsonify({
                'success': False,
                'error': msg
            }), 400
        
        # Calcular estadísticas
        stats = csv_handler.get_statistics(df)
        
        return jsonify({
            'success': True,
            'stats': stats
        }), 200
    
    except Exception as e:
        app.logger.error(f"Error en get_contacts_stats: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500


@app.route('/api/contacts/pending', methods=['GET'])
def get_pending_contacts():
    """
    Lista los contactos pendientes de envío.
    
    Útil para revisar qué contactos serán procesados antes de
    ejecutar un envío masivo.
    
    Returns:
        JSON: Lista de contactos pendientes con su información
    """
    try:
        # Cargar CSV
        success, df, msg = csv_handler.load_csv()
        if not success:
            return jsonify({
                'success': False,
                'error': msg
            }), 400
        
        # Obtener contactos pendientes
        pending_contacts = csv_handler.get_pending_contacts(df)
        
        # Formatear información para la respuesta
        contacts_list = []
        for idx, row in pending_contacts:
            contact_info = csv_handler.get_contact_info(row)
            contacts_list.append(contact_info)
        
        return jsonify({
            'success': True,
            'count': len(contacts_list),
            'contacts': contacts_list
        }), 200
    
    except Exception as e:
        app.logger.error(f"Error en get_pending_contacts: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500


@app.route('/api/debug/template-payload', methods=['GET'])
def debug_template_payload():
    """
    Endpoint de debug para ver el payload que se enviaría a WhatsApp.
    
    Muestra exactamente qué JSON se construiría para el primer contacto
    pendiente, sin enviarlo realmente.
    
    Returns:
        JSON: Payload que se enviaría a WhatsApp
    """
    try:
        # Cargar CSV
        success, df, msg = csv_handler.load_csv()
        if not success:
            return jsonify({
                'success': False,
                'error': msg
            }), 400
        
        # Obtener primer contacto pendiente
        pending_contacts = csv_handler.get_pending_contacts(df)
        
        if not pending_contacts:
            return jsonify({
                'success': False,
                'error': 'No hay contactos pendientes'
            }), 400
        
        # Tomar el primer contacto
        idx, row = pending_contacts[0]
        contact_info = csv_handler.get_contact_info(row)
        phone = contact_info['telefono']
        
        # Extraer parámetros igual que en send_batch
        parameters = [
            str(row.get('nombre', '')),
            str(row.get('bootcamp', '')),
            str(row.get('modalidad', '')),
            str(row.get('ingles_inicio', '')),
            str(row.get('ingles_fin', '')),
            str(row.get('inicio_formacion', '')),
            str(row.get('horario', '')),
            str(row.get('lugar', ''))
        ]
        
        # Construir el payload (sin enviarlo)
        normalized_phone = phone.strip().replace('+', '').replace(' ', '').replace('-', '')
        
        # Construir payload manualmente para mostrarlo
        components = []
        body_parameters = []
        for param_value in parameters:
            text_value = str(param_value).strip() if param_value else ""
            body_parameters.append({
                "type": "text",
                "text": text_value
            })
        
        components.append({
            "type": "body",
            "parameters": body_parameters
        })
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": normalized_phone,
            "type": "template",
            "template": {
                "name": "prueba_matricula",
                "language": {
                    "code": "es"
                },
                "components": components
            }
        }
        
        return jsonify({
            'success': True,
            'contact': {
                'nombre': contact_info['nombre'],
                'phone': phone,
                'phone_normalized': normalized_phone
            },
            'parameters': parameters,
            'payload': payload,
            'payload_json_string': json.dumps(payload, indent=2)
        }), 200
    
    except Exception as e:
        app.logger.error(f"Error en debug_template_payload: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500


@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """
    Webhook para recibir notificaciones de WhatsApp.
    
    Este endpoint maneja dos tipos de peticiones:
    1. GET: Verificación del webhook por parte de Meta (una sola vez)
    2. POST: Recepción de eventos (mensajes, respuestas, etc.)
    
    El webhook captura las respuestas de los usuarios y las registra en el CSV,
    permitiendo trazabilidad completa de las conversaciones.
    
    Returns:
        - GET: Challenge token para verificación
        - POST: Status 200 para confirmar recepción
    """
    if request.method == 'GET':
        # Verificación del webhook por parte de Meta
        # Esto solo ocurre una vez durante la configuración inicial
        verify_token = os.getenv('VERIFY_TOKEN', 'mi_token_secreto')
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == verify_token:
            app.logger.info('Webhook verificado exitosamente')
            return challenge, 200
        else:
            app.logger.warning('Fallo en la verificación del webhook')
            return 'Forbidden', 403
    
    elif request.method == 'POST':
        # Recepción de eventos de WhatsApp
        try:
            body = request.get_json()
            
            # Log del evento recibido para debugging
            app.logger.info(f"Webhook recibido: {body}")
            
            # Verificar que el evento tenga la estructura esperada
            # WhatsApp envía eventos en este formato específico
            if not body or 'entry' not in body:
                return jsonify({'status': 'ok'}), 200
            
            # Procesar cada entrada (normalmente es una sola)
            for entry in body.get('entry', []):
                for change in entry.get('changes', []):
                    value = change.get('value', {})
                    
                    # Verificar si hay mensajes en el evento
                    messages = value.get('messages', [])
                    if not messages:
                        continue
                    
                    # Procesar cada mensaje
                    for message in messages:
                        # Extraer información del remitente
                        from_number = message.get('from', '')
                        message_type = message.get('type', '')
                        
                        response_text = None
                        button_id = None
                        
                        # Manejar diferentes tipos de respuesta
                        # Los botones interactivos envían un tipo especial
                        if message_type == 'interactive':
                            interactive = message.get('interactive', {})
                            button_reply = interactive.get('button_reply', {})
                            button_id = button_reply.get('id', '')
                            response_text = button_reply.get('title', '')
                        
                        # Manejar respuestas de texto plano
                        elif message_type == 'text':
                            response_text = message.get('text', {}).get('body', '')
                        
                        # Si tenemos una respuesta, procesarla
                        if response_text and from_number:
                            # Normalizar la respuesta para comparación
                            # Esto permite detectar "SI", "si", "Si", "sí", "SÍ", etc.
                            response_normalized = response_text.strip().lower()
                            
                            # Variantes válidas de "Sí" y "No"
                            # Incluye con y sin tilde, diferentes capitalizaciones
                            valid_yes = ['si', 'sí', 'yes', 'y']
                            valid_no = ['no', 'n']
                            
                            # Verificar si la respuesta es válida
                            is_valid_response = (
                                response_normalized in valid_yes or 
                                response_normalized in valid_no
                            )
                            
                            if is_valid_response:
                                # Cargar CSV
                                success, df, msg = csv_handler.load_csv()
                                if not success:
                                    app.logger.error(f"Error cargando CSV: {msg}")
                                    continue
                                
                                # Determinar la respuesta normalizada para guardar
                                # Esto estandariza el formato en el CSV
                                if response_normalized in valid_yes:
                                    standardized_response = "Sí"
                                else:
                                    standardized_response = "No"
                                
                                # Actualizar respuesta en el CSV
                                success, df, msg = csv_handler.update_response(
                                    df,
                                    from_number,
                                    standardized_response,
                                    button_id
                                )
                                
                                if success:
                                    # Guardar cambios
                                    csv_handler.save_csv(df)
                                    app.logger.info(f"✅ {msg} - Respuesta: '{standardized_response}'")
                                    
                                    # Enviar mensaje de agradecimiento
                                    # Esto mejora la experiencia del usuario y confirma la recepción
                                    thank_you_message = (
                                        "¡Muchas gracias por tu respuesta! 🙏\n\n"
                                        "Hemos registrado tu confirmación correctamente. "
                                        "Si tienes alguna pregunta adicional, no dudes en contactarnos. "
                                        "¡Que tengas un excelente día! "
                                    )
                                    
                                    # Enviar mensaje de agradecimiento de forma asíncrona
                                    # No bloqueamos el webhook si este envío falla
                                    try:
                                        whatsapp_service.send_text_message(
                                            from_number,
                                            thank_you_message
                                        )
                                        app.logger.info(f"📨 Mensaje de agradecimiento enviado a {from_number}")
                                    except Exception as e:
                                        app.logger.error(f"Error enviando agradecimiento: {str(e)}")
                                else:
                                    app.logger.warning(f"⚠️ {msg}")
                            else:
                                # Respuesta no válida - no actualizar CSV
                                # Esto evita contaminar los datos con respuestas irrelevantes
                                app.logger.info(
                                    f"ℹ️ Respuesta no válida recibida de {from_number}: '{response_text}'"
                                )
                                
                                # Enviar mensaje indicando que solo se aceptan "Sí" o "No"
                                invalid_response_message = (
                                    "⚠️ Solo se aceptan respuestas de *Sí* o *No*.\n\n"
                                    "Por favor, responde con:\n"
                                    "• *Sí* (o Si, yes, y)\n"
                                    "• *No* (o no, n)\n\n"
                                    "Gracias por tu comprensión. "
                                )
                                
                                try:
                                    whatsapp_service.send_text_message(
                                        from_number,
                                        invalid_response_message
                                    )
                                    app.logger.info(f"📨 Mensaje de validación enviado a {from_number}")
                                except Exception as e:
                                    app.logger.error(f"Error enviando mensaje de validación: {str(e)}")
            
            # Siempre retornar 200 para confirmar recepción
            # Esto evita que WhatsApp reintente enviar el evento
            return jsonify({'status': 'ok'}), 200
        
        except Exception as e:
            app.logger.error(f"Error procesando webhook: {str(e)}")
            # Aún así retornar 200 para evitar reintentos
            return jsonify({'status': 'ok'}), 200


@app.errorhandler(404)
def not_found(error):
    """
    Manejo de rutas no encontradas.
    
    Proporciona una respuesta JSON consistente para endpoints inexistentes.
    """
    return jsonify({
        'success': False,
        'error': 'Endpoint no encontrado'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """
    Manejo de errores internos del servidor.
    
    Captura errores no manejados y proporciona respuesta JSON.
    """
    app.logger.error(f"Error interno: {str(error)}")
    return jsonify({
        'success': False,
        'error': 'Error interno del servidor'
    }), 500


if __name__ == '__main__':
    # Configuración para desarrollo
    # En producción, usar un servidor WSGI como Gunicorn
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV', 'production') == 'development'
    
    print("\n" + "="*70)
    print("  🚀 WhatsApp Messaging API Server")
    print("="*70)
    print(f"\n  📡 Puerto: {port}")
    print(f"  🔧 Debug: {debug}")
    print(f"  📂 CSV: {CSV_PATH}")
    print(f"  ⏱️  Delay entre mensajes: {DELAY_SECONDS}s")
    print("\n" + "="*70 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
