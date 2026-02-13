from flask import Blueprint, jsonify, send_from_directory
from app import whatsapp_service, db_handler

system_bp = Blueprint('system', __name__)

@system_bp.route('/', methods=['GET'])
def index():
    """Información general de la API."""
    return jsonify({
        'service': 'WhatsApp Messaging API Server',
        'version': '2.0 (MVC Refactored)',
        'status': 'running',
        'database': 'Turso (cloud)' if db_handler.use_turso else 'SQLite (local)'
    }), 200

@system_bp.route('/health', methods=['GET'])
def health_check():
    """Health check para monitoreo."""
    valid, msg = whatsapp_service.validate_credentials()
    return jsonify({
        'status': 'healthy' if valid else 'warning',
        'service': 'WhatsApp Messaging API',
        'credentials': msg,
        'database': 'Turso (libSQL)'
    }), 200 if valid else 503

@system_bp.route('/privacy', methods=['GET'])
def privacy_policy():
    """Política de privacidad."""
    # Asegúrate de tener la carpeta 'templates' en la raíz o ajusta la ruta
    return send_from_directory('../templates', 'privacy.html')

@system_bp.route('/api/database/reset', methods=['DELETE'])
def reset_database():
    """[CRITICAL] Elimina TODO el contenido de la base de datos."""
    try:
        success, msg = db_handler.reset_database()
        return jsonify({
            'success': success,
            'message': msg if success else None,
            'error': msg if not success else None
        }), 200 if success else 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500