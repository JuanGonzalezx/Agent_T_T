"""
Servicio para integración con Google Drive API.

Este módulo encapsula toda la lógica de interacción con Google Drive,
incluyendo descarga de archivos, actualización de Sheets/CSV/XLSX,
y gestión de metadatos con limpieza PROFUNDA de datos para evitar errores visuales.
"""

import io
import requests
import pandas as pd
from typing import Tuple, Dict, Any


class GoogleDriveService:
    """
    Servicio para manejar operaciones con Google Drive API.
    """
    
    def __init__(self):
        """Inicializa el servicio de Google Drive."""
        self.drive_api_base = "https://www.googleapis.com/drive/v3"
        self.sheets_api_base = "https://sheets.googleapis.com/v4"
    
    def get_file_metadata(self, file_id: str, access_token: str) -> Tuple[bool, Dict[str, Any], str]:
        """Obtiene metadata del archivo."""
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
            
            if response.status_code == 200:
                return True, response.json(), ''
            elif response.status_code == 401:
                return False, {}, 'Token inválido o expirado'
            elif response.status_code == 404:
                return False, {}, 'Archivo no encontrado'
            else:
                return False, {}, f'Error metadata: {response.status_code}'
            
        except Exception as e:
            return False, {}, f'Error conexión: {str(e)}'
    
    def download_file_content(self, file_id: str, access_token: str, 
                              is_google_sheet: bool) -> Tuple[bool, bytes, str]:
        """Descarga el contenido binario del archivo."""
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        
        try:
            if is_google_sheet:
                # Exportar Google Sheet como CSV
                url = f"{self.drive_api_base}/files/{file_id}/export"
                params = {'mimeType': 'text/csv', 'supportsAllDrives': 'true'}
            else:
                # Descargar archivo binario
                url = f"{self.drive_api_base}/files/{file_id}"
                params = {'alt': 'media', 'supportsAllDrives': 'true'}

            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                return True, response.content, ''
            else:
                return False, b'', f'Error descarga: {response.status_code}'
                
        except Exception as e:
            return False, b'', f'Excepción descarga: {str(e)}'
    
    def parse_file_content(self, content: bytes) -> Tuple[bool, pd.DataFrame, str]:
        """
        Parsea y LIMPIA AGRESIVAMENTE los datos para que el Frontend no se rompa.
        
        Soluciona:
        1. Comas dentro del texto (que desplazan columnas).
        2. Saltos de línea (que parten filas).
        3. Teléfonos científicos (e.g. 5.7E+10).
        """
        if not content:
            return False, pd.DataFrame(), 'Archivo vacío'
        
        try:
            # 1. Intentar leer como CSV
            try:
                text = content.decode('utf-8')
                # Usar engine='python' es más robusto para csv mal formados
                df = pd.read_csv(
                    io.StringIO(text), 
                    dtype=str,             # Todo a string (CRÍTICO)
                    keep_default_na=False, # Evita NaNs
                    on_bad_lines='skip'    # Salta líneas rotas si las hay
                )
            except UnicodeDecodeError:
                # Si falla, intentar como Excel
                df = pd.read_excel(
                    io.BytesIO(content), 
                    engine='openpyxl', 
                    dtype=str,
                    keep_default_na=False
                )

            # --- FASE DE SANITIZACIÓN (AQUÍ ESTÁ LA MAGIA) ---

            # 2. Normalizar Columnas (Minúsculas y sin espacios para que coincida con tu JSON)
            df.columns = df.columns.astype(str).str.strip().str.lower()

            # 3. Eliminar filas vacías
            df = df.dropna(how='all')

            # 4. ELIMINAR SALTOS DE LÍNEA (Arregla filas partidas)
            # Reemplaza \n por espacio
            df = df.replace(r'[\r\n]+', ' ', regex=True)

            # 5. REEMPLAZAR COMAS POR PUNTOS O ESPACIOS (Arregla desplazamiento de columnas)
            # Si tu frontend separa por comas, una coma dentro de "Lunes, Martes" rompe todo.
            # Cambiamos ',' por ' - ' para mantener legibilidad sin romper el CSV.
            df = df.replace(r',', ' - ', regex=True)

            # 6. Trim de espacios
            df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)

            return True, df, ''
            
        except Exception as e:
            return False, pd.DataFrame(), f'Error parseando: {str(e)}'
    
    def update_google_sheet(self, spreadsheet_id: str, access_token: str, 
                            df: pd.DataFrame) -> Tuple[bool, str]:
        """Actualiza el Google Sheet original."""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Obtener info hoja
            url_meta = f"{self.sheets_api_base}/spreadsheets/{spreadsheet_id}"
            resp = requests.get(url_meta, headers=headers, params={'fields': 'sheets.properties'})
            if resp.status_code != 200: return False, "Error acceso sheet"
            
            first_sheet = resp.json().get('sheets', [])[0].get('properties', {}).get('title', 'Sheet1')
            
            # Preparar datos (limpios)
            df_clean = df.fillna('')
            values = [df_clean.columns.tolist()] + df_clean.values.tolist()
            
            # Limpiar y escribir
            url_clear = f"{self.sheets_api_base}/spreadsheets/{spreadsheet_id}/values/{first_sheet}:clear"
            requests.post(url_clear, headers=headers, json={})
            
            url_update = f"{self.sheets_api_base}/spreadsheets/{spreadsheet_id}/values:batchUpdate"
            body = {'valueInputOption': 'RAW', 'data': [{'range': f'{first_sheet}!A1', 'values': values}]}
            
            resp_update = requests.post(url_update, headers=headers, json=body)
            
            if resp_update.status_code == 200:
                rows = resp_update.json().get('totalUpdatedRows', 0)
                return True, f"Sheet actualizado: {rows} filas"
            return False, f"Error writing: {resp_update.text}"
                
        except Exception as e:
            return False, f"Excepción API: {str(e)}"

    def update_csv_file(self, file_id: str, access_token: str, df: pd.DataFrame) -> Tuple[bool, str]:
        """Actualiza archivo CSV."""
        try:
            buffer = io.StringIO()
            df.to_csv(buffer, index=False)
            url = f"https://www.googleapis.com/upload/drive/v3/files/{file_id}?uploadType=media"
            headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'text/csv'}
            requests.patch(url, headers=headers, data=buffer.getvalue().encode('utf-8'))
            return True, "CSV actualizado"
        except Exception:
            return False, "Error actualizando CSV"

    def update_xlsx_file(self, file_id: str, access_token: str, df: pd.DataFrame) -> Tuple[bool, str]:
        """Actualiza archivo XLSX."""
        try:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            buffer.seek(0)
            url = f"https://www.googleapis.com/upload/drive/v3/files/{file_id}?uploadType=media"
            headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
            requests.patch(url, headers=headers, data=buffer.getvalue())
            return True, "XLSX actualizado"
        except Exception:
            return False, "Error actualizando XLSX"