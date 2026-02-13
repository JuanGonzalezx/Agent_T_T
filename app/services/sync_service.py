import logging
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

class SyncService:
    def __init__(self, db_handler, drive_service):
        self.db = db_handler
        self.drive = drive_service
        self.pending_sync = False
        
        # Estado cacheado del archivo actual
        self.current_file_id = None
        self.current_token = None
        self.current_mime_type = None
        
        # Inicializar Scheduler
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(
            func=self._sync_job,
            trigger="interval",
            minutes=5,
            id='sync_drive_job',
            replace_existing=True
        )

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("⏰ Scheduler iniciado: Sincronización automática activa")

    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown()

    def set_current_file(self, file_id, token, mime_type):
        """Actualiza el contexto del archivo activo para la sincronización"""
        self.current_file_id = file_id
        self.current_token = token
        self.current_mime_type = mime_type
        logger.info(f"📁 Contexto de archivo actualizado para sync: {file_id}")

    def mark_pending(self):
        """Marca que hay cambios pendientes en la BD para subir a Drive"""
        self.pending_sync = True

    def _sync_job(self):
        """Tarea interna del scheduler que se ejecuta cada 5 min"""
        if not self.pending_sync:
            return
        
        if not self.current_file_id or not self.current_token:
            logger.warning("[SYNC] Omitiendo sync: Sin credenciales de Google cacheadas")
            return

        logger.info("🔄 Ejecutando sincronización automática con Drive...")
        try:
            # Obtener datos desde Turso
            estudiantes = self.db.get_all_estudiantes()
            if not estudiantes:
                logger.warning("[SYNC] No hay datos en Turso para sincronizar")
                return

            df = pd.DataFrame(estudiantes)
            update_success = False
            
            # Determinar método de actualización según tipo MIME
            mime = self.current_mime_type
            if mime == 'application/vnd.google-apps.spreadsheet':
                update_success, _ = self.drive.update_google_sheet(
                    self.current_file_id, self.current_token, df
                )
            elif mime == 'text/csv':
                update_success, _ = self.drive.update_csv_file(
                    self.current_file_id, self.current_token, df
                )
            elif 'spreadsheetml' in mime or 'excel' in mime:
                update_success, _ = self.drive.update_xlsx_file(
                    self.current_file_id, self.current_token, df
                )
            else:
                logger.warning(f"[SYNC] Tipo no soportado para auto-sync: {mime}")
                return

            if update_success:
                self.pending_sync = False
                logger.info("[SYNC] Drive actualizado exitosamente - OK")
            else:
                logger.error("[SYNC] Falló la actualización en Drive")

        except Exception as e:
            logger.error(f"[SYNC] Excepción crítica: {str(e)}")