import os
import sys
import logging
from dotenv import load_dotenv
import atexit
from flask import Flask, jsonify
from flask_cors import CORS
load_dotenv()

# =============================================================================
# CONFIGURACIÓN DE LOGGING PARA RENDER/GUNICORN
# =============================================================================
# Configurar logging ANTES de importar cualquier módulo
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Forzar salida a stdout para Render
    ]
)
# Reducir ruido de librerías externas
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('langchain').setLevel(logging.WARNING)
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
    
    # ════════════════════════════════════════════════════════
    # PREVENCIÓN DE MÚLTIPLES SCHEDULERS EN GUNICORN/RENDER
    # Solo iniciamos el scheduler si:
    # 1. Es local (no gunicorn) y es el proceso principal (WERKZEUG_RUN_MAIN)
    # 2. Es Gunicorn y es el worker designado (IS_SCHEDULER_WORKER)
    # ════════════════════════════════════════════════════════
    is_gunicorn = "gunicorn" in os.environ.get("SERVER_SOFTWARE", "")
    
    if is_gunicorn:
        if os.environ.get("IS_SCHEDULER_WORKER") == "True":
            sync_service.start()
            atexit.register(lambda: sync_service.shutdown())
            app.logger.info("Scheduler iniciado en el Worker designado de Gunicorn.")
    else:
        # Modo local Flask (evitar doble ejecución por el reloader)
        if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            sync_service.start()
            atexit.register(lambda: sync_service.shutdown())
            app.logger.info("Scheduler iniciado en modo desarrollo local.")

    # --- Registrar Controladores (Blueprints) ---
    from app.controllers.system_controller import system_bp
    from app.controllers.webhook_controller import webhook_bp
    from app.controllers.message_controller import message_bp
    from app.controllers.drive_controller import drive_bp
    from app.controllers.student_controller import student_bp
    from app.controllers.bootcamp_controller import bootcamp_bp
    from app.controllers.campaign_controller import campaign_bp

    app.register_blueprint(system_bp)
    app.register_blueprint(webhook_bp)
    app.register_blueprint(message_bp, url_prefix='/api/messages')
    app.register_blueprint(drive_bp, url_prefix='/api') # Incluye /google y /sync
    app.register_blueprint(student_bp, url_prefix='/api') # Incluye /estudiantes y /contacts
    app.register_blueprint(bootcamp_bp, url_prefix='/api/bootcamps')
    app.register_blueprint(campaign_bp, url_prefix='/api/campaigns')

    # Manejadores de Error Globales
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'success': False, 'error': 'Endpoint no encontrado'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Error interno: {str(error)}")
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

    return app


# =============================================================================
# METADATA DEL PAQUETE
# =============================================================================
"""
Backend Flask para sistema de mensajería WhatsApp.

Este paquete proporciona una API REST completa para el envío de mensajes
de WhatsApp usando Turso como fuente única de verdad.

Módulos:
    - controllers: Endpoints HTTP (webhooks, mensajes, estudiantes, etc.)
    - services: Servicios externos (WhatsApp API, Drive, Turso)
    - core: Lógica de negocio (procesamiento de respuestas)
    - agent: Agente IA con LangGraph (futuro)
    - utils: Utilidades de normalización de datos
"""

__version__ = '2.0.0'
__author__ = 'Agent_T_T'
__all__ = ['create_app', 'app', 'whatsapp_service', 'db_handler', 'google_drive_service']


# =============================================================================
# INSTANCIA WSGI PARA PRODUCCIÓN
# =============================================================================
# Gunicorn y otros servidores WSGI buscan: gunicorn app:app
# Esta instancia se crea al importar el paquete
app = create_app()
