"""
Servicio de gestión de base de datos SQLite para tracking de estudiantes.

Este módulo encapsula toda la lógica de interacción con SQLite,
permitiendo el seguimiento de estudiantes y bootcamps sin depender
de la sincronización con Google Drive.

Soporta dos modos:
- Desarrollo: SQLite local (whatsapp_tracking.db)
- Producción: Turso/libSQL (SQLite en la nube)
"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import os
import threading
import time

# Imports para Turso
import requests
import json


class DatabaseHandler:
    """
    Gestor de base de datos SQLite para el sistema de mensajería.
    
    Maneja dos tablas principales:
    - bootcamps: Catálogo de bootcamps disponibles
    - estudiantes: Información completa de estudiantes y sus respuestas
    
    Soporta Turso (cloud) y SQLite local automáticamente.
    """
    
    def __init__(self, db_path: str = "whatsapp_tracking.db"):
        """
        Inicializa el manejador de base de datos.
        
        Detecta automáticamente si usar Turso (producción) o SQLite local (desarrollo).
        
        Args:
            db_path: Ruta al archivo de base de datos SQLite (solo para modo local)
        """
        self.db_path = db_path
        self._lock = threading.RLock()  # Lock para operaciones críticas
        
        # Detectar si usar Turso o SQLite local
        self.turso_url = os.getenv('TURSO_DATABASE_URL')
        self.turso_token = os.getenv('TURSO_AUTH_TOKEN')
        
        if self.turso_url and self.turso_token:
            self.use_turso = True
            # Convertir URL de libsql a HTTP
            self.turso_http_url = self.turso_url.replace('libsql://', 'https://')
            print(f"✅ Usando Turso (cloud): {self.turso_url}")
        else:
            self.use_turso = False
            self.turso_http_url = None
            print(f"✅ Usando SQLite local: {self.db_path}")
        
        self._init_database()
    
    def _execute_turso_query(self, query: str, params: tuple = None):
        """Ejecuta una query en Turso via HTTP."""
        url = f"{self.turso_http_url}/v2/pipeline"
        headers = {
            'Authorization': f'Bearer {self.turso_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            "requests": [{
                "type": "execute",
                "stmt": {
                    "sql": query
                }
            }]
        }
        
        # Formatear parámetros según el tipo esperado por Turso
        if params:
            args = []
            for param in params:
                if param is None:
                    args.append({"type": "null"})
                elif isinstance(param, bool):
                    args.append({"type": "integer", "value": str(1 if param else 0)})
                elif isinstance(param, int):
                    args.append({"type": "integer", "value": str(param)})
                elif isinstance(param, float):
                    args.append({"type": "float", "value": str(param)})
                else:  # string
                    args.append({"type": "text", "value": str(param)})
            payload["requests"][0]["stmt"]["args"] = args
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code != 200:
            raise Exception(f"Turso query failed: {response.status_code} - {response.text}")
        
        result = response.json()
        return result.get('results', [{}])[0]
    
    def _execute_query(self, query: str, params: tuple = None, fetch_one: bool = False, fetch_all: bool = False):
        """
        Método unificado para ejecutar queries en Turso o SQLite.
        
        Args:
            query: Query SQL a ejecutar
            params: Parámetros de la query
            fetch_one: Si debe retornar un solo resultado
            fetch_all: Si debe retornar todos los resultados
            
        Returns:
            None, dict, o list[dict] dependiendo de fetch_one/fetch_all
        """
        if self.use_turso:
            # Turso via HTTP
            result = self._execute_turso_query(query, params)
            
            if fetch_all:
                # Convertir resultado de Turso a lista de diccionarios
                rows = result.get('response', {}).get('result', {}).get('rows', [])
                cols = [col['name'] for col in result.get('response', {}).get('result', {}).get('cols', [])]
                return [dict(zip(cols, row)) for row in rows]
            elif fetch_one:
                rows = result.get('response', {}).get('result', {}).get('rows', [])
                if rows:
                    cols = [col['name'] for col in result.get('response', {}).get('result', {}).get('cols', [])]
                    return dict(zip(cols, rows[0]))
                return None
            else:
                # Solo ejecutar (INSERT, UPDATE, DELETE)
                return None
        else:
            # SQLite local
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            if fetch_all:
                rows = cursor.fetchall()
                conn.close()
                return [dict(row) for row in rows]
            elif fetch_one:
                row = cursor.fetchone()
                conn.close()
                return dict(row) if row else None
            else:
                conn.commit()
                conn.close()
                return None
    
    def _get_connection(self):
        """Crea una conexión a la base de datos (Turso o SQLite local)."""
        if self.use_turso:
            # Para Turso, retornamos self ya que usamos HTTP directo
            return self
        else:
            # Conexión a SQLite local
            conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,  # Esperar hasta 30 segundos si está bloqueada
                check_same_thread=False,  # Permitir uso desde múltiples threads
                isolation_level=None  # Autocommit mode para mejor concurrencia
            )
            conn.row_factory = sqlite3.Row
            # Habilitar Write-Ahead Logging para mejor concurrencia
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA busy_timeout=30000')  # 30 segundos
            conn.execute('PRAGMA synchronous=NORMAL')  # Balance entre velocidad y seguridad
            return conn
    
    def _execute_with_retry(self, func, max_retries=3, delay=0.5):
        """
        Ejecuta una función con reintentos en caso de bloqueo.
        
        Args:
            func: Función a ejecutar
            max_retries: Número máximo de reintentos
            delay: Segundos de espera entre reintentos
            
        Returns:
            El resultado de la función
        """
        for attempt in range(max_retries):
            try:
                return func()
            except sqlite3.OperationalError as e:
                if "locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(delay * (attempt + 1))  # Backoff exponencial
                    continue
                raise
        return None
    
    def _init_database(self):
        """Inicializa las tablas de la base de datos si no existen."""
        conn = self._get_connection()
        
        # Queries de creación de tablas
        queries = [
            # Tabla de bootcamps
            '''CREATE TABLE IF NOT EXISTS bootcamps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bootcamp_id TEXT UNIQUE NOT NULL,
                bootcamp_nombre TEXT NOT NULL,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            # Tabla de estudiantes
            '''CREATE TABLE IF NOT EXISTS estudiantes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telefono_e164 TEXT NOT NULL UNIQUE,
                nombre TEXT NOT NULL,
                bootcamp_id TEXT,
                bootcamp_nombre TEXT,
                modalidad TEXT,
                ingles_inicio TEXT,
                ingles_fin TEXT,
                inicio_formacion TEXT,
                horario TEXT,
                lugar TEXT,
                opt_in TEXT,
                estado_envio TEXT,
                fecha_envio TIMESTAMP,
                message_id TEXT,
                respuesta TEXT,
                fecha_respuesta TIMESTAMP,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',
            
            # Índices para mejorar rendimiento
            '''CREATE INDEX IF NOT EXISTS idx_estudiantes_telefono 
            ON estudiantes(telefono_e164)''',
            
            '''CREATE INDEX IF NOT EXISTS idx_estudiantes_bootcamp 
            ON estudiantes(bootcamp_id)''',
            
            '''CREATE INDEX IF NOT EXISTS idx_estudiantes_fecha_envio 
            ON estudiantes(fecha_envio)''',
            
            '''CREATE INDEX IF NOT EXISTS idx_estudiantes_respuesta 
            ON estudiantes(respuesta)'''
        ]
        
        if self.use_turso:
            # Turso usa HTTP directo
            for query in queries:
                self._execute_turso_query(query)
        else:
            # SQLite usa cursor
            cursor = conn.cursor()
            for query in queries:
                cursor.execute(query)
            conn.commit()
            conn.close()
    
    # ==================== BOOTCAMPS ====================
    
    def insert_or_update_bootcamp(self, bootcamp_id: str, bootcamp_nombre: str) -> Tuple[bool, str]:
        """
        Inserta o actualiza un bootcamp en la base de datos.
        
        Args:
            bootcamp_id: Código único del bootcamp
            bootcamp_nombre: Nombre del bootcamp
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        if not bootcamp_id or not bootcamp_nombre:
            return False, "bootcamp_id y bootcamp_nombre son requeridos"
        
        try:
            query = '''
                INSERT INTO bootcamps (bootcamp_id, bootcamp_nombre)
                VALUES (?, ?)
                ON CONFLICT(bootcamp_id) 
                DO UPDATE SET bootcamp_nombre = excluded.bootcamp_nombre
            '''
            self._execute_query(query, (bootcamp_id, bootcamp_nombre))
            return True, f"Bootcamp {bootcamp_id} registrado"
        except Exception as e:
            return False, f"Error al guardar bootcamp: {str(e)}"
    
    def get_all_bootcamps(self) -> List[Dict[str, Any]]:
        """
        Obtiene todos los bootcamps registrados.
        
        Returns:
            List[Dict]: Lista de bootcamps
        """
        try:
            query = '''
                SELECT bootcamp_id, bootcamp_nombre, fecha_creacion
                FROM bootcamps
                ORDER BY bootcamp_nombre
            '''
            return self._execute_query(query, fetch_all=True)
        except Exception as e:
            print(f"Error obteniendo bootcamps: {str(e)}")
            return []
    
    # ==================== ESTUDIANTES ====================
    
    def insert_or_update_estudiante(self, estudiante_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Inserta o actualiza un estudiante en la base de datos.
        
        Args:
            estudiante_data: Diccionario con los datos del estudiante
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        required_fields = ['telefono_e164', 'nombre']
        for field in required_fields:
            if field not in estudiante_data or not estudiante_data[field]:
                return False, f"Campo requerido faltante: {field}"
        
        # Preparar datos para inserción
        telefono = estudiante_data.get('telefono_e164')
        nombre = estudiante_data.get('nombre')
        bootcamp_id = estudiante_data.get('bootcamp_id') or ''
        bootcamp_nombre = estudiante_data.get('bootcamp_nombre') or ''
        modalidad = estudiante_data.get('modalidad') or ''
        ingles_inicio = estudiante_data.get('ingles_inicio') or ''
        ingles_fin = estudiante_data.get('ingles_fin') or ''
        inicio_formacion = estudiante_data.get('inicio_formacion') or ''
        horario = estudiante_data.get('horario') or ''
        lugar = estudiante_data.get('lugar') or ''
        opt_in = estudiante_data.get('opt_in') or ''
        estado_envio = estudiante_data.get('estado_envio') or ''
        fecha_envio = estudiante_data.get('fecha_envio') or None
        message_id = estudiante_data.get('message_id') or ''
        respuesta = estudiante_data.get('respuesta') or ''
        fecha_respuesta = estudiante_data.get('fecha_respuesta') or None
        
        try:
            query = '''
                INSERT INTO estudiantes (
                    telefono_e164, nombre, bootcamp_id, bootcamp_nombre,
                    modalidad, ingles_inicio, ingles_fin, inicio_formacion,
                    horario, lugar, opt_in, estado_envio, fecha_envio,
                    message_id, respuesta, fecha_respuesta
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(telefono_e164) 
                DO UPDATE SET
                    nombre = excluded.nombre,
                    bootcamp_id = excluded.bootcamp_id,
                    bootcamp_nombre = excluded.bootcamp_nombre,
                    modalidad = excluded.modalidad,
                    ingles_inicio = excluded.ingles_inicio,
                    ingles_fin = excluded.ingles_fin,
                    inicio_formacion = excluded.inicio_formacion,
                    horario = excluded.horario,
                    lugar = excluded.lugar,
                    opt_in = excluded.opt_in,
                    estado_envio = CASE 
                        WHEN excluded.estado_envio != '' THEN excluded.estado_envio 
                        ELSE estudiantes.estado_envio 
                    END,
                    fecha_envio = CASE 
                        WHEN excluded.fecha_envio IS NOT NULL THEN excluded.fecha_envio 
                        ELSE estudiantes.fecha_envio 
                    END,
                    message_id = CASE 
                        WHEN excluded.message_id != '' THEN excluded.message_id 
                        ELSE estudiantes.message_id 
                    END,
                    respuesta = CASE 
                        WHEN excluded.respuesta != '' THEN excluded.respuesta 
                        ELSE estudiantes.respuesta 
                    END,
                    fecha_respuesta = CASE 
                        WHEN excluded.fecha_respuesta IS NOT NULL THEN excluded.fecha_respuesta 
                        ELSE estudiantes.fecha_respuesta 
                    END,
                    fecha_actualizacion = CURRENT_TIMESTAMP
            '''
            
            params = (
                telefono, nombre, bootcamp_id, bootcamp_nombre,
                modalidad, ingles_inicio, ingles_fin, inicio_formacion,
                horario, lugar, opt_in, estado_envio, fecha_envio,
                message_id, respuesta, fecha_respuesta
            )
            
            self._execute_query(query, params)
            return True, f"Estudiante {nombre} registrado/actualizado"
        except Exception as e:
            return False, f"Error al guardar estudiante: {str(e)}"
    
    def get_estudiantes_by_bootcamp(self, bootcamp_id: str) -> List[Dict[str, Any]]:
        """
        Obtiene todos los estudiantes de un bootcamp específico.
        
        Args:
            bootcamp_id: Código del bootcamp
            
        Returns:
            List[Dict]: Lista de estudiantes
        """
        try:
            query = '''
                SELECT * FROM estudiantes
                WHERE bootcamp_id = ?
                ORDER BY fecha_envio DESC
            '''
            return self._execute_query(query, (bootcamp_id,), fetch_all=True)
        except Exception as e:
            print(f"Error obteniendo estudiantes: {str(e)}")
            return []
    
    def get_estudiante_by_phone(self, telefono: str) -> List[Dict[str, Any]]:
        """
        Busca estudiantes por número de teléfono.
        
        Args:
            telefono: Número de teléfono a buscar
            
        Returns:
            List[Dict]: Lista de registros del estudiante
        """
        try:
            # Normalizar teléfono para búsqueda
            telefono_clean = telefono.replace('+', '').replace(' ', '').replace('-', '')
            
            query = '''
                SELECT * FROM estudiantes
                WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = ?
                ORDER BY fecha_envio DESC
            '''
            return self._execute_query(query, (telefono_clean,), fetch_all=True)
        except Exception as e:
            print(f"Error buscando por teléfono: {str(e)}")
            return []
    
    def get_estudiantes_by_date_range(
        self, 
        fecha_inicio: Optional[str] = None, 
        fecha_fin: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtiene estudiantes filtrados por rango de fechas de envío.
        
        Args:
            fecha_inicio: Fecha inicial (formato ISO: YYYY-MM-DD)
            fecha_fin: Fecha final (formato ISO: YYYY-MM-DD)
            
        Returns:
            List[Dict]: Lista de estudiantes
        """
        try:
            query = "SELECT * FROM estudiantes WHERE 1=1"
            params = []
            
            if fecha_inicio:
                query += " AND DATE(fecha_envio) >= ?"
                params.append(fecha_inicio)
            
            if fecha_fin:
                query += " AND DATE(fecha_envio) <= ?"
                params.append(fecha_fin)
            
            query += " ORDER BY fecha_envio DESC"
            
            return self._execute_query(query, tuple(params) if params else None, fetch_all=True)
        except Exception as e:
            print(f"Error buscando por fecha: {str(e)}")
            return []
    
    def get_all_estudiantes(
        self, 
        limit: int = 100, 
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Obtiene todos los estudiantes con paginación.
        
        Args:
            limit: Número máximo de registros a retornar
            offset: Número de registros a saltar
            
        Returns:
            Tuple[List[Dict], int]: (lista de estudiantes, total de registros)
        """
        try:
            # Obtener total de registros
            total_result = self._execute_query("SELECT COUNT(*) as total FROM estudiantes", fetch_one=True)
            total = total_result.get('total', 0) if total_result else 0
            
            # Obtener registros paginados
            query = '''
                SELECT * FROM estudiantes
                ORDER BY fecha_envio DESC
                LIMIT ? OFFSET ?
            '''
            rows = self._execute_query(query, (limit, offset), fetch_all=True)
            
            return rows, total
        except Exception as e:
            print(f"Error obteniendo todos los estudiantes: {str(e)}")
            return [], 0
    
    def get_estadisticas(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas generales del sistema.
        
        Returns:
            Dict: Estadísticas completas
        """
        try:
            # Helper para extraer valor numérico (Turso puede devolver dict con 'type' y 'value')
            def get_count_value(result, key):
                if not result:
                    return 0
                value = result.get(key, 0)
                # Si es un dict de Turso, extraer el valor
                if isinstance(value, dict):
                    return int(value.get('value', 0))
                return int(value) if value else 0
            
            # Total de estudiantes
            result_total = self._execute_query(
                "SELECT COUNT(*) as total FROM estudiantes",
                fetch_one=True
            )
            total = get_count_value(result_total, 'total')
            
            # Enviados con éxito
            result_enviados = self._execute_query(
                "SELECT COUNT(*) as enviados FROM estudiantes WHERE estado_envio = 'sent'",
                fetch_one=True
            )
            enviados = get_count_value(result_enviados, 'enviados')
            
            # Con errores
            result_errores = self._execute_query(
                "SELECT COUNT(*) as errores FROM estudiantes WHERE estado_envio = 'error'",
                fetch_one=True
            )
            errores = get_count_value(result_errores, 'errores')
            
            # Respondieron "Sí"
            result_confirmados = self._execute_query(
                "SELECT COUNT(*) as confirmados FROM estudiantes WHERE respuesta = 'Sí'",
                fetch_one=True
            )
            confirmados = get_count_value(result_confirmados, 'confirmados')
            
            # Respondieron "No"
            result_rechazados = self._execute_query(
                "SELECT COUNT(*) as rechazados FROM estudiantes WHERE respuesta = 'No'",
                fetch_one=True
            )
            rechazados = get_count_value(result_rechazados, 'rechazados')
            
            # Sin respuesta
            pendientes_respuesta = enviados - confirmados - rechazados
            
            # Total de bootcamps
            result_bootcamps = self._execute_query(
                "SELECT COUNT(*) as total_bootcamps FROM bootcamps",
                fetch_one=True
            )
            total_bootcamps = get_count_value(result_bootcamps, 'total_bootcamps')
            
            return {
                'total_estudiantes': total,
                'mensajes_enviados': enviados,
                'mensajes_error': errores,
                'confirmaron_si': confirmados,
                'confirmaron_no': rechazados,
                'pendientes_respuesta': pendientes_respuesta,
                'total_bootcamps': total_bootcamps,
                'tasa_respuesta': round((confirmados + rechazados) / enviados * 100, 2) if enviados > 0 else 0
            }
            
        except Exception as e:
            print(f"Error obteniendo estadísticas: {str(e)}")
            return {}
    
    def update_respuesta(
        self, 
        telefono: str, 
        respuesta: str, 
        fecha_respuesta: str
    ) -> Tuple[bool, str]:
        """
        Actualiza la respuesta de un estudiante.
        
        Args:
            telefono: Número de teléfono del estudiante
            respuesta: Respuesta del estudiante ("Sí" o "No")
            fecha_respuesta: Timestamp de la respuesta
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        # Normalizar teléfono
        telefono_clean = telefono.replace('+', '').replace(' ', '').replace('-', '')
        
        def _execute():
            if self.use_turso:
                # Para Turso necesitamos hacer SELECT primero para contar
                check_result = self._execute_query('''
                    SELECT COUNT(*) as count FROM estudiantes
                    WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = ?
                      AND (respuesta IS NULL OR respuesta = '')
                ''', (telefono_clean,), fetch_one=True)
                
                if check_result and check_result['count'] > 0:
                    self._execute_query('''
                        UPDATE estudiantes
                        SET respuesta = ?,
                            fecha_respuesta = ?,
                            fecha_actualizacion = CURRENT_TIMESTAMP
                        WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = ?
                          AND (respuesta IS NULL OR respuesta = '')
                    ''', (respuesta, fecha_respuesta, telefono_clean))
                    return True, f"Respuesta actualizada para {check_result['count']} registro(s)"
                else:
                    return False, "No se encontró el estudiante o ya tiene respuesta"
            else:
                # SQLite puede usar rowcount
                conn = self._get_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE estudiantes
                        SET respuesta = ?,
                            fecha_respuesta = ?,
                            fecha_actualizacion = CURRENT_TIMESTAMP
                        WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = ?
                          AND (respuesta IS NULL OR respuesta = '')
                    ''', (respuesta, fecha_respuesta, telefono_clean))
                    rows_affected = cursor.rowcount
                    conn.commit()
                    
                    if rows_affected > 0:
                        return True, f"Respuesta actualizada para {rows_affected} registro(s)"
                    else:
                        return False, "No se encontró el estudiante o ya tiene respuesta"
                finally:
                    conn.close()
        
        try:
            return self._execute_with_retry(_execute)
        except Exception as e:
            return False, f"Error actualizando respuesta: {str(e)}"
    
    # ==================== CRUD OPERATIONS ====================
    
    def update_estudiante_field(
        self,
        telefono: str,
        field: str,
        value: Any
    ) -> Tuple[bool, str]:
        """
        Actualiza un campo específico de un estudiante.
        
        Args:
            telefono: Número de teléfono del estudiante
            field: Nombre del campo a actualizar
            value: Nuevo valor
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        # Validar campo permitido
        allowed_fields = [
            'nombre', 'bootcamp_id', 'bootcamp_nombre', 'modalidad',
            'ingles_inicio', 'ingles_fin', 'inicio_formacion', 'horario',
            'lugar', 'opt_in', 'estado_envio', 'fecha_envio', 'message_id',
            'respuesta', 'fecha_respuesta'
        ]
        
        if field not in allowed_fields:
            return False, f"Campo no válido: {field}"
        
        try:
            # Normalizar teléfono
            telefono_clean = telefono.replace('+', '').replace(' ', '').replace('-', '')
            
            query = f'''
                UPDATE estudiantes
                SET {field} = ?,
                    fecha_actualizacion = CURRENT_TIMESTAMP
                WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = ?
            '''
            
            if self.use_turso:
                # Para Turso, verificar si existe primero
                check = self._execute_query(
                    "SELECT COUNT(*) as count FROM estudiantes WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = ?",
                    (telefono_clean,),
                    fetch_one=True
                )
                if check and check['count'] > 0:
                    self._execute_query(query, (value, telefono_clean))
                    return True, f"Campo '{field}' actualizado exitosamente"
                else:
                    return False, f"No se encontró estudiante con teléfono {telefono}"
            else:
                # SQLite con rowcount
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute(query, (value, telefono_clean))
                rows_affected = cursor.rowcount
                conn.commit()
                conn.close()
                
                if rows_affected > 0:
                    return True, f"Campo '{field}' actualizado exitosamente"
                else:
                    return False, f"No se encontró estudiante con teléfono {telefono}"
            
        except Exception as e:
            return False, f"Error actualizando campo: {str(e)}"
    
    def update_estudiante_fields(
        self,
        telefono: str,
        fields: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Actualiza múltiples campos de un estudiante.
        
        Args:
            telefono: Número de teléfono del estudiante
            fields: Diccionario con {campo: valor}
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        allowed_fields = [
            'nombre', 'bootcamp_id', 'bootcamp_nombre', 'modalidad',
            'ingles_inicio', 'ingles_fin', 'inicio_formacion', 'horario',
            'lugar', 'opt_in', 'estado_envio', 'fecha_envio', 'message_id',
            'respuesta', 'fecha_respuesta'
        ]
        
        # Validar campos
        invalid_fields = [f for f in fields.keys() if f not in allowed_fields]
        if invalid_fields:
            return False, f"Campos no válidos: {', '.join(invalid_fields)}"
        
        if not fields:
            return False, "No se especificaron campos para actualizar"
        
        try:
            # Normalizar teléfono
            telefono_clean = telefono.replace('+', '').replace(' ', '').replace('-', '')
            
            # Construir query dinámicamente
            set_clauses = [f"{field} = ?" for field in fields.keys()]
            set_clauses.append("fecha_actualizacion = CURRENT_TIMESTAMP")
            set_clause = ", ".join(set_clauses)
            
            query = f'''
                UPDATE estudiantes
                SET {set_clause}
                WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = ?
            '''
            
            values = list(fields.values()) + [telefono_clean]
            
            if self.use_turso:
                # Para Turso, verificar existencia primero
                check = self._execute_query(
                    "SELECT COUNT(*) as count FROM estudiantes WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = ?",
                    (telefono_clean,),
                    fetch_one=True
                )
                if check and check['count'] > 0:
                    self._execute_query(query, tuple(values))
                    return True, f"{len(fields)} campo(s) actualizado(s) exitosamente"
                else:
                    return False, f"No se encontró estudiante con teléfono {telefono}"
            else:
                # SQLite con rowcount
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute(query, values)
                rows_affected = cursor.rowcount
                conn.commit()
                conn.close()
                
                if rows_affected > 0:
                    return True, f"{len(fields)} campo(s) actualizado(s) exitosamente"
                else:
                    return False, f"No se encontró estudiante con teléfono {telefono}"
            
        except Exception as e:
            return False, f"Error actualizando campos: {str(e)}"
    
    def delete_estudiante(self, telefono: str) -> Tuple[bool, str]:
        """
        Elimina un estudiante por su teléfono.
        
        Args:
            telefono: Número de teléfono del estudiante
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            # Normalizar teléfono
            telefono_clean = telefono.replace('+', '').replace(' ', '').replace('-', '')
            
            if self.use_turso:
                # Verificar existencia antes de eliminar
                check = self._execute_query(
                    "SELECT COUNT(*) as count FROM estudiantes WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = ?",
                    (telefono_clean,),
                    fetch_one=True
                )
                if check and check['count'] > 0:
                    self._execute_query('''
                        DELETE FROM estudiantes
                        WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = ?
                    ''', (telefono_clean,))
                    return True, f"Estudiante eliminado ({check['count']} registro(s))"
                else:
                    return False, f"No se encontró estudiante con teléfono {telefono}"
            else:
                # SQLite con rowcount
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM estudiantes
                    WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = ?
                ''', (telefono_clean,))
                rows_affected = cursor.rowcount
                conn.commit()
                conn.close()
                
                if rows_affected > 0:
                    return True, f"Estudiante eliminado ({rows_affected} registro(s))"
                else:
                    return False, f"No se encontró estudiante con teléfono {telefono}"
            
        except Exception as e:
            return False, f"Error eliminando estudiante: {str(e)}"
    
    def delete_bootcamp(self, bootcamp_id: str) -> Tuple[bool, str]:
        """
        Elimina un bootcamp del catálogo.
        
        Args:
            bootcamp_id: Código del bootcamp
            
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            if self.use_turso:
                # Verificar existencia antes de eliminar
                check = self._execute_query(
                    "SELECT COUNT(*) as count FROM bootcamps WHERE bootcamp_id = ?",
                    (bootcamp_id,),
                    fetch_one=True
                )
                if check and check['count'] > 0:
                    self._execute_query('DELETE FROM bootcamps WHERE bootcamp_id = ?', (bootcamp_id,))
                    return True, f"Bootcamp {bootcamp_id} eliminado"
                else:
                    return False, f"No se encontró bootcamp {bootcamp_id}"
            else:
                # SQLite con rowcount
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM bootcamps WHERE bootcamp_id = ?', (bootcamp_id,))
                rows_affected = cursor.rowcount
                conn.commit()
                conn.close()
                
                if rows_affected > 0:
                    return True, f"Bootcamp {bootcamp_id} eliminado"
                else:
                    return False, f"No se encontró bootcamp {bootcamp_id}"
            
        except Exception as e:
            return False, f"Error eliminando bootcamp: {str(e)}"
    
    def clear_all_estudiantes(self) -> Tuple[bool, str]:
        """
        Elimina TODOS los estudiantes de la base de datos.
        
        ⚠️ PELIGRO: Esta operación no se puede deshacer.
        
        Returns:
            Tuple[bool, str]: (éxito, mensaje con cantidad eliminada)
        """
        def _execute():
            with self._lock:  # Lock crítico para operación de borrado
                if self.use_turso:
                    # Para Turso, contar primero y luego eliminar
                    count_result = self._execute_query(
                        'SELECT COUNT(*) as total FROM estudiantes',
                        fetch_one=True
                    )
                    # Extraer el valor del dict de Turso
                    if count_result and 'total' in count_result:
                        total_value = count_result['total']
                        count = int(total_value.get('value', 0)) if isinstance(total_value, dict) else int(total_value)
                    else:
                        count = 0
                    self._execute_query('DELETE FROM estudiantes')
                    return True, f"{count} estudiante(s) eliminado(s)"
                else:
                    # SQLite tradicional
                    conn = self._get_connection()
                    try:
                        cursor = conn.cursor()
                        cursor.execute('SELECT COUNT(*) as total FROM estudiantes')
                        count = cursor.fetchone()['total']
                        cursor.execute('DELETE FROM estudiantes')
                        conn.commit()
                        return True, f"{count} estudiante(s) eliminado(s)"
                    finally:
                        conn.close()
        
        try:
            return self._execute_with_retry(_execute)
        except sqlite3.OperationalError as e:
            if "locked" in str(e):
                return False, "Base de datos ocupada. Intenta de nuevo en unos segundos."
            return False, f"Error vaciando tabla estudiantes: {str(e)}"
        except Exception as e:
            return False, f"Error vaciando tabla estudiantes: {str(e)}"
    
    def clear_all_bootcamps(self) -> Tuple[bool, str]:
        """
        Elimina TODOS los bootcamps de la base de datos.
        
        ⚠️ PELIGRO: Esta operación no se puede deshacer.
        
        Returns:
            Tuple[bool, str]: (éxito, mensaje con cantidad eliminada)
        """
        def _execute():
            with self._lock:  # Lock crítico para operación de borrado
                if self.use_turso:
                    # Para Turso, contar primero y luego eliminar
                    count_result = self._execute_query(
                        'SELECT COUNT(*) as total FROM bootcamps',
                        fetch_one=True
                    )
                    # Extraer el valor del dict de Turso
                    if count_result and 'total' in count_result:
                        total_value = count_result['total']
                        count = int(total_value.get('value', 0)) if isinstance(total_value, dict) else int(total_value)
                    else:
                        count = 0
                    self._execute_query('DELETE FROM bootcamps')
                    return True, f"{count} bootcamp(s) eliminado(s)"
                else:
                    # SQLite tradicional
                    conn = self._get_connection()
                    try:
                        cursor = conn.cursor()
                        cursor.execute('SELECT COUNT(*) as total FROM bootcamps')
                        count = cursor.fetchone()['total']
                        cursor.execute('DELETE FROM bootcamps')
                        conn.commit()
                        return True, f"{count} bootcamp(s) eliminado(s)"
                    finally:
                        conn.close()
        
        try:
            return self._execute_with_retry(_execute)
        except sqlite3.OperationalError as e:
            if "locked" in str(e):
                return False, "Base de datos ocupada. Intenta de nuevo en unos segundos."
            return False, f"Error vaciando tabla bootcamps: {str(e)}"
        except Exception as e:
            return False, f"Error vaciando tabla bootcamps: {str(e)}"
    
    def reset_database(self) -> Tuple[bool, str]:
        """
        Elimina TODO el contenido de la base de datos.
        
        ⚠️ PELIGRO EXTREMO: Borra estudiantes Y bootcamps.
        
        Returns:
            Tuple[bool, str]: (éxito, mensaje)
        """
        try:
            success1, msg1 = self.clear_all_estudiantes()
            success2, msg2 = self.clear_all_bootcamps()
            
            if success1 and success2:
                return True, f"Base de datos vaciada: {msg1}, {msg2}"
            else:
                errors = []
                if not success1:
                    errors.append(msg1)
                if not success2:
                    errors.append(msg2)
                return False, f"Errores: {'; '.join(errors)}"
            
        except Exception as e:
            return False, f"Error reseteando base de datos: {str(e)}"
