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
from typing import Dict, Any, Tuple
import io
import requests
import pandas as pd

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
            "template_name": "prueba",
            "parameters": ["talentoTech", "Inteligencia Artificial", "Presencial"],
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

# ============================================================================
# Funciones auxiliares para Google Drive Integration
# ============================================================================

def _normalize_column_name(col_name: str) -> str:
    """
    Normaliza un nombre de columna eliminando acentos, espacios y caracteres especiales.
    
    Args:
        col_name: Nombre de columna original
        
    Returns:
        str: Nombre normalizado en minúsculas sin acentos ni caracteres especiales
    """
    import unicodedata
    normalized = ''.join(
        c for c in unicodedata.normalize('NFD', col_name.lower())
        if unicodedata.category(c) != 'Mn'
    )
    return normalized.replace(' ', '').replace('_', '').replace('-', '')


def _get_drive_file_metadata(file_id: str, access_token: str) -> Tuple[bool, Dict[str, Any], str]:
    """
    Obtiene los metadatos de un archivo de Google Drive.
    
    Args:
        file_id: ID del archivo en Google Drive
        access_token: Token de autenticación OAuth
        
    Returns:
        Tuple[bool, Dict, str]: (éxito, metadata, mensaje_error)
    """
    metadata_url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }
    params = {
        'fields': 'id,name,mimeType,size',
        'supportsAllDrives': 'true'
    }
    
    try:
        response = requests.get(metadata_url, headers=headers, params=params, timeout=20)
        
        if response.status_code == 401:
            return False, {}, 'Token inválido o expirado'
        elif response.status_code == 403:
            return False, {}, 'Sin permisos para acceder al archivo'
        elif response.status_code == 404:
            return False, {}, 'Archivo no encontrado'
        elif response.status_code != 200:
            return False, {}, f'Error obteniendo metadata (código {response.status_code})'
        
        return True, response.json(), ''
        
    except requests.exceptions.Timeout:
        return False, {}, 'Timeout al conectar con Google Drive'
    except requests.exceptions.ConnectionError:
        return False, {}, 'Error de conexión con Google Drive'
    except Exception as e:
        return False, {}, f'Error inesperado: {str(e)}'


def _download_drive_file_content(file_id: str, access_token: str, 
                                  is_google_sheet: bool) -> Tuple[bool, bytes, str]:
    """
    Descarga el contenido de un archivo de Google Drive.
    
    Args:
        file_id: ID del archivo
        access_token: Token OAuth
        is_google_sheet: Si es una hoja de cálculo de Google
        
    Returns:
        Tuple[bool, bytes, str]: (éxito, contenido, mensaje_error)
    """
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }
    
    try:
        if is_google_sheet:
            # Exportar Google Sheet como CSV
            export_url = f"https://www.googleapis.com/drive/v3/files/{file_id}/export"
            params = {'mimeType': 'text/csv', 'supportsAllDrives': 'true'}
            response = requests.get(export_url, headers=headers, params=params, timeout=30)
            
            if response.status_code != 200:
                return False, b'', f'Error exportando Google Sheet: {response.status_code}'
            
            app.logger.info("✅ Sheet exportado a CSV")
            return True, response.content, ''
            
        else:
            # Descargar archivo binario (CSV o XLSX)
            download_url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
            params = {'alt': 'media', 'supportsAllDrives': 'true'}
            response = requests.get(download_url, headers=headers, params=params, timeout=30)
            
            if response.status_code != 200:
                return False, b'', 'Error descargando archivo'
            
            app.logger.info(f"✅ Archivo descargado ({len(response.content)} bytes)")
            return True, response.content, ''
            
    except requests.exceptions.Timeout:
        return False, b'', 'Timeout descargando archivo'
    except Exception as e:
        return False, b'', f'Error descargando: {str(e)}'


