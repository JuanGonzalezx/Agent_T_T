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
from typing import Dict, Any, Tuple
import io
import requests
import pandas as pd

from services.whatsapp_service import WhatsAppService
from services.google_drive_service import GoogleDriveService
from services.db_handler import DatabaseHandler
from utils.csv_handler import CSVHandler
from utils.data_normalizer import (
    normalize_phone_column,
    clean_phone_numbers,
    add_tracking_columns,
    validate_dataframe
)


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
google_drive_service = GoogleDriveService()
csv_handler = CSVHandler(CSV_PATH)

# SQLite con soporte para disco persistente en Render
# Si existe /data (volumen en Render), usa ese path; sino, usa local
DB_PATH = os.path.join(os.getenv('DATA_DIR', '.'), 'whatsapp_tracking.db')
db_handler = DatabaseHandler(DB_PATH)

# Variables para sincronización automática con Drive
pending_sync = False
cached_file_id = None
cached_access_token = None
cached_mime_type = None


def sync_to_drive_if_needed():
    """
    Sincroniza bd_envio.csv a Google Drive si hay cambios pendientes.
    Esta función es llamada por el scheduler cada 5 minutos.
    Solo sincroniza si pending_sync es True, optimizando llamadas a la API.
    """
    global pending_sync, cached_file_id, cached_access_token, cached_mime_type
    
    # Verificar si hay cambios pendientes
    if not pending_sync:
        app.logger.info("⏭️ Sync omitido: No hay cambios pendientes")
        return
    
    # Verificar credenciales cacheadas
    if not cached_file_id or not cached_access_token:
        app.logger.warning("⚠️ Sync omitido: No hay credenciales de Google cacheadas")
        return
    
    try:
        app.logger.info("🔄 Iniciando sincronización automática con Drive...")
        
        # Cargar CSV local
        success, df, msg = csv_handler.load_csv()
        if not success:
            app.logger.error(f"❌ Error cargando CSV: {msg}")
            return
        
        # Actualizar en Drive según el tipo de archivo
        update_success = False
        update_message = ""
        
        if cached_mime_type == 'application/vnd.google-apps.spreadsheet':
            update_success, update_message = google_drive_service.update_google_sheet(
                cached_file_id, cached_access_token, df
            )
        elif cached_mime_type == 'text/csv':
            update_success, update_message = google_drive_service.update_csv_file(
                cached_file_id, cached_access_token, df
            )
        elif cached_mime_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
            update_success, update_message = google_drive_service.update_xlsx_file(
                cached_file_id, cached_access_token, df
            )
        else:
            app.logger.warning(f"⚠️ Tipo de archivo no soportado: {cached_mime_type}")
            return
        
        if update_success:
            pending_sync = False  # Resetear bandera
            app.logger.info(f"✅ Sincronización automática exitosa: {update_message}")
        else:
            app.logger.error(f"❌ Fallo en sincronización automática: {update_message}")
            
    except Exception as e:
        app.logger.error(f"❌ Error en sincronización automática: {str(e)}")
        import traceback
        app.logger.error(traceback.format_exc())


