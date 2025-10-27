"""
Servicio para integración con Google Drive API.

Este módulo encapsula toda la lógica de interacción con Google Drive,
incluyendo descarga de archivos, actualización de Sheets/CSV/XLSX,
y gestión de metadatos.
"""

import io
import requests
import pandas as pd
from typing import Tuple, Dict, Any


class GoogleDriveService:
    """
    Servicio para manejar operaciones con Google Drive API.
    
    Soporta:
    - Google Sheets (exportación como CSV y actualización vía Sheets API)
    - Archivos CSV en Drive (descarga y actualización)
    - Archivos XLSX en Drive (descarga y actualización)
    """
    
    def __init__(self):
        """Inicializa el servicio de Google Drive."""
        self.drive_api_base = "https://www.googleapis.com/drive/v3"
        self.sheets_api_base = "https://sheets.googleapis.com/v4"
    
    def get_file_metadata(self, file_id: str, access_token: str) -> Tuple[bool, Dict[str, Any], str]:
        """
        Obtiene los metadatos de un archivo de Google Drive.
        
        Args:
            file_id: ID del archivo en Google Drive
            access_token: Token de autenticación OAuth
            
        Returns:
            Tuple[bool, Dict, str]: (éxito, metadata, mensaje_error)
        """
        metadata_url = f"{self.drive_api_base}/files/{file_id}"
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
    
    def download_file_content(self, file_id: str, access_token: str, 
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
                export_url = f"{self.drive_api_base}/files/{file_id}/export"
                params = {'mimeType': 'text/csv', 'supportsAllDrives': 'true'}
                response = requests.get(export_url, headers=headers, params=params, timeout=30)
                
                if response.status_code != 200:
                    return False, b'', f'Error exportando Google Sheet: {response.status_code}'
                
                return True, response.content, ''
                
            else:
                # Descargar archivo binario (CSV o XLSX)
                download_url = f"{self.drive_api_base}/files/{file_id}"
                params = {'alt': 'media', 'supportsAllDrives': 'true'}
                response = requests.get(download_url, headers=headers, params=params, timeout=30)
                
                if response.status_code != 200:
                    return False, b'', 'Error descargando archivo'
                
                return True, response.content, ''
                
        except requests.exceptions.Timeout:
            return False, b'', 'Timeout descargando archivo'
        except Exception as e:
            return False, b'', f'Error descargando: {str(e)}'
    
    def parse_file_content(self, content: bytes) -> Tuple[bool, pd.DataFrame, str]:
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
            return True, df, ''
            
        except Exception:
            try:
                # Intentar como XLSX
                df = pd.read_excel(io.BytesIO(content), engine='openpyxl', dtype=str)
                return True, df, ''
                
            except Exception as e:
                return False, None, 'No se pudo leer el archivo'
    
    def update_google_sheet(self, spreadsheet_id: str, access_token: str, 
                           df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Actualiza un Google Sheet con el DataFrame procesado.
        Obtiene dinámicamente el nombre de la primera hoja y actualiza todos los datos.
        
        Args:
            spreadsheet_id: ID del spreadsheet (mismo que file_id de Drive para Sheets)
            access_token: Token OAuth
            df: DataFrame con los datos actualizados
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Paso 0: Obtener el nombre de la primera hoja del spreadsheet
            sheet_url = f"{self.sheets_api_base}/spreadsheets/{spreadsheet_id}"
            sheet_resp = requests.get(sheet_url, headers=headers, params={'fields': 'sheets.properties'}, timeout=20)
            
            if sheet_resp.status_code != 200:
                return False, f"No se pudo acceder al spreadsheet: {sheet_resp.status_code}"
            
            sheet_info = sheet_resp.json()
            sheets = sheet_info.get('sheets', [])
            
            if not sheets:
                return False, "El spreadsheet no contiene hojas"
            
            # Obtener el nombre de la primera hoja
            first_sheet_name = sheets[0].get('properties', {}).get('title', 'Sheet1')
            
            # Preparar datos: headers + valores
            headers_list = df.columns.tolist()
            values_list = [headers_list] + df.fillna('').values.tolist()
            
            # Paso 1: Limpiar TODO el contenido de la hoja
            clear_url = f"{self.sheets_api_base}/spreadsheets/{spreadsheet_id}/values/{first_sheet_name}:clear"
            
            clear_resp = requests.post(
                clear_url,
                headers=headers,
                json={},
                timeout=20
            )
            
            if clear_resp.status_code != 200:
                return False, f"Error limpiando hoja: {clear_resp.status_code}"
            
            # Paso 2: Escribir TODOS los datos desde A1 usando batchUpdate
            batch_url = f"{self.sheets_api_base}/spreadsheets/{spreadsheet_id}/values:batchUpdate"
            
            batch_body = {
                'valueInputOption': 'RAW',
                'data': [{
                    'range': f'{first_sheet_name}!A1',
                    'values': values_list
                }]
            }
            
            batch_resp = requests.post(
                batch_url,
                headers=headers,
                json=batch_body,
                timeout=30
            )
            
            if batch_resp.status_code == 200:
                result = batch_resp.json()
                total_updated = result.get('totalUpdatedRows', 0)
                return True, f"Sheet '{first_sheet_name}' actualizado: {total_updated} filas, {len(headers_list)} columnas"
            else:
                error_text = batch_resp.text
                return False, f"Error actualizando Sheet: {batch_resp.status_code}"
                
        except Exception as e:
            return False, f"Error de conexión: {str(e)}"
    
    def update_csv_file(self, file_id: str, access_token: str, df: pd.DataFrame) -> Tuple[bool, str]:
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
                return True, "CSV actualizado correctamente"
            else:
                return False, f"No se pudo actualizar: {response.status_code}"
                
        except Exception as e:
            return False, f"Error al actualizar: {str(e)}"
    
    def update_xlsx_file(self, file_id: str, access_token: str, df: pd.DataFrame) -> Tuple[bool, str]:
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
                return True, f"XLSX actualizado con {len(df)} filas y {len(df.columns)} columnas"
            else:
                return False, f"Error al actualizar XLSX: {response.status_code}"
                
        except Exception as e:
            return False, f"Error de actualización: {str(e)}"
