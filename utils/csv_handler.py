"""
Módulo para el manejo de operaciones con archivos CSV.

Este módulo centraliza todas las operaciones relacionadas con la lectura,
escritura y actualización del archivo CSV de contactos, permitiendo un
manejo consistente y reutilizable de los datos.
"""

import pandas as pd
from datetime import datetime
from typing import Tuple, List, Dict, Any, Optional


class CSVHandler:
    """
    Gestor de operaciones CSV para el sistema de mensajería WhatsApp.
    
    Esta clase encapsula todas las operaciones necesarias para trabajar
    con el archivo CSV de contactos, evitando duplicación de código y
    asegurando consistencia en el manejo de datos.
    """
    
    def __init__(self, csv_path: str):
        """
        Inicializa el manejador de CSV.
        
        Args:
            csv_path: Ruta al archivo CSV de contactos
        """
        self.csv_path = csv_path
        self._required_columns = ['telefono_e164']
        self._tracking_columns = ['estado_envio_simple', 'fecha_envio_simple', 'message_id_simple']
    
    def load_csv(self) -> Tuple[bool, pd.DataFrame, str]:
        """
        Carga el archivo CSV y valida su estructura.
        
        La validación asegura que el archivo tenga las columnas mínimas
        necesarias para funcionar correctamente.
        
        Returns:
            Tuple[bool, pd.DataFrame, str]: (éxito, dataframe, mensaje)
        """
        try:
            df = pd.read_csv(self.csv_path, dtype=str)
            
            # Validar que existan las columnas requeridas
            missing_cols = [col for col in self._required_columns if col not in df.columns]
            if missing_cols:
                return False, None, f"Columnas faltantes: {', '.join(missing_cols)}"
            
            # Crear columnas de seguimiento si no existen
            # Esto permite trabajar con CSVs nuevos sin preparación previa
            for col in self._tracking_columns:
                if col not in df.columns:
                    df[col] = ''
            
            return True, df, f"CSV cargado exitosamente: {len(df)} registros"
            
        except FileNotFoundError:
            return False, None, f"Archivo no encontrado: {self.csv_path}"
        except Exception as e:
            return False, None, f"Error al cargar CSV: {str(e)}"
    
    def save_csv(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Guarda el dataframe en el archivo CSV.
        
        Args:
            df: DataFrame a guardar
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            df.to_csv(self.csv_path, index=False)
            return True, "CSV guardado exitosamente"
        except Exception as e:
            return False, f"Error al guardar CSV: {str(e)}"
    
    def create_backup(self, df: pd.DataFrame) -> Tuple[bool, str, str]:
        """
        Crea una copia de seguridad del CSV con timestamp.
        
        Los backups permiten recuperar el estado anterior en caso de
        errores durante el envío de mensajes o problemas de datos.
        
        Args:
            df: DataFrame a respaldar
            
        Returns:
            Tuple[bool, str, str]: (éxito, ruta_backup, mensaje)
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = self.csv_path.replace('.csv', f'_backup_{timestamp}.csv')
            df.to_csv(backup_path, index=False)
            return True, backup_path, f"Backup creado: {backup_path}"
        except Exception as e:
            return False, '', f"Error al crear backup: {str(e)}"
    
    def get_pending_contacts(self, df: pd.DataFrame) -> List[Tuple[int, pd.Series]]:
        """
        Filtra los contactos pendientes de envío.
        
        Un contacto está pendiente si:
        1. Tiene opt_in=TRUE (si la columna existe)
        2. No ha sido enviado anteriormente (estado_envio_simple != 'sent')
        
        Este filtrado evita reenvíos no deseados y respeta las preferencias
        de comunicación de los usuarios.
        
        Args:
            df: DataFrame con los contactos
            
        Returns:
            List[Tuple[int, pd.Series]]: Lista de tuplas (índice, fila)
        """
        pending = []
        
        for idx, row in df.iterrows():
            # Validar opt_in si la columna existe
            # Esto respeta las preferencias GDPR y de privacidad
            if 'opt_in' in df.columns:
                opt_in = str(row.get('opt_in', '')).strip().upper()
                if opt_in not in ('TRUE', '1', 'YES', 'SI', 'SÍ'):
                    continue
            
            # Evitar reenvíos a contactos ya procesados
            # Esto previene spam y duplicación de mensajes
            estado = str(row.get('estado_envio_simple', '')).strip().lower()
            if estado == 'sent':
                continue
            
            pending.append((idx, row))
        
        return pending
    
    def update_send_status(
        self, 
        df: pd.DataFrame, 
        idx: int, 
        success: bool, 
        result: str
    ) -> pd.DataFrame:
        """
        Actualiza el estado de envío de un contacto.
        
        El registro de estado permite trazabilidad completa de cada
        mensaje enviado y facilita la resolución de problemas.
        
        Args:
            df: DataFrame a actualizar
            idx: Índice del registro a actualizar
            success: Si el envío fue exitoso
            result: ID del mensaje (si éxito) o mensaje de error
            
        Returns:
            pd.DataFrame: DataFrame actualizado
        """
        if success:
            df.at[idx, 'estado_envio_simple'] = 'sent'
            df.at[idx, 'message_id_simple'] = result
        else:
            df.at[idx, 'estado_envio_simple'] = 'error'
        
        # El timestamp permite auditoría y análisis temporal de envíos
        df.at[idx, 'fecha_envio_simple'] = datetime.now().isoformat()
        
        return df
    
    def get_contact_info(self, row: pd.Series) -> Dict[str, Any]:
        """
        Extrae información relevante de un contacto.
        
        Args:
            row: Fila del DataFrame
            
        Returns:
            Dict[str, Any]: Diccionario con la información del contacto
        """
        return {
            'telefono': row.get('telefono_e164', ''),
            'nombre': row.get('nombre', 'Usuario'),
            'bootcamp': row.get('bootcamp', ''),
            'modalidad': row.get('modalidad', ''),
            'horario': row.get('horario', ''),
            'lugar': row.get('lugar', '')
        }
    
    def get_statistics(self, df: pd.DataFrame) -> Dict[str, int]:
        """
        Calcula estadísticas sobre el estado de los envíos.
        
        Las métricas ayudan a monitorear la efectividad del sistema
        y detectar problemas de manera temprana.
        
        Args:
            df: DataFrame con los datos
            
        Returns:
            Dict[str, int]: Diccionario con estadísticas
        """
        total = len(df)
        sent = len(df[df['estado_envio_simple'] == 'sent'])
        errors = len(df[df['estado_envio_simple'] == 'error'])
        pending = total - sent - errors
        
        return {
            'total': total,
            'sent': sent,
            'errors': errors,
            'pending': pending
        }
    
    def find_contact_by_phone(self, df: pd.DataFrame, phone: str) -> Optional[int]:
        """
        Busca un contacto por número de teléfono.
        
        Args:
            df: DataFrame con los contactos
            phone: Número de teléfono a buscar (normalizado o con +)
            
        Returns:
            Optional[int]: Índice del contacto encontrado o None
        """
        # Normalizar el teléfono de búsqueda
        phone_normalized = phone.strip().replace('+', '').replace(' ', '').replace('-', '')
        
        # Buscar en el DataFrame
        for idx, row in df.iterrows():
            phone_in_csv = str(row.get('telefono_e164', '')).strip().replace('+', '').replace(' ', '').replace('-', '')
            if phone_in_csv == phone_normalized:
                return idx
        
        return None
    
    def update_response(
        self,
        df: pd.DataFrame,
        phone: str,
        response_text: str,
        button_id: str = None
    ) -> Tuple[bool, pd.DataFrame, str]:
        """
        Actualiza la respuesta del usuario en el CSV.
        
        Este método registra cuando un usuario responde a un mensaje,
        permitiendo trazabilidad completa de la interacción.
        
        Args:
            df: DataFrame a actualizar
            phone: Número de teléfono del usuario
            response_text: Texto de la respuesta
            button_id: ID del botón presionado (si aplica)
            
        Returns:
            Tuple[bool, pd.DataFrame, str]: (éxito, dataframe_actualizado, mensaje)
        """
        # Crear columnas de respuesta si no existen
        # Esto permite trabajar con CSVs que no tienen estas columnas
        response_columns = ['respuesta', 'fecha_respuesta', 'respuesta_id']
        for col in response_columns:
            if col not in df.columns:
                df[col] = ''
        
        # Buscar el contacto por teléfono
        idx = self.find_contact_by_phone(df, phone)
        
        if idx is None:
            return False, df, f"Contacto no encontrado: {phone}"
        
        # Actualizar la respuesta
        df.at[idx, 'respuesta'] = response_text
        df.at[idx, 'fecha_respuesta'] = datetime.now().isoformat()
        if button_id:
            df.at[idx, 'respuesta_id'] = button_id
        
        return True, df, f"Respuesta registrada para {df.at[idx, 'nombre']}"
