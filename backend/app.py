"""
API REST para el sistema de envío de mensajes WhatsApp.

Este servidor Flask expone endpoints para gestionar el envío de mensajes
a través de WhatsApp Business API, proporcionando una interfaz HTTP limpia
y bien documentada para integraciones externas.
"""

import os
import time
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
    Envía un mensaje simple a un número de teléfono.
    
    Este endpoint permite enviar un mensaje de texto a un número específico
    sin necesidad de usar el CSV, útil para pruebas o envíos individuales.
    
    Request Body:
        {
            "phone": "+573001234567",
            "message": "Texto del mensaje"
        }
    
    Returns:
        JSON: Resultado del envío con el ID del mensaje o error
    """
    try:
        data = request.get_json()
        
        # Validación de entrada
        # Rechazar peticiones sin los campos requeridos previene errores
        if not data:
            return jsonify({
                'success': False,
                'error': 'No se recibió JSON en el body'
            }), 400
        
        phone = data.get('phone')
        message = data.get('message')
        
        if not phone or not message:
            return jsonify({
                'success': False,
                'error': 'Campos requeridos: phone, message'
            }), 400
        
        # Enviar mensaje
        success, result = whatsapp_service.send_text_message(phone, message)
        
        if success:
            return jsonify({
                'success': True,
                'message_id': result,
                'phone': phone
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
    envía mensajes de forma controlada con delays para evitar rate limits.
    
    Request Body:
        {
            "message": "Texto del mensaje a enviar",
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
        
        message = data.get('message')
        create_backup = data.get('create_backup', True)
        
        if not message:
            return jsonify({
                'success': False,
                'error': 'Campo requerido: message'
            }), 400
        
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
            
            # Enviar mensaje
            success, result = whatsapp_service.send_text_message(phone, message)
            
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
