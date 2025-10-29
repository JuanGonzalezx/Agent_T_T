"""
Servicio de gestión de base de datos SQLite para tracking de estudiantes.

Este módulo encapsula toda la lógica de interacción con SQLite,
permitiendo el seguimiento de estudiantes y bootcamps sin depender
de la sincronización con Google Drive.
"""

import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import os


class DatabaseHandler:
    """
    Gestor de base de datos SQLite para el sistema de mensajería.
    
    Maneja dos tablas principales:
    - bootcamps: Catálogo de bootcamps disponibles
    - estudiantes: Información completa de estudiantes y sus respuestas
    """
    
    def __init__(self, db_path: str = "whatsapp_tracking.db"):
        """
        Inicializa el manejador de base de datos.
        
        Args:
            db_path: Ruta al archivo de base de datos SQLite
        """
        self.db_path = db_path
        self._init_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Crea una conexión a la base de datos."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Permite acceso por nombre de columna
        return conn
    
    def _init_database(self):
        """Inicializa las tablas de la base de datos si no existen."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Tabla de bootcamps
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bootcamps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bootcamp_id TEXT UNIQUE NOT NULL,
                bootcamp_nombre TEXT NOT NULL,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de estudiantes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS estudiantes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telefono_e164 TEXT NOT NULL,
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
                fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(telefono_e164, bootcamp_id)
            )
        ''')
        
        # Índices para mejorar rendimiento de búsquedas
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_estudiantes_telefono 
            ON estudiantes(telefono_e164)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_estudiantes_bootcamp 
            ON estudiantes(bootcamp_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_estudiantes_fecha_envio 
            ON estudiantes(fecha_envio)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_estudiantes_respuesta 
            ON estudiantes(respuesta)
        ''')
        
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
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO bootcamps (bootcamp_id, bootcamp_nombre)
                VALUES (?, ?)
                ON CONFLICT(bootcamp_id) 
                DO UPDATE SET bootcamp_nombre = excluded.bootcamp_nombre
            ''', (bootcamp_id, bootcamp_nombre))
            
            conn.commit()
            conn.close()
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
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT bootcamp_id, bootcamp_nombre, fecha_creacion
                FROM bootcamps
                ORDER BY bootcamp_nombre
            ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
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
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Preparar datos para inserción
            telefono = estudiante_data.get('telefono_e164')
            nombre = estudiante_data.get('nombre')
            bootcamp_id = estudiante_data.get('bootcamp_id', '')
            bootcamp_nombre = estudiante_data.get('bootcamp_nombre', '')
            modalidad = estudiante_data.get('modalidad', '')
            ingles_inicio = estudiante_data.get('ingles_inicio', '')
            ingles_fin = estudiante_data.get('ingles_fin', '')
            inicio_formacion = estudiante_data.get('inicio_formacion', '')
            horario = estudiante_data.get('horario', '')
            lugar = estudiante_data.get('lugar', '')
            opt_in = estudiante_data.get('opt_in', '')
            estado_envio = estudiante_data.get('estado_envio', '')
            fecha_envio = estudiante_data.get('fecha_envio', None)
            message_id = estudiante_data.get('message_id', '')
            respuesta = estudiante_data.get('respuesta', '')
            fecha_respuesta = estudiante_data.get('fecha_respuesta', None)
            
            cursor.execute('''
                INSERT INTO estudiantes (
                    telefono_e164, nombre, bootcamp_id, bootcamp_nombre,
                    modalidad, ingles_inicio, ingles_fin, inicio_formacion,
                    horario, lugar, opt_in, estado_envio, fecha_envio,
                    message_id, respuesta, fecha_respuesta
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(telefono_e164, bootcamp_id) 
                DO UPDATE SET
                    nombre = excluded.nombre,
                    bootcamp_nombre = excluded.bootcamp_nombre,
                    modalidad = excluded.modalidad,
                    ingles_inicio = excluded.ingles_inicio,
                    ingles_fin = excluded.ingles_fin,
                    inicio_formacion = excluded.inicio_formacion,
                    horario = excluded.horario,
                    lugar = excluded.lugar,
                    opt_in = excluded.opt_in,
                    estado_envio = excluded.estado_envio,
                    fecha_envio = excluded.fecha_envio,
                    message_id = excluded.message_id,
                    respuesta = excluded.respuesta,
                    fecha_respuesta = excluded.fecha_respuesta,
                    fecha_actualizacion = CURRENT_TIMESTAMP
            ''', (
                telefono, nombre, bootcamp_id, bootcamp_nombre,
                modalidad, ingles_inicio, ingles_fin, inicio_formacion,
                horario, lugar, opt_in, estado_envio, fecha_envio,
                message_id, respuesta, fecha_respuesta
            ))
            
            conn.commit()
            conn.close()
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
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM estudiantes
                WHERE bootcamp_id = ?
                ORDER BY fecha_envio DESC
            ''', (bootcamp_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
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
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Normalizar teléfono para búsqueda
            telefono_clean = telefono.replace('+', '').replace(' ', '').replace('-', '')
            
            cursor.execute('''
                SELECT * FROM estudiantes
                WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = ?
                ORDER BY fecha_envio DESC
            ''', (telefono_clean,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
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
            conn = self._get_connection()
            cursor = conn.cursor()
            
            query = "SELECT * FROM estudiantes WHERE 1=1"
            params = []
            
            if fecha_inicio:
                query += " AND DATE(fecha_envio) >= ?"
                params.append(fecha_inicio)
            
            if fecha_fin:
                query += " AND DATE(fecha_envio) <= ?"
                params.append(fecha_fin)
            
            query += " ORDER BY fecha_envio DESC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
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
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Obtener total de registros
            cursor.execute("SELECT COUNT(*) as total FROM estudiantes")
            total = cursor.fetchone()['total']
            
            # Obtener registros paginados
            cursor.execute('''
                SELECT * FROM estudiantes
                ORDER BY fecha_envio DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows], total
            
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
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Total de estudiantes
            cursor.execute("SELECT COUNT(*) as total FROM estudiantes")
            total = cursor.fetchone()['total']
            
            # Enviados con éxito
            cursor.execute("SELECT COUNT(*) as enviados FROM estudiantes WHERE estado_envio = 'sent'")
            enviados = cursor.fetchone()['enviados']
            
            # Con errores
            cursor.execute("SELECT COUNT(*) as errores FROM estudiantes WHERE estado_envio = 'error'")
            errores = cursor.fetchone()['errores']
            
            # Respondieron "Sí"
            cursor.execute("SELECT COUNT(*) as confirmados FROM estudiantes WHERE respuesta = 'Sí'")
            confirmados = cursor.fetchone()['confirmados']
            
            # Respondieron "No"
            cursor.execute("SELECT COUNT(*) as rechazados FROM estudiantes WHERE respuesta = 'No'")
            rechazados = cursor.fetchone()['rechazados']
            
            # Sin respuesta
            pendientes_respuesta = enviados - confirmados - rechazados
            
            # Total de bootcamps
            cursor.execute("SELECT COUNT(*) as total_bootcamps FROM bootcamps")
            total_bootcamps = cursor.fetchone()['total_bootcamps']
            
            conn.close()
            
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
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Normalizar teléfono
            telefono_clean = telefono.replace('+', '').replace(' ', '').replace('-', '')
            
            cursor.execute('''
                UPDATE estudiantes
                SET respuesta = ?,
                    fecha_respuesta = ?,
                    fecha_actualizacion = CURRENT_TIMESTAMP
                WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = ?
                  AND respuesta IS NULL OR respuesta = ''
            ''', (respuesta, fecha_respuesta, telefono_clean))
            
            rows_affected = cursor.rowcount
            conn.commit()
            conn.close()
            
            if rows_affected > 0:
                return True, f"Respuesta actualizada para {rows_affected} registro(s)"
            else:
                return False, "No se encontró el estudiante o ya tiene respuesta"
            
        except Exception as e:
            return False, f"Error actualizando respuesta: {str(e)}"