def _parse_file_content(content: bytes) -> Tuple[bool, pd.DataFrame, str]:
    """
    Parsea el contenido de un archivo a DataFrame de pandas.
    
    Args:
        content: Contenido binario del archivo
        
    Returns:
        Tuple[bool, DataFrame, str]: (éxito, dataframe, mensaje_error)
    """
    if not content:
        return False, None, 'Archivo vacío'
    
    try:
        # Intentar como CSV primero
        text = content.decode('utf-8')
        df = pd.read_csv(io.StringIO(text), dtype=str)
        app.logger.info(f"✅ Parseado como CSV ({len(df)} filas)")
        return True, df, ''
        
    except Exception:
        try:
            # Intentar como XLSX
            df = pd.read_excel(io.BytesIO(content), engine='openpyxl', dtype=str)
            app.logger.info(f"✅ Parseado como XLSX ({len(df)} filas)")
            return True, df, ''
            
        except Exception as e:
            app.logger.error(f"Error parseando archivo: {str(e)}")
            return False, None, 'No se pudo leer el archivo'


def _normalize_phone_column(df: pd.DataFrame) -> Tuple[bool, pd.DataFrame, str]:
    """
    Normaliza y mapea la columna de teléfono a 'telefono_e164'.
    
    Args:
        df: DataFrame original
        
    Returns:
        Tuple[bool, DataFrame, str]: (éxito, dataframe_modificado, mensaje_error)
    """
    app.logger.info(f"📊 Columnas detectadas: {', '.join(df.columns.tolist())}")
    
    # Si ya existe telefono_e164, no hacer nada
    if 'telefono_e164' in df.columns:
        return True, df, ''
    
    # Crear mapeo de columnas normalizadas
    normalized_cols = {_normalize_column_name(c): c for c in df.columns}
    
    # Variantes posibles de columna de teléfono
    phone_variants = [
        'telefono', 'telefonocelular', 'telefonoe164', 
        'phone', 'phonenumber', 'celular', 'cel',
        'telefonodelestudiante', 'telefonoestudiante',
        'movil', 'whatsapp', 'contacto'
    ]
    
    # Buscar coincidencia
    for variant in phone_variants:
        if variant in normalized_cols:
            original_col = normalized_cols[variant]
            df = df.rename(columns={original_col: 'telefono_e164'})
            app.logger.info(f"🔄 Columna '{original_col}' mapeada a 'telefono_e164'")
            return True, df, ''
    
    # No se encontró columna de teléfono
    cols = ', '.join(df.columns.tolist())
    return False, df, f'Columna de teléfono no encontrada. Disponibles: {cols}'


def _clean_phone_numbers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia y normaliza los números de teléfono.
    
    Args:
        df: DataFrame con columna telefono_e164
        
    Returns:
        DataFrame: DataFrame con teléfonos normalizados
    """
    df['telefono_e164'] = (df['telefono_e164']
        .astype(str)
        .str.strip()
        .str.replace(' ', '', regex=False)
        .str.replace('-', '', regex=False)
        .str.replace('(', '', regex=False)
        .str.replace(')', '', regex=False)
        .str.replace('+', '', regex=False)
    )
    return df


def _add_tracking_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Añade columnas de tracking al DataFrame si no existen.
    
    Args:
        df: DataFrame original
        
    Returns:
        DataFrame: DataFrame con columnas de tracking
    """
    tracking_cols = [
        'estado_envio_simple', 'fecha_envio_simple', 'message_id_simple',
        'respuesta', 'fecha_respuesta', 'respuesta_id'
    ]
    
    for col in tracking_cols:
        if col not in df.columns:
            df[col] = ''
    
    app.logger.info("✅ Columnas de tracking añadidas")
    return df


