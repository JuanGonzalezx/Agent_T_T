import os
import atexit
from flask import Flask, jsonify
from flask_cors import CORS

# Importar Servicios (Asegúrate de haber movido los archivos a app/services/)
from app.services.whatsapp_service import WhatsAppService
from app.services.google_drive_service import GoogleDriveService
from app.services.db_handler import DatabaseHandler
from app.services.sync_service import SyncService
from app.core.logic import ResponseLogic

# --- Instancias Globales (Singleton) ---
whatsapp_service = WhatsAppService()
google_drive_service = GoogleDriveService()
db_handler = None
sync_service = None
logic_brain = None

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    # Configuración básica
    app.config['DELAY_SECONDS'] = float(os.getenv("DELAY_SECONDS", "1.5"))
    
    # Inicializar Base de Datos y Servicios
    global db_handler, sync_service, logic_brain
    
    # Ruta de la BD (Ajustada para que quede en la carpeta data/)
    db_path = os.path.join(os.getcwd(), 'data', 'whatsapp_tracking.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    db_handler = DatabaseHandler(db_path)
    sync_service = SyncService(db_handler, google_drive_service)
    logic_brain = ResponseLogic(db_handler, whatsapp_service)
    
    # Iniciar Scheduler
    sync_service.start()
    atexit.register(lambda: sync_service.shutdown())

    # --- Registrar Controladores (Blueprints) ---
    from app.controllers.system_controller import system_bp
    from app.controllers.webhook_controller import webhook_bp
    from app.controllers.message_controller import message_bp
    from app.controllers.drive_controller import drive_bp
    from app.controllers.student_controller import student_bp
    from app.controllers.bootcamp_controller import bootcamp_bp

    app.register_blueprint(system_bp)
    app.register_blueprint(webhook_bp)
    app.register_blueprint(message_bp, url_prefix='/api/messages')
    app.register_blueprint(drive_bp, url_prefix='/api') # Incluye /google y /sync
    app.register_blueprint(student_bp, url_prefix='/api') # Incluye /estudiantes y /contacts
    app.register_blueprint(bootcamp_bp, url_prefix='/api/bootcamps')

    # Manejadores de Error Globales
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'success': False, 'error': 'Endpoint no encontrado'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Error interno: {str(error)}")
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

    return app