@app.route('/', methods=['GET'])
def index():
    """
    Ruta raíz del servidor - Información general de la API.
    
    Returns:
        JSON: Información sobre la API y endpoints disponibles
    """
    return jsonify({
        'service': 'WhatsApp Messaging API Server',
        'version': '2.0',
        'status': 'running',
        'database': 'Turso (cloud)' if db_handler.use_turso else 'SQLite (local)',
        'endpoints': {
            'health': '/health',
            'estudiantes': '/api/estudiantes/all',
            'bootcamps': '/api/bootcamps',
            'estadisticas': '/api/estadisticas',
            'send_message': '/api/messages/send-simple',
            'send_batch': '/api/messages/send-batch',
            'webhook': '/webhook'
        }
    }), 200


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
            # {{1}}, {{2}}, {{3}}, {{4}}, {{5}}, {{6}}, {{7}}, {{8}}
            parameters = [
                str(row.get('nombre', '')),
                str(row.get('modalidad', '')),
                str(row.get('bootcamp_nombre', '')),
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
            
            # Guardar también en SQLite
            if success:
                estudiante_data = {
                    'telefono_e164': phone,
                    'nombre': name,
                    'bootcamp_id': row.get('bootcamp_id', ''),
                    'bootcamp_nombre': row.get('bootcamp_nombre', ''),
                    'modalidad': row.get('modalidad', ''),
                    'ingles_inicio': row.get('ingles_inicio', ''),
                    'ingles_fin': row.get('ingles_fin', ''),
                    'inicio_formacion': row.get('inicio_formacion', ''),
                    'horario': row.get('horario', ''),
                    'lugar': row.get('lugar', ''),
                    'opt_in': row.get('opt_in', ''),
                    'estado_envio': 'sent',
                    'fecha_envio': df.at[idx, 'fecha_envio'],
                    'message_id': result
                }
                db_success, db_msg = db_handler.insert_or_update_estudiante(estudiante_data)
                if not db_success:
                    app.logger.warning(f"⚠️ No se pudo guardar en SQLite: {db_msg}")
            
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

# ============================================================================
# Google Drive Integration Endpoint
# ============================================================================

@app.route('/api/google/upload', methods=['POST'])
def upload_from_google():
    """
    Procesa un archivo de Google Drive: descarga, normaliza, actualiza CSV local y Drive.
    
    Flujo:
    1. Autenticación con Google OAuth
    2. Selección de archivo (Sheet/CSV/XLSX) desde Drive
    3. Descarga del contenido del archivo
    4. Normalización de columnas y teléfonos
    5. Añade columnas de tracking (estado_envio, fecha_envio, message_id, respuesta, fecha_respuesta)
    6. Guarda en bd_envio.csv local
    7. Actualiza el archivo original en Drive con las nuevas columnas
    
    Request Body:
        {
            "fileId": "1abc...",      // ID del archivo en Google Drive
            "accessToken": "ya29..."   // Token OAuth del Google Picker
        }
    
    Returns:
        JSON: Datos procesados con información de sincronización
    """
    try:
        # Validar request
        data = request.get_json() or {}
        file_id = data.get('fileId') or data.get('file_id')
        access_token = data.get('accessToken') or data.get('access_token')
        
        if not file_id:
            return jsonify({'success': False, 'error': 'fileId requerido'}), 400
        if not access_token:
            return jsonify({'success': False, 'error': 'accessToken requerido'}), 400
        
        # Cachear credenciales para sincronización automática
        global cached_file_id, cached_access_token, cached_mime_type
        cached_file_id = file_id
        cached_access_token = access_token
        
        app.logger.info(f"📥 Procesando archivo de Google Drive: {file_id}")
        
        # 1. Obtener metadata del archivo
        success, metadata, error = google_drive_service.get_file_metadata(file_id, access_token)
        if not success:
            return jsonify({'success': False, 'error': error}), 400
        
        mime_type = metadata.get('mimeType', '')
        file_name = metadata.get('name', file_id)
        is_google_sheet = mime_type == 'application/vnd.google-apps.spreadsheet'
        
        # Cachear mime_type para sincronización automática
        cached_mime_type = mime_type
        
        app.logger.info(f"📄 Archivo: {file_name} | Tipo: {mime_type}")
        
        # Validar tipo de archivo soportado
        supported_types = [
            'application/vnd.google-apps.spreadsheet',
            'text/csv',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ]
        
        if mime_type not in supported_types and not file_name.lower().endswith(('.csv', '.xlsx')):
            return jsonify({'success': False, 'error': f'Tipo no soportado: {mime_type}'}), 400
        
        # 2. Descargar contenido del archivo
        success, content, error = google_drive_service.download_file_content(
            file_id, access_token, is_google_sheet
        )
        if not success:
            return jsonify({'success': False, 'error': error}), 400
        
        app.logger.info(f"✅ Archivo descargado ({len(content)} bytes)")
        
        # 3. Parsear contenido a DataFrame
        success, df, error = google_drive_service.parse_file_content(content)
        if not success:
            return jsonify({'success': False, 'error': error}), 400
        
        if df.empty:
            return jsonify({'success': False, 'error': 'El archivo no contiene datos'}), 400
        
        app.logger.info(f"✅ Archivo parseado: {len(df)} filas, {len(df.columns)} columnas")
        
        # 4. Normalizar columna de teléfono
        success, df, error = normalize_phone_column(df)
        if not success:
            return jsonify({'success': False, 'error': error}), 400
        
        app.logger.info("✅ Columna de teléfono normalizada")
        
        # 5. Limpiar números de teléfono
        df = clean_phone_numbers(df)
        app.logger.info("✅ Números de teléfono limpiados")
        
        # 6. Añadir columnas de tracking (estado_envio, fecha_envio, message_id, respuesta, fecha_respuesta)
        df = add_tracking_columns(df)
        app.logger.info("✅ Columnas de tracking añadidas")
        
        # 7. Validar DataFrame final
        valid, msg = validate_dataframe(df)
        if not valid:
            return jsonify({'success': False, 'error': msg}), 400
        
        app.logger.info(f"✅ DataFrame validado: {msg}")
        
        # 8. Guardar localmente (sobreescribir bd_envio.csv)
        ok, save_msg = csv_handler.save_csv(df)
        if not ok:
            app.logger.error(f"❌ Error guardando CSV: {save_msg}")
            return jsonify({'success': False, 'error': f'No se pudo guardar CSV: {save_msg}'}), 500
        
        app.logger.info(f"✅ bd_envio.csv actualizado con {len(df)} registros")
        
        # 8.1. Guardar en SQLite
        app.logger.info("💾 Guardando datos en SQLite...")
        sqlite_success_count = 0
        sqlite_error_count = 0
        
        # Primero, registrar bootcamps únicos
        bootcamp_ids = df['bootcamp_id'].dropna().unique()
        for bootcamp_id in bootcamp_ids:
            if bootcamp_id:
                # Obtener el nombre correspondiente
                bootcamp_row = df[df['bootcamp_id'] == bootcamp_id].iloc[0]
                bootcamp_nombre = bootcamp_row.get('bootcamp_nombre', '')
                success, msg = db_handler.insert_or_update_bootcamp(bootcamp_id, bootcamp_nombre)
                if success:
                    app.logger.info(f"  ✓ Bootcamp registrado: {bootcamp_id}")
        
        # Luego, registrar estudiantes
        for idx, row in df.iterrows():
            estudiante_data = {
                'telefono_e164': row.get('telefono_e164', ''),
                'nombre': row.get('nombre', ''),
                'bootcamp_id': row.get('bootcamp_id', ''),
                'bootcamp_nombre': row.get('bootcamp_nombre', ''),
                'modalidad': row.get('modalidad', ''),
                'ingles_inicio': row.get('ingles_inicio', ''),
                'ingles_fin': row.get('ingles_fin', ''),
                'inicio_formacion': row.get('inicio_formacion', ''),
                'horario': row.get('horario', ''),
                'lugar': row.get('lugar', ''),
                'opt_in': row.get('opt_in', ''),
                'estado_envio': row.get('estado_envio', ''),
                'fecha_envio': row.get('fecha_envio', None),
                'message_id': row.get('message_id', ''),
                'respuesta': row.get('respuesta', ''),
                'fecha_respuesta': row.get('fecha_respuesta', None)
            }
            success, msg = db_handler.insert_or_update_estudiante(estudiante_data)
            if success:
                sqlite_success_count += 1
            else:
                sqlite_error_count += 1
                app.logger.warning(f"  ⚠️ Error guardando estudiante {estudiante_data['nombre']}: {msg}")
        
        app.logger.info(f"✅ SQLite: {sqlite_success_count} estudiantes guardados, {sqlite_error_count} errores")
        
        # 9. Actualizar archivo en Drive (con las nuevas columnas de tracking)
        update_success = False
        update_message = ""
        
        if is_google_sheet:
            update_success, update_message = google_drive_service.update_google_sheet(
                file_id, access_token, df
            )
        elif mime_type == 'text/csv':
            update_success, update_message = google_drive_service.update_csv_file(
                file_id, access_token, df
            )
        elif mime_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' or file_name.lower().endswith('.xlsx'):
            update_success, update_message = google_drive_service.update_xlsx_file(
                file_id, access_token, df
            )
        else:
            app.logger.info(f"ℹ️ Tipo de archivo no soportado para actualización: {mime_type}")
            update_message = f"Tipo de archivo {mime_type} no se actualiza en Drive"
        
        if update_success:
            app.logger.info(f"✅ Archivo en Drive actualizado: {update_message}")
        else:
            app.logger.warning(f"⚠️ No se pudo actualizar Drive: {update_message}")
        
        # 10. Preparar respuesta
        csv_output = io.StringIO()
        df.to_csv(csv_output, index=False)
        
        response_data = {
            'success': True,
            'message': 'Archivo procesado y sincronizado correctamente',
            'file_name': file_name,
            'mimeType': mime_type,
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'csv_data': csv_output.getvalue(),
            'columns': df.columns.tolist(),
            'drive_updated': update_success,
            'update_message': update_message
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        app.logger.error(f"❌ Error en upload_from_google: {str(e)}")
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': f'Error interno: {str(e)}'}), 500


@app.route('/api/messages/send-template', methods=['POST'])
def send_template():
    """
    Envía un mensaje de plantilla a un único contacto.
    
    Este endpoint permite probar plantillas individuales con parámetros personalizados.
    
    Request Body:
        {
            "phone": "+573154963483",
            "template_name": "prueba_matricula",
            "parameters": ["Juan", "IA", "Virtual", "20", "1 nov", "5 nov", "L-V 6pm", "Sede Central"],
            "language_code": "es"  // Opcional, default: "es"
        }
    
    Returns:
        JSON: Resultado del envío con message_id o error
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No se recibió JSON en el body'
            }), 400
        
        # Validar campos requeridos
        phone = data.get('phone')
        template_name = data.get('template_name')
        parameters = data.get('parameters', [])
        language_code = data.get('language_code', 'es')
        
        if not phone:
            return jsonify({
                'success': False,
                'error': 'El campo "phone" es requerido'
            }), 400
        
        if not template_name:
            return jsonify({
                'success': False,
                'error': 'El campo "template_name" es requerido'
            }), 400
        
        # Enviar mensaje
        success, result = whatsapp_service.send_template_message(
            phone,
            template_name,
            parameters,
            language_code
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Plantilla enviada exitosamente',
                'message_id': result,
                'phone': phone,
                'template_name': template_name,
                'parameters': parameters,
                'language_code': language_code
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result,
                'phone': phone,
                'template_name': template_name,
                'parameters': parameters,
                'language_code': language_code
            }), 400
    
    except Exception as e:
        app.logger.error(f"Error en send_template: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500


@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """
    Webhook para recibir notificaciones de WhatsApp.

    Maneja:
    1) GET: verificación del webhook (una sola vez).
    2) POST: eventos de mensajes (texto, botones de plantilla, interactivos, etc.).
    """
    if request.method == 'GET':
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
        try:
            body = request.get_json()
            app.logger.info(f"Webhook recibido: {body}")

            if not body or 'entry' not in body:
                return jsonify({'status': 'ok'}), 200

            for entry in body.get('entry', []):
                for change in entry.get('changes', []):
                    value = change.get('value', {})
                    messages = value.get('messages', [])
                    if not messages:
                        continue

                    for message in messages:
                        from_number = message.get('from', '')
                        message_type = message.get('type', '')
                        context = message.get('context', {}) or {}

                        response_text = None
                        button_id = None

                        # (1) Botones de PLANTILLA (quick replies de plantilla)
                        if message_type == 'button':
                            btn = message.get('button', {}) or {}
                            response_text = btn.get('text', '')
                            # 'payload' puede venir o no; si no, usamos el texto como fallback
                            button_id = btn.get('payload') or response_text
                            app.logger.info(f"🟢 Botón de plantilla - payload: {button_id}, texto: {response_text}")

                        # (2) Interactivos enviados como 'interactive' (no-plantilla)
                        elif message_type == 'interactive':
                            interactive = message.get('interactive', {}) or {}
                            itype = interactive.get('type')

                            if itype == 'button_reply':
                                br = interactive.get('button_reply', {}) or {}
                                button_id = br.get('id') or br.get('payload')
                                response_text = br.get('title', '')
                                app.logger.info(f"🟦 Botón interactivo - id: {button_id}, texto: {response_text}")

                            elif itype == 'list_reply':
                                lr = interactive.get('list_reply', {}) or {}
                                button_id = lr.get('id')
                                response_text = lr.get('title', '')
                                app.logger.info(f"🟪 Lista interactiva - id: {button_id}, texto: {response_text}")

                            # (Opcional) Respuestas de Flows/NFM (si las usas)
                            elif itype == 'nfm_reply':
                                nfm = interactive.get('nfm_reply', {}) or {}
                                button_id = f"flow:{nfm.get('name','')}"
                                response_text = nfm.get('response_json')  # JSON de respuestas del flow
                                app.logger.info(f"🟨 Flow reply - id: {button_id}, payload: {response_text}")

                        # (3) Texto escrito por el usuario
                        elif message_type == 'text':
                            response_text = message.get('text', {}).get('body', '')
                            if context:
                                app.logger.info(f"💬 Texto (con contexto) - {response_text} | reply_to={context.get('id')}")
                            else:
                                app.logger.info(f"💬 Texto - {response_text}")

                        # ---- Normalización/validación de respuesta y guardado ----
                        if response_text and from_number:
                            response_normalized = str(response_text).strip().lower()

                            valid_yes = ['si', 'sí', 'yes', 'y']
                            valid_no = ['no', 'n']
                            is_valid_response = (response_normalized in valid_yes or
                                                 response_normalized in valid_no)

                            if is_valid_response:
                                standardized_response = "Sí" if response_normalized in valid_yes else "No"

                                success, df, msg = csv_handler.load_csv()
                                if not success:
                                    app.logger.error(f"Error cargando CSV: {msg}")
                                    continue

                                # Preferimos guardar algún identificador del "clic" o el id del mensaje respondido
                                correlation_id = button_id or context.get('id', '')

                                success, df, msg = csv_handler.update_response(
                                    df,
                                    from_number,
                                    standardized_response,
                                    correlation_id
                                )

                                if success:
                                    csv_handler.save_csv(df)
                                    app.logger.info(f"✅ {msg} - Respuesta: '{standardized_response}'")
                                    
                                    # Actualizar también en SQLite
                                    db_success, db_msg = db_handler.update_respuesta(
                                        from_number,
                                        standardized_response,
                                        df.at[csv_handler.find_contact_by_phone(df, from_number), 'fecha_respuesta']
                                    )
                                    if db_success:
                                        app.logger.info(f"✅ SQLite actualizado: {db_msg}")
                                    else:
                                        app.logger.warning(f"⚠️ SQLite no actualizado: {db_msg}")

                                    # Marcar pending sync (si usas este flag global)
                                    try:
                                        global pending_sync
                                        pending_sync = True
                                        app.logger.info("🔄 Cambios pendientes marcados para sincronización con Drive")
                                    except NameError:
                                        # Si no usas pending_sync en tu app, puedes ignorar este bloque
                                        pass

                                    # Agradecimiento (no bloquear si falla)
                                    try:
                                        whatsapp_service.send_text_message(
                                            from_number,
                                            "¡Muchas gracias por tu respuesta! 🙏\n\n"
                                            "Hemos registrado tu confirmación correctamente. "
                                            "Si tienes alguna pregunta adicional, no dudes en contactarnos. "
                                            "¡Que tengas un excelente día!"
                                        )
                                        app.logger.info(f"📨 Mensaje de agradecimiento enviado a {from_number}")
                                    except Exception as e:
                                        app.logger.error(f"Error enviando agradecimiento: {str(e)}")

                                else:
                                    # Verificar si ya había respondido anteriormente
                                    if msg.startswith("already_answered:"):
                                        previous_answer = msg.split(":", 1)[1]
                                        app.logger.info(f"⚠️ Usuario {from_number} ya respondió anteriormente: '{previous_answer}' - Ignorando nuevo intento")
                                        # No enviar ningún mensaje, simplemente ignorar
                                    else:
                                        app.logger.warning(f"⚠️ {msg}")

                            else:
                                # Respuesta no válida → verificar si ya respondió antes
                                app.logger.info(f"ℹ️ Respuesta no válida de {from_number}: '{response_text}'")
                                
                                # Verificar si el usuario ya tiene una respuesta registrada
                                success, df, msg = csv_handler.load_csv()
                                if success:
                                    idx = csv_handler.find_contact_by_phone(df, from_number)
                                    if idx is not None:
                                        respuesta_existente = str(df.at[idx, 'respuesta']).strip()
                                        if respuesta_existente and respuesta_existente != 'nan':
                                            # Ya respondió, ignorar mensaje inválido
                                            app.logger.info(f"ℹ️ Usuario ya respondió '{respuesta_existente}' - Ignorando mensaje inválido")
                                            continue
                                
                                # Si no ha respondido, enviar mensaje de validación
                                try:
                                    whatsapp_service.send_text_message(
                                        from_number,
                                        "⚠️ Solo se aceptan respuestas de *Sí* o *No*.\n\n"
                                        "Por favor, responde con:\n"
                                        "• *Sí* (o Si, yes, y)\n"
                                        "• *No* (o no, n)\n\n"
                                        "Gracias por tu comprensión."
                                    )
                                    app.logger.info(f"📨 Mensaje de validación enviado a {from_number}")
                                except Exception as e:
                                    app.logger.error(f"Error enviando mensaje de validación: {str(e)}")

            # Confirmar recepción para evitar reintentos de Meta
            return jsonify({'status': 'ok'}), 200

        except Exception as e:
            app.logger.error(f"Error procesando webhook: {str(e)}")
            # Aun con error respondemos 200 para evitar reintentos
            return jsonify({'status': 'ok'}), 200


@app.route('/api/sync/drive-manual', methods=['POST'])
def sync_drive_manual():
    """
    Fuerza una sincronización manual con Google Drive.
    
    Este endpoint permite ejecutar la sincronización inmediatamente
    sin esperar al próximo ciclo del scheduler. Útil para:
    - Testing de la funcionalidad de sync
    - Sincronización forzada cuando se necesita actualizar Drive inmediatamente
    - Debugging de problemas de sincronización
    
    Returns:
        JSON: Resultado de la operación de sincronización
    """
    try:
        app.logger.info("🔧 Sincronización manual solicitada")
        sync_to_drive_if_needed()
        return jsonify({
            'success': True,
            'message': 'Sincronización manual ejecutada',
            'pending_sync': pending_sync
        }), 200
    except Exception as e:
        app.logger.error(f"❌ Error en sincronización manual: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# SQLite Query Endpoints
# ============================================================================

@app.route('/api/estudiantes/all', methods=['GET'])
def get_all_estudiantes():
    """
    Obtiene todos los estudiantes con paginación.
    
    Query Parameters:
        limit (int): Número máximo de registros (default: 100)
        offset (int): Número de registros a saltar (default: 0)
    
    Returns:
        JSON: Lista de estudiantes con metadatos de paginación
    """
    try:
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        estudiantes, total = db_handler.get_all_estudiantes(limit, offset)
        
        return jsonify({
            'success': True,
            'total': total,
            'limit': limit,
            'offset': offset,
            'count': len(estudiantes),
            'estudiantes': estudiantes
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error en get_all_estudiantes: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500


@app.route('/api/estudiantes/bootcamp/<bootcamp_id>', methods=['GET'])
def get_estudiantes_by_bootcamp(bootcamp_id):
    """
    Filtra estudiantes por bootcamp_id.
    
    Path Parameters:
        bootcamp_id (str): Código del bootcamp a consultar
    
    Returns:
        JSON: Lista de estudiantes del bootcamp especificado
    """
    try:
        estudiantes = db_handler.get_estudiantes_by_bootcamp(bootcamp_id)
        
        return jsonify({
            'success': True,
            'bootcamp_id': bootcamp_id,
            'count': len(estudiantes),
            'estudiantes': estudiantes
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error en get_estudiantes_by_bootcamp: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500


@app.route('/api/estudiantes/phone/<phone>', methods=['GET'])
def get_estudiante_by_phone(phone):
    """
    Busca estudiantes por número de teléfono.
    
    Path Parameters:
        phone (str): Número de teléfono a buscar
    
    Returns:
        JSON: Registros del estudiante con ese teléfono
    """
    try:
        estudiantes = db_handler.get_estudiante_by_phone(phone)
        
        return jsonify({
            'success': True,
            'phone': phone,
            'count': len(estudiantes),
            'estudiantes': estudiantes
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error en get_estudiante_by_phone: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500


@app.route('/api/estudiantes/date-range', methods=['GET'])
def get_estudiantes_by_date():
    """
    Filtra estudiantes por rango de fechas de envío.
    
    Query Parameters:
        fecha_inicio (str): Fecha inicial en formato YYYY-MM-DD (opcional)
        fecha_fin (str): Fecha final en formato YYYY-MM-DD (opcional)
    
    Returns:
        JSON: Estudiantes filtrados por rango de fechas
    """
    try:
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        
        estudiantes = db_handler.get_estudiantes_by_date_range(fecha_inicio, fecha_fin)
        
        return jsonify({
            'success': True,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'count': len(estudiantes),
            'estudiantes': estudiantes
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error en get_estudiantes_by_date: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500


@app.route('/api/bootcamps', methods=['GET'])
def get_all_bootcamps():
    """
    Lista todos los bootcamps registrados.
    
    Este endpoint es útil para poblar dropdowns en el frontend
    con los códigos de bootcamp disponibles.
    
    Returns:
        JSON: Lista de bootcamps con sus códigos y nombres
    """
    try:
        bootcamps = db_handler.get_all_bootcamps()
        
        return jsonify({
            'success': True,
            'count': len(bootcamps),
            'bootcamps': bootcamps
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error en get_all_bootcamps: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500


@app.route('/api/estadisticas', methods=['GET'])
def get_estadisticas():
    """
    Obtiene estadísticas generales del sistema.
    
    Proporciona métricas sobre:
    - Total de estudiantes
    - Mensajes enviados/error
    - Respuestas confirmadas (Sí/No)
    - Pendientes de respuesta
    - Total de bootcamps
    - Tasa de respuesta
    
    Returns:
        JSON: Estadísticas completas del sistema
    """
    try:
        stats = db_handler.get_estadisticas()
        
        return jsonify({
            'success': True,
            'estadisticas': stats
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error en get_estadisticas: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500


# ============================================================================
# CRUD Endpoints - Editar, Eliminar, Vaciar
# ============================================================================

@app.route('/api/estudiantes/update-field', methods=['PUT'])
def update_estudiante_field():
    """
    Actualiza UN campo específico de un estudiante.
    
    Request Body:
        {
            "telefono": "+573001234567",
            "field": "nombre",
            "value": "Juan Pérez Actualizado"
        }
    
    Returns:
        JSON: Resultado de la actualización
    """
    try:
        data = request.get_json()
        
        telefono = data.get('telefono')
        field = data.get('field')
        value = data.get('value')
        
        if not telefono or not field:
            return jsonify({
                'success': False,
                'error': 'Campos requeridos: telefono, field, value'
            }), 400
        
        success, msg = db_handler.update_estudiante_field(telefono, field, value)
        
        return jsonify({
            'success': success,
            'message' if success else 'error': msg
        }), 200 if success else 400
        
    except Exception as e:
        app.logger.error(f"Error en update_estudiante_field: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500


@app.route('/api/estudiantes/update-fields', methods=['PUT'])
def update_estudiante_fields():
    """
    Actualiza MÚLTIPLES campos de un estudiante.
    
    Request Body:
        {
            "telefono": "+573001234567",
            "fields": {
                "nombre": "Juan Pérez",
                "modalidad": "Virtual",
                "horario": "Lunes a viernes 6pm-10pm"
            }
        }
    
    Returns:
        JSON: Resultado de la actualización
    """
    try:
        data = request.get_json()
        
        telefono = data.get('telefono')
        fields = data.get('fields')
        
        if not telefono or not fields:
            return jsonify({
                'success': False,
                'error': 'Campos requeridos: telefono, fields'
            }), 400
        
        success, msg = db_handler.update_estudiante_fields(telefono, fields)
        
        return jsonify({
            'success': success,
            'message' if success else 'error': msg
        }), 200 if success else 400
        
    except Exception as e:
        app.logger.error(f"Error en update_estudiante_fields: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500


@app.route('/api/estudiantes/delete/<phone>', methods=['DELETE'])
def delete_estudiante(phone):
    """
    Elimina un estudiante por su número de teléfono.
    
    Path Parameters:
        phone (str): Número de teléfono del estudiante
    
    Returns:
        JSON: Resultado de la eliminación
    """
    try:
        success, msg = db_handler.delete_estudiante(phone)
        
        return jsonify({
            'success': success,
            'message' if success else 'error': msg
        }), 200 if success else 404
        
    except Exception as e:
        app.logger.error(f"Error en delete_estudiante: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500


@app.route('/api/bootcamps/delete/<bootcamp_id>', methods=['DELETE'])
def delete_bootcamp(bootcamp_id):
    """
    Elimina un bootcamp del catálogo.
    
    Path Parameters:
        bootcamp_id (str): Código del bootcamp
    
    Returns:
        JSON: Resultado de la eliminación
    """
    try:
        success, msg = db_handler.delete_bootcamp(bootcamp_id)
        
        return jsonify({
            'success': success,
            'message' if success else 'error': msg
        }), 200 if success else 404
        
    except Exception as e:
        app.logger.error(f"Error en delete_bootcamp: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500


@app.route('/api/estudiantes/clear-all', methods=['DELETE'])
def clear_all_estudiantes():
    """
    ⚠️ PELIGRO: Elimina TODOS los estudiantes de la base de datos.
    
    Esta operación no se puede deshacer. Usar con precaución.
    
    Returns:
        JSON: Cantidad de registros eliminados
    """
    try:
        success, msg = db_handler.clear_all_estudiantes()
        
        return jsonify({
            'success': success,
            'message' if success else 'error': msg
        }), 200 if success else 500
        
    except Exception as e:
        app.logger.error(f"Error en clear_all_estudiantes: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500


@app.route('/api/bootcamps/clear-all', methods=['DELETE'])
def clear_all_bootcamps():
    """
    ⚠️ PELIGRO: Elimina TODOS los bootcamps de la base de datos.
    
    Esta operación no se puede deshacer. Usar con precaución.
    
    Returns:
        JSON: Cantidad de registros eliminados
    """
    try:
        success, msg = db_handler.clear_all_bootcamps()
        
        return jsonify({
            'success': success,
            'message' if success else 'error': msg
        }), 200 if success else 500
        
    except Exception as e:
        app.logger.error(f"Error en clear_all_bootcamps: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}'
        }), 500


@app.route('/api/database/reset', methods=['DELETE'])
def reset_database():
    """
    ⚠️ PELIGRO EXTREMO: Elimina TODO el contenido de la base de datos.
    
    Borra estudiantes Y bootcamps. Esta operación no se puede deshacer.
    
    Returns:
        JSON: Resultado del reseteo completo
    """
    try:
        success, msg = db_handler.reset_database()
        
        return jsonify({
            'success': success,
            'message' if success else 'error': msg
        }), 200 if success else 500
        
    except Exception as e:
        app.logger.error(f"Error en reset_database: {str(e)}")
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


# Configurar scheduler para sincronización automática con Drive
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

scheduler = BackgroundScheduler()
scheduler.add_job(
    func=sync_to_drive_if_needed,
    trigger="interval",
    minutes=5,
    id='sync_drive_job',
    name='Sincronización automática con Google Drive',
    replace_existing=True
)
scheduler.start()

# Asegurar que el scheduler se detenga al cerrar la app
atexit.register(lambda: scheduler.shutdown())

app.logger.info("⏰ Scheduler iniciado: sincronización automática cada 5 minutos")


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
    print("  🔄 Sync automático: Cada 5 minutos")
    print("\n" + "="*70 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