def _update_google_sheet(spreadsheet_id: str, access_token: str, 
                         df: pd.DataFrame) -> Tuple[bool, str]:
    """
    Actualiza un Google Sheet con el DataFrame procesado.
    Usa el método batchUpdate para garantizar que todas las columnas se escriban.
    
    Args:
        spreadsheet_id: ID del spreadsheet
        access_token: Token OAuth
        df: DataFrame con los datos actualizados
        
    Returns:
        Tuple[bool, str]: (éxito, mensaje)
    """
    try:
        app.logger.info("🔄 Actualizando Google Sheet...")
        app.logger.info(f"📊 DataFrame: {len(df)} filas x {len(df.columns)} columnas")
        app.logger.info(f"📋 Columnas: {', '.join(df.columns.tolist())}")
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Preparar datos: headers + valores
        headers_list = df.columns.tolist()
        values_list = [headers_list] + df.fillna('').values.tolist()
        
        app.logger.info(f"✍️ Preparando {len(values_list)} filas (incluyendo headers)")
        
        # Paso 1: Limpiar TODO el contenido del Sheet
        clear_url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/Sheet1!A:ZZ"
        clear_body = {}
        
        clear_resp = requests.delete(
            clear_url,
            headers=headers,
            timeout=20
        )
        
        # Si el clear falla, intentar con el método alternativo
        if clear_resp.status_code != 200:
            app.logger.warning(f"⚠️ Clear con DELETE falló: {clear_resp.status_code}, intentando con POST")
            clear_url_alt = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/Sheet1!A1:ZZ:clear"
            clear_resp = requests.post(clear_url_alt, headers=headers, timeout=20)
        
        if clear_resp.status_code == 200:
            app.logger.info("✅ Sheet limpiado completamente")
        else:
            app.logger.warning(f"⚠️ No se pudo limpiar el sheet: {clear_resp.status_code}")
        
        # Paso 2: Escribir TODOS los datos desde A1 usando batchUpdate
        batch_url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values:batchUpdate"
        
        batch_body = {
            'valueInputOption': 'RAW',
            'data': [{
                'range': 'Sheet1!A1',
                'values': values_list
            }]
        }
        
        app.logger.info(f"📤 Enviando {len(headers_list)} columnas a Google Sheets...")
        
        batch_resp = requests.post(
            batch_url,
            headers=headers,
            json=batch_body,
            timeout=30
        )
        
        if batch_resp.status_code == 200:
            result = batch_resp.json()
            total_updated = result.get('totalUpdatedRows', 0)
            total_cols = result.get('totalUpdatedColumns', 0)
            app.logger.info(f"✅ Google Sheet actualizado exitosamente!")
            app.logger.info(f"   📊 {total_updated} filas x {total_cols} columnas")
            app.logger.info(f"   📋 Columnas escritas: {len(headers_list)}")
            return True, f"Sheet actualizado: {total_updated} filas, {len(headers_list)} columnas"
        else:
            error_text = batch_resp.text
            app.logger.error(f"❌ Error en batchUpdate: {batch_resp.status_code}")
            app.logger.error(f"   Respuesta: {error_text}")
            return False, f"Error actualizando Sheet: {batch_resp.status_code}"
            
    except Exception as e:
        app.logger.error(f"❌ Error con Sheets API: {str(e)}")
        import traceback
        app.logger.error(traceback.format_exc())
        return False, f"Error de conexión: {str(e)}"


def _update_csv_file(file_id: str, access_token: str, df: pd.DataFrame) -> Tuple[bool, str]:
    """
    Actualiza un archivo CSV en Google Drive.
    
    Args:
        file_id: ID del archivo
        access_token: Token OAuth
        df: DataFrame a subir
        
    Returns:
        Tuple[bool, str]: (éxito, mensaje)
    """
    try:
        app.logger.info("🔄 Actualizando archivo CSV en Drive...")
        
        # Convertir DataFrame a CSV
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_content = csv_buffer.getvalue().encode('utf-8')
        
        # Actualizar archivo
        update_url = f"https://www.googleapis.com/upload/drive/v3/files/{file_id}"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'text/csv'
        }
        params = {
            'uploadType': 'media',
            'supportsAllDrives': 'true'
        }
        
        response = requests.patch(
            update_url,
            headers=headers,
            params=params,
            data=csv_content,
            timeout=30
        )
        
        if response.status_code == 200:
            app.logger.info("✅ Archivo CSV actualizado en Drive")
            return True, "CSV actualizado correctamente"
        else:
            app.logger.warning(f"⚠️ Error: {response.status_code}")
            return False, f"No se pudo actualizar: {response.status_code}"
            
    except Exception as e:
        app.logger.warning(f"⚠️ Error: {str(e)}")
        return False, f"Error al actualizar: {str(e)}"


def _update_xlsx_file(file_id: str, access_token: str, df: pd.DataFrame) -> Tuple[bool, str]:
    """
    Actualiza un archivo XLSX en Google Drive.
    
    Args:
        file_id: ID del archivo en Drive
        access_token: Token OAuth
        df: DataFrame con los datos actualizados
        
    Returns:
        Tuple[bool, str]: (éxito, mensaje)
    """
    try:
        app.logger.info("🔄 Actualizando archivo XLSX en Drive...")
        
        # Crear archivo Excel en memoria
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
        output.seek(0)
        
        # Actualizar en Drive
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
        
        update_url = f"https://www.googleapis.com/upload/drive/v3/files/{file_id}"
        params = {
            'uploadType': 'media',
            'supportsAllDrives': 'true'
        }
        
        response = requests.patch(
            update_url,
            headers=headers,
            params=params,
            data=output.getvalue(),
            timeout=30
        )
        
        if response.status_code == 200:
            app.logger.info(f"✅ Archivo XLSX actualizado: {len(df)} filas, {len(df.columns)} columnas")
            return True, f"XLSX actualizado con {len(df)} filas y {len(df.columns)} columnas"
        else:
            app.logger.error(f"❌ Error actualizando XLSX: {response.status_code} - {response.text}")
            return False, f"Error al actualizar XLSX: {response.status_code}"
            
    except Exception as e:
        app.logger.error(f"❌ Error actualizando XLSX: {str(e)}")
        import traceback
        app.logger.error(traceback.format_exc())
        return False, f"Error de actualización: {str(e)}"


# ============================================================================
# Endpoint principal de Google Drive
# ============================================================================

@app.route('/api/google/upload', methods=['POST'])
def upload_from_google():
    """
    Procesa un archivo de Google Drive: descarga, normaliza, actualiza CSV local y Drive.
    
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
        
        app.logger.info(f"📥 Procesando archivo de Google Drive: {file_id}")
        
        # 1. Obtener metadata
        success, metadata, error = _get_drive_file_metadata(file_id, access_token)
        if not success:
            return jsonify({'success': False, 'error': error}), 400
        
        mime_type = metadata.get('mimeType', '')
        file_name = metadata.get('name', file_id)
        is_google_sheet = mime_type == 'application/vnd.google-apps.spreadsheet'
        
        app.logger.info(f"📄 Archivo: {file_name} | Tipo: {mime_type}")
        
        # Validar tipo de archivo
        supported_types = [
            'application/vnd.google-apps.spreadsheet',
            'text/csv',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ]
        
        if mime_type not in supported_types and not file_name.lower().endswith(('.csv', '.xlsx')):
            return jsonify({'success': False, 'error': f'Tipo no soportado: {mime_type}'}), 400
        
        # 2. Descargar contenido
        success, content, error = _download_drive_file_content(
            file_id, access_token, is_google_sheet
        )
        if not success:
            return jsonify({'success': False, 'error': error}), 400
        
        # 3. Parsear a DataFrame
        success, df, error = _parse_file_content(content)
        if not success:
            return jsonify({'success': False, 'error': error}), 400
        
        if df.empty:
            return jsonify({'success': False, 'error': 'El archivo no contiene datos'}), 400
        
        # 4. Normalizar columna de teléfono
        success, df, error = _normalize_phone_column(df)
        if not success:
            return jsonify({'success': False, 'error': error}), 400
        
        # 5. Limpiar números de teléfono
        df = _clean_phone_numbers(df)
        
        # 6. Añadir columnas de tracking
        df = _add_tracking_columns(df)
        
        # 7. Guardar localmente (sobreescribir bd_envio.csv)
        ok, save_msg = csv_handler.save_csv(df)
        if not ok:
            app.logger.error(f"❌ Error guardando CSV: {save_msg}")
            return jsonify({'success': False, 'error': f'No se pudo guardar CSV: {save_msg}'}), 500
        
        app.logger.info(f"✅ bd_envio.csv sobreescrito con {len(df)} registros")
        
        # 8. Actualizar archivo en Drive
        update_success = False
        update_message = ""
        
        if is_google_sheet:
            update_success, update_message = _update_google_sheet(file_id, access_token, df)
        elif mime_type == 'text/csv':
            update_success, update_message = _update_csv_file(file_id, access_token, df)
        elif mime_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' or file_name.lower().endswith('.xlsx'):
            update_success, update_message = _update_xlsx_file(file_id, access_token, df)
        else:
            app.logger.info(f"ℹ️ Tipo de archivo no soportado para actualización: {mime_type}")
            update_message = f"Tipo de archivo {mime_type} no se actualiza en Drive"
        
        # 9. Preparar respuesta
        csv_output = io.StringIO()
        df.to_csv(csv_output, index=False)
        
        response_data = {
            'success': True,
            'message': 'Archivo procesado y sincronizado',
            'file_name': file_name,
            'mimeType': mime_type,
            'total_rows': len(df),
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
