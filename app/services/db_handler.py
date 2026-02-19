"""
Servicio de gestión de base de datos SQLite para tracking de estudiantes.

Esquema normalizado v3:
  - bootcamps: Info logística del grupo (horario, lugar, modalidad)
  - estudiantes: Datos maestros del alumno + estado académico
  - campanas: Envíos masivos tipados (MATRICULA, EVENTO, INFO)
  - campana_miembros: Tracking individual de cada envío/respuesta

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

    Tablas:
      - bootcamps: Catálogo con info logística
      - estudiantes: Registro maestro de alumnos
      - campanas: Contenedores de envíos masivos
      - campana_miembros: Tracking por estudiante/campaña

    Soporta Turso (cloud) y SQLite local automáticamente.
    """

    def __init__(self, db_path: str = "whatsapp_tracking.db"):
        self.db_path = db_path
        self._lock = threading.RLock()

        # Detectar si usar Turso o SQLite local
        self.turso_url = os.getenv('TURSO_DATABASE_URL')
        self.turso_token = os.getenv('TURSO_AUTH_TOKEN')

        if self.turso_url and self.turso_token:
            self.use_turso = True
            self.turso_http_url = self.turso_url.replace('libsql://', 'https://')
            print(f"[DB] Usando Turso (cloud): {self.turso_url}")
        else:
            self.use_turso = False
            self.turso_http_url = None
            print(f"[DB] Usando SQLite local: {self.db_path}")

        self._init_database()

    # =================================================================
    # INFRAESTRUCTURA DE CONEXIÓN
    # =================================================================

    def _extract_turso_value(self, cell):
        """Extrae el valor real de una celda de Turso."""
        if cell is None:
            return None
        if isinstance(cell, dict):
            if cell.get('type') == 'null':
                return None
            return cell.get('value', '')
        return cell

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
                "stmt": {"sql": query}
            }]
        }

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
                else:
                    args.append({"type": "text", "value": str(param)})
            payload["requests"][0]["stmt"]["args"] = args

        response = requests.post(url, headers=headers, json=payload, timeout=30)

        if response.status_code != 200:
            raise Exception(f"Turso query failed: {response.status_code} - {response.text}")

        result = response.json()
        return result.get('results', [{}])[0]

    def _execute_query(self, query: str, params: tuple = None,
                       fetch_one: bool = False, fetch_all: bool = False):
        """Método unificado para ejecutar queries en Turso o SQLite."""
        if self.use_turso:
            result = self._execute_turso_query(query, params)

            if fetch_all:
                rows = result.get('response', {}).get('result', {}).get('rows', [])
                cols = [col['name'] for col in result.get('response', {}).get('result', {}).get('cols', [])]
                return [dict(zip(cols, [self._extract_turso_value(cell) for cell in row])) for row in rows]
            elif fetch_one:
                rows = result.get('response', {}).get('result', {}).get('rows', [])
                if rows:
                    cols = [col['name'] for col in result.get('response', {}).get('result', {}).get('cols', [])]
                    return dict(zip(cols, [self._extract_turso_value(cell) for cell in rows[0]]))
                return None
            else:
                return None
        else:
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
        """Crea una conexión a la base de datos SQLite local."""
        if self.use_turso:
            return self
        else:
            conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                check_same_thread=False,
                isolation_level=None
            )
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA busy_timeout=30000')
            conn.execute('PRAGMA synchronous=NORMAL')
            return conn

    def _execute_with_retry(self, func, max_retries=3, delay=0.5):
        """Ejecuta una función con reintentos en caso de bloqueo."""
        for attempt in range(max_retries):
            try:
                return func()
            except sqlite3.OperationalError as e:
                if "locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(delay * (attempt + 1))
                    continue
                raise
        return None

    def _execute_insert(self, query: str, params: tuple = None) -> int:
        """
        Ejecuta un INSERT y retorna el last_insert_rowid.

        Para Turso: extrae 'last_insert_rowid' del response JSON.
        Para SQLite: usa cursor.lastrowid.
        """
        if self.use_turso:
            result = self._execute_turso_query(query, params)
            # Verificar error en respuesta Turso
            if result.get('type') == 'error':
                error_msg = result.get('error', {}).get('message', 'Unknown Turso error')
                raise Exception(f"Turso INSERT error: {error_msg}")
            last_id = result.get('response', {}).get('result', {}).get('last_insert_rowid')
            if last_id is not None:
                return int(last_id) if isinstance(last_id, (str, int)) else 0
            return 0
        else:
            conn = self._get_connection()
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            conn.commit()
            last_id = cursor.lastrowid
            conn.close()
            return last_id or 0

    # =================================================================
    # INICIALIZACIÓN DEL ESQUEMA (v3 – normalizado)
    # =================================================================

    def _init_database(self):
        """Crea las tablas si no existen (esquema normalizado v3)."""
        queries = [
            # ─── bootcamps ───
            '''CREATE TABLE IF NOT EXISTS bootcamps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE NOT NULL,
                nombre TEXT NOT NULL,
                modalidad TEXT,
                horario TEXT,
                lugar TEXT,
                fecha_inicio_ingles TEXT,
                fecha_fin_ingles TEXT,
                fecha_inicio_tecnica TEXT,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''',

            # ─── estudiantes ───
            '''CREATE TABLE IF NOT EXISTS estudiantes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telefono_e164 TEXT UNIQUE NOT NULL,
                nombre TEXT NOT NULL,
                documento TEXT,
                email TEXT,
                bootcamp_id INTEGER,
                opt_in INTEGER DEFAULT 1,
                estado_academico TEXT DEFAULT 'INSCRITO',
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(bootcamp_id) REFERENCES bootcamps(id)
            )''',

            # ─── índices estudiantes ───
            'CREATE INDEX IF NOT EXISTS idx_estudiantes_telefono ON estudiantes(telefono_e164)',
            'CREATE INDEX IF NOT EXISTS idx_estudiantes_bootcamp ON estudiantes(bootcamp_id)',
            'CREATE INDEX IF NOT EXISTS idx_estudiantes_estado ON estudiantes(estado_academico)',

            # ─── campañas ───
            '''CREATE TABLE IF NOT EXISTS campanas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                tipo TEXT NOT NULL,
                bootcamp_objetivo_id INTEGER,
                plantilla_whatsapp TEXT,
                estado TEXT DEFAULT 'DRAFT',
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(bootcamp_objetivo_id) REFERENCES bootcamps(id)
            )''',

            # ─── campana_miembros (tracking) ───
            '''CREATE TABLE IF NOT EXISTS campana_miembros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campana_id INTEGER NOT NULL,
                estudiante_id INTEGER NOT NULL,
                variables_contexto TEXT,
                estado_envio TEXT DEFAULT 'pending',
                message_id TEXT,
                respuesta_usuario TEXT,
                mensaje_respuesta_raw TEXT,
                fecha_envio TIMESTAMP,
                fecha_respuesta TIMESTAMP,
                FOREIGN KEY(campana_id) REFERENCES campanas(id),
                FOREIGN KEY(estudiante_id) REFERENCES estudiantes(id)
            )''',

            # ─── índices campañas ───
            'CREATE INDEX IF NOT EXISTS idx_campanas_tipo ON campanas(tipo)',
            'CREATE INDEX IF NOT EXISTS idx_campanas_estado ON campanas(estado)',
            'CREATE INDEX IF NOT EXISTS idx_cm_campana ON campana_miembros(campana_id)',
            'CREATE INDEX IF NOT EXISTS idx_cm_estudiante ON campana_miembros(estudiante_id)',
            'CREATE INDEX IF NOT EXISTS idx_cm_estado ON campana_miembros(estado_envio)',
        ]

        # Migraciones: agregar columnas nuevas a tablas existentes
        migrations = [
            "ALTER TABLE bootcamps ADD COLUMN fecha_fin_ingles TEXT",
        ]

        if self.use_turso:
            for query in queries:
                self._execute_turso_query(query)
            for migration in migrations:
                try:
                    self._execute_turso_query(migration)
                except Exception:
                    pass  # Columna ya existe
        else:
            conn = self._get_connection()
            cursor = conn.cursor()
            for query in queries:
                cursor.execute(query)
            for migration in migrations:
                try:
                    cursor.execute(migration)
                except Exception:
                    pass  # Columna ya existe
            conn.commit()
            conn.close()

    # =================================================================
    # BOOTCAMPS
    # =================================================================

    def insert_or_update_bootcamp(self, codigo: str, nombre: str,
                                   modalidad: str = None, horario: str = None,
                                   lugar: str = None, fecha_inicio_ingles: str = None,
                                   fecha_fin_ingles: str = None,
                                   fecha_inicio_tecnica: str = None) -> Tuple[bool, str]:
        """
        Inserta o actualiza un bootcamp.

        Args:
            codigo: Código único (ej: "IA_Manizales_01")
            nombre: Nombre descriptivo
            modalidad: Presencial / Virtual / Híbrido
            horario: Ej: "L-V 6pm-10pm"
            lugar: Sede / URL
            fecha_inicio_ingles: Fecha inicio inglés
            fecha_fin_ingles: Fecha fin inglés
            fecha_inicio_tecnica: Fecha inicio formación técnica
        """
        if not codigo or not nombre:
            return False, "codigo y nombre son requeridos"

        try:
            query = '''
                INSERT INTO bootcamps (codigo, nombre, modalidad, horario, lugar,
                                       fecha_inicio_ingles, fecha_fin_ingles, fecha_inicio_tecnica)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(codigo)
                DO UPDATE SET
                    nombre = excluded.nombre,
                    modalidad = COALESCE(NULLIF(excluded.modalidad, ''), bootcamps.modalidad),
                    horario = COALESCE(NULLIF(excluded.horario, ''), bootcamps.horario),
                    lugar = COALESCE(NULLIF(excluded.lugar, ''), bootcamps.lugar),
                    fecha_inicio_ingles = COALESCE(NULLIF(excluded.fecha_inicio_ingles, ''), bootcamps.fecha_inicio_ingles),
                    fecha_fin_ingles = COALESCE(NULLIF(excluded.fecha_fin_ingles, ''), bootcamps.fecha_fin_ingles),
                    fecha_inicio_tecnica = COALESCE(NULLIF(excluded.fecha_inicio_tecnica, ''), bootcamps.fecha_inicio_tecnica)
            '''
            self._execute_query(query, (
                codigo, nombre, modalidad or '', horario or '', lugar or '',
                fecha_inicio_ingles or '', fecha_fin_ingles or '', fecha_inicio_tecnica or ''
            ))
            return True, f"Bootcamp {codigo} registrado"
        except Exception as e:
            return False, f"Error al guardar bootcamp: {str(e)}"

    def get_bootcamp_by_codigo(self, codigo: str) -> Optional[Dict[str, Any]]:
        """Obtiene un bootcamp por su código."""
        try:
            return self._execute_query(
                "SELECT * FROM bootcamps WHERE codigo = ?",
                (codigo,), fetch_one=True
            )
        except Exception as e:
            print(f"Error obteniendo bootcamp: {str(e)}")
            return None

    def get_bootcamp_by_id(self, bootcamp_id: int) -> Optional[Dict[str, Any]]:
        """Obtiene un bootcamp por su ID numérico."""
        try:
            return self._execute_query(
                "SELECT * FROM bootcamps WHERE id = ?",
                (bootcamp_id,), fetch_one=True
            )
        except Exception as e:
            print(f"Error obteniendo bootcamp: {str(e)}")
            return None

    def get_all_bootcamps(self) -> List[Dict[str, Any]]:
        """Obtiene todos los bootcamps registrados."""
        try:
            return self._execute_query(
                "SELECT * FROM bootcamps ORDER BY nombre",
                fetch_all=True
            ) or []
        except Exception as e:
            print(f"Error obteniendo bootcamps: {str(e)}")
            return []

    def delete_bootcamp(self, codigo: str) -> Tuple[bool, str]:
        """Elimina un bootcamp por su código."""
        try:
            if self.use_turso:
                check = self._execute_query(
                    "SELECT COUNT(*) as count FROM bootcamps WHERE codigo = ?",
                    (codigo,), fetch_one=True
                )
                if check and int(check.get('count', 0)) > 0:
                    self._execute_query('DELETE FROM bootcamps WHERE codigo = ?', (codigo,))
                    return True, f"Bootcamp {codigo} eliminado"
                return False, f"No se encontró bootcamp {codigo}"
            else:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM bootcamps WHERE codigo = ?', (codigo,))
                rows_affected = cursor.rowcount
                conn.commit()
                conn.close()
                if rows_affected > 0:
                    return True, f"Bootcamp {codigo} eliminado"
                return False, f"No se encontró bootcamp {codigo}"
        except Exception as e:
            return False, f"Error eliminando bootcamp: {str(e)}"

    # =================================================================
    # ESTUDIANTES
    # =================================================================

    def insert_or_update_estudiante(self, estudiante_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Inserta o actualiza un estudiante en la tabla maestra.

        Campos aceptados:
            telefono_e164, nombre (requeridos)
            documento, email, bootcamp_id (int FK), opt_in (0/1), estado_academico
        """
        required_fields = ['telefono_e164', 'nombre']
        for field in required_fields:
            if field not in estudiante_data or not estudiante_data[field]:
                return False, f"Campo requerido faltante: {field}"

        telefono = estudiante_data.get('telefono_e164')
        nombre = estudiante_data.get('nombre')
        documento = estudiante_data.get('documento') or ''
        email = estudiante_data.get('email') or ''
        bootcamp_id = estudiante_data.get('bootcamp_id')  # INTEGER FK or None
        opt_in = 1  # Todos los estudiantes subidos se consideran contactables
        estado_academico = estudiante_data.get('estado_academico') or 'INSCRITO'

        # bootcamp_id puede ser None/empty
        if bootcamp_id is not None and bootcamp_id != '':
            try:
                bootcamp_id = int(bootcamp_id)
            except (ValueError, TypeError):
                bootcamp_id = None
        else:
            bootcamp_id = None

        try:
            query = '''
                INSERT INTO estudiantes (
                    telefono_e164, nombre, documento, email,
                    bootcamp_id, opt_in, estado_academico
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(telefono_e164)
                DO UPDATE SET
                    nombre = excluded.nombre,
                    documento = CASE WHEN excluded.documento != '' THEN excluded.documento ELSE estudiantes.documento END,
                    email = CASE WHEN excluded.email != '' THEN excluded.email ELSE estudiantes.email END,
                    bootcamp_id = COALESCE(excluded.bootcamp_id, estudiantes.bootcamp_id),
                    opt_in = 1,
                    estado_academico = CASE
                        WHEN excluded.estado_academico != 'INSCRITO' THEN excluded.estado_academico
                        ELSE estudiantes.estado_academico
                    END
            '''
            self._execute_query(query, (
                telefono, nombre, documento, email,
                bootcamp_id, opt_in, estado_academico
            ))
            return True, f"Estudiante {nombre} registrado/actualizado"
        except Exception as e:
            return False, f"Error al guardar estudiante: {str(e)}"

    def get_estudiante_by_phone(self, telefono: str) -> List[Dict[str, Any]]:
        """Busca estudiantes por número de teléfono (con JOIN a bootcamp)."""
        try:
            telefono_clean = telefono.replace('+', '').replace(' ', '').replace('-', '')
            query = '''
                SELECT e.*, b.codigo as bootcamp_codigo, b.nombre as bootcamp_nombre,
                       b.modalidad, b.horario, b.lugar,
                       b.fecha_inicio_ingles, b.fecha_fin_ingles, b.fecha_inicio_tecnica
                FROM estudiantes e
                LEFT JOIN bootcamps b ON e.bootcamp_id = b.id
                WHERE REPLACE(REPLACE(REPLACE(e.telefono_e164, '+', ''), ' ', ''), '-', '') = ?
            '''
            return self._execute_query(query, (telefono_clean,), fetch_all=True) or []
        except Exception as e:
            print(f"Error buscando por teléfono: {str(e)}")
            return []

    def get_estudiantes_by_bootcamp(self, bootcamp_id) -> List[Dict[str, Any]]:
        """
        Obtiene estudiantes de un bootcamp.

        Args:
            bootcamp_id: Puede ser int (id) o str (codigo)
        """
        try:
            try:
                bid = int(bootcamp_id)
                query = '''
                    SELECT e.*, b.codigo as bootcamp_codigo, b.nombre as bootcamp_nombre,
                           b.modalidad, b.horario, b.lugar,
                           b.fecha_inicio_ingles, b.fecha_fin_ingles, b.fecha_inicio_tecnica
                    FROM estudiantes e
                    LEFT JOIN bootcamps b ON e.bootcamp_id = b.id
                    WHERE e.bootcamp_id = ?
                    ORDER BY e.nombre
                '''
                return self._execute_query(query, (bid,), fetch_all=True) or []
            except (ValueError, TypeError):
                query = '''
                    SELECT e.*, b.codigo as bootcamp_codigo, b.nombre as bootcamp_nombre,
                           b.modalidad, b.horario, b.lugar,
                           b.fecha_inicio_ingles, b.fecha_fin_ingles, b.fecha_inicio_tecnica
                    FROM estudiantes e
                    JOIN bootcamps b ON e.bootcamp_id = b.id
                    WHERE b.codigo = ?
                    ORDER BY e.nombre
                '''
                return self._execute_query(query, (str(bootcamp_id),), fetch_all=True) or []
        except Exception as e:
            print(f"Error obteniendo estudiantes: {str(e)}")
            return []

    def get_estudiantes_opt_in(self) -> List[Dict[str, Any]]:
        """Obtiene todos los estudiantes (opt_in ya no filtra)."""
        try:
            query = '''
                SELECT e.*, b.codigo as bootcamp_codigo, b.nombre as bootcamp_nombre,
                       b.modalidad, b.horario, b.lugar,
                       b.fecha_inicio_ingles, b.fecha_fin_ingles, b.fecha_inicio_tecnica
                FROM estudiantes e
                LEFT JOIN bootcamps b ON e.bootcamp_id = b.id
                ORDER BY e.id ASC
            '''
            return self._execute_query(query, fetch_all=True) or []
        except Exception as e:
            print(f"Error obteniendo estudiantes: {str(e)}")
            return []

    # Alias para compatibilidad con código existente
    def get_estudiantes_pendientes_envio(self) -> List[Dict[str, Any]]:
        """Alias de get_estudiantes_opt_in (compatibilidad)."""
        return self.get_estudiantes_opt_in()

    def get_estudiantes_sin_campana_enviada(self, tipo: str) -> List[Dict[str, Any]]:
        """
        Obtiene estudiantes que NO tienen una campaña del tipo dado con estado_envio='sent'.

        Útil para evitar enviar dos veces la misma campaña (ej: MATRICULA) al mismo estudiante.

        Args:
            tipo: Tipo de campaña (MATRICULA, EVENTO, INFO)
        """
        try:
            query = '''
                SELECT e.*, b.codigo as bootcamp_codigo, b.nombre as bootcamp_nombre,
                       b.modalidad, b.horario, b.lugar,
                       b.fecha_inicio_ingles, b.fecha_fin_ingles, b.fecha_inicio_tecnica
                FROM estudiantes e
                LEFT JOIN bootcamps b ON e.bootcamp_id = b.id
                WHERE e.id NOT IN (
                    SELECT cm.estudiante_id
                    FROM campana_miembros cm
                    JOIN campanas c ON cm.campana_id = c.id
                    WHERE c.tipo = ?
                      AND cm.estado_envio = 'sent'
                )
                ORDER BY e.id ASC
            '''
            return self._execute_query(query, (tipo.upper(),), fetch_all=True) or []
        except Exception as e:
            print(f"Error obteniendo estudiantes sin campaña enviada: {str(e)}")
            return []

    def get_estudiantes_by_campana(self, campana_id: int) -> List[Dict[str, Any]]:
        """
        Obtiene estudiantes asociados a una campaña (vía campana_miembros).

        Args:
            campana_id: ID de la campaña
        """
        try:
            query = '''
                SELECT e.*, b.codigo as bootcamp_codigo, b.nombre as bootcamp_nombre,
                       b.modalidad, b.horario, b.lugar,
                       b.fecha_inicio_ingles, b.fecha_fin_ingles, b.fecha_inicio_tecnica,
                       cm.estado_envio as cm_estado_envio,
                       cm.respuesta_usuario as cm_respuesta,
                       cm.fecha_envio as cm_fecha_envio
                FROM campana_miembros cm
                JOIN estudiantes e ON cm.estudiante_id = e.id
                LEFT JOIN bootcamps b ON e.bootcamp_id = b.id
                WHERE cm.campana_id = ?
                ORDER BY e.nombre ASC
            '''
            return self._execute_query(query, (campana_id,), fetch_all=True) or []
        except Exception as e:
            print(f"Error obteniendo estudiantes de campaña: {str(e)}")
            return []

    def get_all_estudiantes(self, limit: int = 100, offset: int = 0,
                            campana_id: int = None) -> Tuple[List[Dict[str, Any]], int]:
        """
        Obtiene todos los estudiantes con paginación (JOIN a bootcamp).

        Args:
            limit: Cantidad máxima de registros
            offset: Desplazamiento para paginación
            campana_id: Si se proporciona, filtra solo miembros de esa campaña
        """
        try:
            if campana_id:
                # Filtro por campaña: INNER JOIN con campana_miembros
                total_result = self._execute_query(
                    "SELECT COUNT(*) as total FROM campana_miembros WHERE campana_id = ?",
                    (campana_id,), fetch_one=True
                )
                total = int(total_result.get('total', 0)) if total_result else 0

                query = '''
                    SELECT e.*, b.codigo as bootcamp_codigo, b.nombre as bootcamp_nombre,
                           b.modalidad, b.horario, b.lugar,
                           b.fecha_inicio_ingles, b.fecha_fin_ingles, b.fecha_inicio_tecnica,
                           cm.estado_envio as cm_estado_envio,
                           cm.respuesta_usuario as cm_respuesta,
                           cm.fecha_envio as cm_fecha_envio
                    FROM campana_miembros cm
                    JOIN estudiantes e ON cm.estudiante_id = e.id
                    LEFT JOIN bootcamps b ON e.bootcamp_id = b.id
                    WHERE cm.campana_id = ?
                    ORDER BY e.nombre ASC
                    LIMIT ? OFFSET ?
                '''
                rows = self._execute_query(query, (campana_id, limit, offset), fetch_all=True) or []
                return rows, total
            else:
                # Sin filtro: todos los estudiantes
                total_result = self._execute_query("SELECT COUNT(*) as total FROM estudiantes", fetch_one=True)
                total = int(total_result.get('total', 0)) if total_result else 0

                query = '''
                    SELECT e.*, b.codigo as bootcamp_codigo, b.nombre as bootcamp_nombre,
                           b.modalidad, b.horario, b.lugar,
                           b.fecha_inicio_ingles, b.fecha_fin_ingles, b.fecha_inicio_tecnica
                    FROM estudiantes e
                    LEFT JOIN bootcamps b ON e.bootcamp_id = b.id
                    ORDER BY e.fecha_creacion DESC
                    LIMIT ? OFFSET ?
                '''
                rows = self._execute_query(query, (limit, offset), fetch_all=True) or []
                return rows, total
        except Exception as e:
            print(f"Error obteniendo todos los estudiantes: {str(e)}")
            return [], 0

    def get_estadisticas(self) -> Dict[str, Any]:
        """Estadísticas generales del sistema (modelo normalizado)."""
        try:
            def get_count(query, params=None):
                result = self._execute_query(query, params, fetch_one=True)
                if not result:
                    return 0
                val = list(result.values())[0]
                if isinstance(val, dict):
                    return int(val.get('value', 0))
                return int(val) if val else 0

            total_estudiantes = get_count("SELECT COUNT(*) as c FROM estudiantes")
            total_bootcamps = get_count("SELECT COUNT(*) as c FROM bootcamps")
            total_campanas = get_count("SELECT COUNT(*) as c FROM campanas")

            # Estado académico
            matriculados = get_count("SELECT COUNT(*) as c FROM estudiantes WHERE estado_academico = 'MATRICULADO'")
            inscritos = get_count("SELECT COUNT(*) as c FROM estudiantes WHERE estado_academico = 'INSCRITO'")
            rechazados = get_count("SELECT COUNT(*) as c FROM estudiantes WHERE estado_academico = 'RECHAZADO'")
            graduados = get_count("SELECT COUNT(*) as c FROM estudiantes WHERE estado_academico = 'GRADUADO'")

            # Campañas: mensajes enviados y respuestas
            mensajes_enviados = get_count("SELECT COUNT(*) as c FROM campana_miembros WHERE estado_envio = 'sent'")
            mensajes_error = get_count("SELECT COUNT(*) as c FROM campana_miembros WHERE estado_envio = 'error'")
            total_respuestas = get_count(
                "SELECT COUNT(*) as c FROM campana_miembros WHERE respuesta_usuario IS NOT NULL AND respuesta_usuario != ''"
            )

            return {
                'total_estudiantes': total_estudiantes,
                'total_bootcamps': total_bootcamps,
                'total_campanas': total_campanas,
                'inscritos': inscritos,
                'matriculados': matriculados,
                'rechazados': rechazados,
                'graduados': graduados,
                'mensajes_enviados': mensajes_enviados,
                'mensajes_error': mensajes_error,
                'total_respuestas': total_respuestas,
                'tasa_respuesta': round(total_respuestas / mensajes_enviados * 100, 2) if mensajes_enviados > 0 else 0
            }
        except Exception as e:
            print(f"Error obteniendo estadísticas: {str(e)}")
            return {}

    def get_respuesta_existente(self, telefono: str) -> Tuple[bool, Optional[str]]:
        """
        Verifica si un estudiante ya tiene confirmación de matrícula.

        Revisa: 1) Campaña MATRICULA activa en campana_miembros
                2) estado_academico en estudiantes
        """
        telefono_clean = telefono.replace('+', '').replace(' ', '').replace('-', '')

        try:
            # Opción 1: Verificar en campana_miembros (campaña MATRICULA activa)
            result = self._execute_query('''
                SELECT cm.respuesta_usuario
                FROM campana_miembros cm
                JOIN campanas c ON cm.campana_id = c.id
                JOIN estudiantes e ON cm.estudiante_id = e.id
                WHERE REPLACE(REPLACE(REPLACE(e.telefono_e164, '+', ''), ' ', ''), '-', '') = ?
                  AND c.tipo = 'MATRICULA'
                  AND cm.respuesta_usuario IS NOT NULL AND cm.respuesta_usuario != ''
                ORDER BY cm.fecha_respuesta DESC
                LIMIT 1
            ''', (telefono_clean,), fetch_one=True)

            if result and result.get('respuesta_usuario'):
                return True, result['respuesta_usuario']

            # Opción 2: Verificar estado_academico directamente
            est = self._execute_query('''
                SELECT estado_academico FROM estudiantes
                WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = ?
            ''', (telefono_clean,), fetch_one=True)

            if est:
                estado = str(est.get('estado_academico', 'INSCRITO')).upper()
                if estado == 'MATRICULADO':
                    return True, 'Sí'
                elif estado == 'RECHAZADO':
                    return True, 'No'

            return False, None
        except Exception as e:
            print(f"Error verificando respuesta: {str(e)}")
            return False, None

    def update_respuesta(self, telefono: str, respuesta: str, fecha_respuesta: str) -> Tuple[bool, str]:
        """
        Registra respuesta de matrícula (Sí/No).

        1. Actualiza campana_miembros si hay campaña MATRICULA activa.
        2. Actualiza estudiantes.estado_academico.
        """
        telefono_clean = telefono.replace('+', '').replace(' ', '').replace('-', '')

        # Determinar estado_academico según respuesta
        resp_lower = respuesta.strip().lower()
        if resp_lower in ('sí', 'si', 'yes', 'confirmado'):
            nuevo_estado = 'MATRICULADO'
            respuesta_campana = 'CONFIRMADO'
        elif resp_lower in ('no', 'rechazado'):
            nuevo_estado = 'RECHAZADO'
            respuesta_campana = 'RECHAZADO'
        else:
            nuevo_estado = 'INSCRITO'
            respuesta_campana = respuesta

        def _execute():
            # 1. Actualizar campana_miembros (si existe campaña activa)
            try:
                self._execute_query('''
                    UPDATE campana_miembros
                    SET respuesta_usuario = ?, mensaje_respuesta_raw = ?, fecha_respuesta = ?
                    WHERE estudiante_id IN (
                        SELECT e.id FROM estudiantes e
                        WHERE REPLACE(REPLACE(REPLACE(e.telefono_e164, '+', ''), ' ', ''), '-', '') = ?
                    )
                    AND campana_id IN (
                        SELECT c.id FROM campanas c WHERE c.tipo = 'MATRICULA'
                    )
                    AND (respuesta_usuario IS NULL OR respuesta_usuario = '')
                ''', (respuesta_campana, respuesta, fecha_respuesta, telefono_clean))
            except Exception:
                pass  # No hay campaña activa, está bien

            # 2. Actualizar estado_academico del estudiante
            if self.use_turso:
                check = self._execute_query('''
                    SELECT COUNT(*) as count FROM estudiantes
                    WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = ?
                      AND estado_academico = 'INSCRITO'
                ''', (telefono_clean,), fetch_one=True)
                count = int(check['count']) if check and check.get('count') else 0
                if count > 0:
                    self._execute_query('''
                        UPDATE estudiantes
                        SET estado_academico = ?
                        WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = ?
                          AND estado_academico = 'INSCRITO'
                    ''', (nuevo_estado, telefono_clean))
                    return True, f"Estado actualizado a {nuevo_estado}"
                else:
                    return False, "Estudiante no encontrado o ya tiene respuesta"
            else:
                conn = self._get_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute('''
                        UPDATE estudiantes
                        SET estado_academico = ?
                        WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = ?
                          AND estado_academico = 'INSCRITO'
                    ''', (nuevo_estado, telefono_clean))
                    rows_affected = cursor.rowcount
                    conn.commit()
                    if rows_affected > 0:
                        return True, f"Estado actualizado a {nuevo_estado}"
                    else:
                        return False, "Estudiante no encontrado o ya tiene respuesta"
                finally:
                    conn.close()

        try:
            return self._execute_with_retry(_execute)
        except Exception as e:
            return False, f"Error actualizando respuesta: {str(e)}"

    # =================================================================
    # CRUD FIELDS
    # =================================================================

    def update_estudiante_field(self, telefono: str, field: str, value: Any) -> Tuple[bool, str]:
        """Actualiza un campo específico de un estudiante."""
        allowed_fields = [
            'nombre', 'documento', 'email', 'bootcamp_id',
            'estado_academico'
        ]

        if field not in allowed_fields:
            return False, f"Campo no válido: {field}"

        try:
            telefono_clean = telefono.replace('+', '').replace(' ', '').replace('-', '')
            query = f'''
                UPDATE estudiantes
                SET {field} = ?
                WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = ?
            '''

            if self.use_turso:
                check = self._execute_query(
                    "SELECT COUNT(*) as count FROM estudiantes WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = ?",
                    (telefono_clean,), fetch_one=True
                )
                if check and int(check.get('count', 0)) > 0:
                    self._execute_query(query, (value, telefono_clean))
                    return True, f"Campo '{field}' actualizado exitosamente"
                return False, f"No se encontró estudiante con teléfono {telefono}"
            else:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute(query, (value, telefono_clean))
                rows_affected = cursor.rowcount
                conn.commit()
                conn.close()
                if rows_affected > 0:
                    return True, f"Campo '{field}' actualizado exitosamente"
                return False, f"No se encontró estudiante con teléfono {telefono}"
        except Exception as e:
            return False, f"Error actualizando campo: {str(e)}"

    def update_estudiante_fields(self, telefono: str, fields: Dict[str, Any]) -> Tuple[bool, str]:
        """Actualiza múltiples campos de un estudiante."""
        allowed_fields = [
            'nombre', 'documento', 'email', 'bootcamp_id',
            'estado_academico'
        ]

        invalid_fields = [f for f in fields.keys() if f not in allowed_fields]
        if invalid_fields:
            return False, f"Campos no válidos: {', '.join(invalid_fields)}"
        if not fields:
            return False, "No se especificaron campos para actualizar"

        try:
            telefono_clean = telefono.replace('+', '').replace(' ', '').replace('-', '')
            set_clauses = [f"{field} = ?" for field in fields.keys()]
            set_clause = ", ".join(set_clauses)
            query = f'''
                UPDATE estudiantes SET {set_clause}
                WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = ?
            '''
            values = list(fields.values()) + [telefono_clean]

            if self.use_turso:
                check = self._execute_query(
                    "SELECT COUNT(*) as count FROM estudiantes WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = ?",
                    (telefono_clean,), fetch_one=True
                )
                if check and int(check.get('count', 0)) > 0:
                    self._execute_query(query, tuple(values))
                    return True, f"{len(fields)} campo(s) actualizado(s) exitosamente"
                return False, f"No se encontró estudiante con teléfono {telefono}"
            else:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute(query, values)
                rows_affected = cursor.rowcount
                conn.commit()
                conn.close()
                if rows_affected > 0:
                    return True, f"{len(fields)} campo(s) actualizado(s) exitosamente"
                return False, f"No se encontró estudiante con teléfono {telefono}"
        except Exception as e:
            return False, f"Error actualizando campos: {str(e)}"

    def delete_estudiante(self, telefono: str) -> Tuple[bool, str]:
        """Elimina un estudiante por su teléfono."""
        try:
            telefono_clean = telefono.replace('+', '').replace(' ', '').replace('-', '')

            if self.use_turso:
                check = self._execute_query(
                    "SELECT COUNT(*) as count FROM estudiantes WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = ?",
                    (telefono_clean,), fetch_one=True
                )
                if check and int(check.get('count', 0)) > 0:
                    self._execute_query('''
                        DELETE FROM estudiantes
                        WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = ?
                    ''', (telefono_clean,))
                    return True, "Estudiante eliminado"
                return False, f"No se encontró estudiante con teléfono {telefono}"
            else:
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
                return False, f"No se encontró estudiante con teléfono {telefono}"
        except Exception as e:
            return False, f"Error eliminando estudiante: {str(e)}"

    # =================================================================
    # CAMPAÑAS
    # =================================================================

    def insert_campana(self, nombre: str, tipo: str, plantilla_whatsapp: str = None,
                       bootcamp_objetivo_id: int = None) -> Tuple[bool, Any]:
        """Crea una nueva campaña."""
        if not nombre or not tipo:
            return False, "nombre y tipo son requeridos"

        tipo = tipo.upper()
        if tipo not in ('MATRICULA', 'EVENTO', 'INFO'):
            return False, f"Tipo inválido: {tipo}. Debe ser MATRICULA, EVENTO o INFO"

        # Sanitizar bootcamp_objetivo_id: debe ser int > 0 o None
        if bootcamp_objetivo_id is not None and bootcamp_objetivo_id != '':
            try:
                bootcamp_objetivo_id = int(bootcamp_objetivo_id)
                if bootcamp_objetivo_id <= 0:
                    bootcamp_objetivo_id = None
            except (ValueError, TypeError):
                bootcamp_objetivo_id = None
        else:
            bootcamp_objetivo_id = None

        try:
            query = '''
                INSERT INTO campanas (nombre, tipo, plantilla_whatsapp, bootcamp_objetivo_id, estado)
                VALUES (?, ?, ?, ?, 'DRAFT')
            '''
            campana_id = self._execute_insert(query, (nombre, tipo, plantilla_whatsapp or '', bootcamp_objetivo_id))
            return True, campana_id
        except Exception as e:
            return False, f"Error creando campaña: {str(e)}"

    def get_campana_by_id(self, campana_id: int) -> Optional[Dict[str, Any]]:
        """Obtiene una campaña por su ID."""
        try:
            return self._execute_query("SELECT * FROM campanas WHERE id = ?", (campana_id,), fetch_one=True)
        except Exception as e:
            print(f"Error obteniendo campaña: {str(e)}")
            return None

    def get_all_campanas(self) -> List[Dict[str, Any]]:
        """Obtiene todas las campañas."""
        try:
            return self._execute_query("SELECT * FROM campanas ORDER BY fecha_creacion DESC", fetch_all=True) or []
        except Exception as e:
            print(f"Error listando campañas: {str(e)}")
            return []

    def update_campana_estado(self, campana_id: int, estado: str) -> Tuple[bool, str]:
        """Actualiza el estado de una campaña (DRAFT, SENDING, COMPLETED)."""
        try:
            self._execute_query("UPDATE campanas SET estado = ? WHERE id = ?", (estado, campana_id))
            return True, f"Campaña {campana_id} actualizada a {estado}"
        except Exception as e:
            return False, f"Error actualizando campaña: {str(e)}"

    def insert_campana_miembros(self, campana_id: int, estudiante_ids: List[int],
                                 variables_contexto_list: List[str] = None) -> Tuple[bool, str]:
        """Agrega miembros a una campaña."""
        try:
            for i, est_id in enumerate(estudiante_ids):
                variables = (variables_contexto_list[i]
                             if variables_contexto_list and i < len(variables_contexto_list)
                             else '')
                self._execute_query('''
                    INSERT INTO campana_miembros (campana_id, estudiante_id, variables_contexto, estado_envio)
                    VALUES (?, ?, ?, 'pending')
                ''', (campana_id, est_id, variables))
            return True, f"{len(estudiante_ids)} miembros agregados a campaña {campana_id}"
        except Exception as e:
            return False, f"Error agregando miembros: {str(e)}"

    def get_miembros_pendientes_envio(self, campana_id: int) -> List[Dict[str, Any]]:
        """Obtiene miembros pendientes de envío (JOIN con estudiantes y bootcamps)."""
        try:
            query = '''
                SELECT cm.id as miembro_id, cm.campana_id, cm.estudiante_id,
                       cm.variables_contexto, cm.estado_envio,
                       e.telefono_e164, e.nombre, e.documento,
                       b.codigo as bootcamp_codigo, b.nombre as bootcamp_nombre,
                       b.modalidad, b.horario, b.lugar,
                       b.fecha_inicio_ingles, b.fecha_fin_ingles, b.fecha_inicio_tecnica
                FROM campana_miembros cm
                JOIN estudiantes e ON cm.estudiante_id = e.id
                LEFT JOIN bootcamps b ON e.bootcamp_id = b.id
                WHERE cm.campana_id = ?
                  AND cm.estado_envio = 'pending'
                ORDER BY cm.id ASC
            '''
            return self._execute_query(query, (campana_id,), fetch_all=True) or []
        except Exception as e:
            print(f"Error obteniendo miembros pendientes: {str(e)}")
            return []

    def update_miembro_estado_envio(self, miembro_id: int, estado: str,
                                     message_id: str = None) -> Tuple[bool, str]:
        """Actualiza estado de envío de un miembro de campaña."""
        try:
            self._execute_query('''
                UPDATE campana_miembros
                SET estado_envio = ?, message_id = ?, fecha_envio = ?
                WHERE id = ?
            ''', (estado, message_id or '', datetime.now().isoformat(), miembro_id))
            return True, f"Miembro {miembro_id} actualizado a {estado}"
        except Exception as e:
            return False, f"Error actualizando miembro: {str(e)}"

    def update_miembro_respuesta(self, miembro_id: int, respuesta: str,
                                  raw_text: str = '') -> Tuple[bool, str]:
        """Actualiza la respuesta de un miembro de campaña."""
        try:
            self._execute_query('''
                UPDATE campana_miembros
                SET respuesta_usuario = ?, mensaje_respuesta_raw = ?, fecha_respuesta = ?
                WHERE id = ?
            ''', (respuesta, raw_text, datetime.now().isoformat(), miembro_id))
            return True, f"Respuesta '{respuesta}' registrada para miembro {miembro_id}"
        except Exception as e:
            return False, f"Error actualizando respuesta: {str(e)}"

    def get_campana_activa_for_student(self, estudiante_id: int) -> Optional[Dict[str, Any]]:
        """
        Busca si un estudiante tiene una campaña activa esperando respuesta.
        Prioriza la campaña más reciente con estado_envio='sent' y sin respuesta.
        """
        try:
            query = '''
                SELECT cm.id as miembro_id, cm.campana_id, cm.estudiante_id,
                       cm.estado_envio as miembro_estado_envio,
                       cm.respuesta_usuario, cm.variables_contexto,
                       c.nombre as campana_nombre, c.tipo as campana_tipo,
                       c.plantilla_whatsapp, c.estado as campana_estado
                FROM campana_miembros cm
                JOIN campanas c ON cm.campana_id = c.id
                WHERE cm.estudiante_id = ?
                  AND cm.estado_envio = 'sent'
                  AND (cm.respuesta_usuario IS NULL OR cm.respuesta_usuario = '')
                  AND c.estado IN ('SENDING', 'COMPLETED')
                ORDER BY cm.fecha_envio DESC
                LIMIT 1
            '''
            return self._execute_query(query, (estudiante_id,), fetch_one=True)
        except Exception as e:
            print(f"Error buscando campaña activa: {str(e)}")
            return None

    def get_campana_stats(self, campana_id: int) -> Dict[str, Any]:
        """Obtiene estadísticas de una campaña específica."""
        try:
            def get_count(query, params=None):
                result = self._execute_query(query, params, fetch_one=True)
                if not result:
                    return 0
                val = list(result.values())[0]
                if isinstance(val, dict):
                    return int(val.get('value', 0))
                return int(val) if val else 0

            total = get_count("SELECT COUNT(*) as c FROM campana_miembros WHERE campana_id = ?", (campana_id,))
            enviados = get_count("SELECT COUNT(*) as c FROM campana_miembros WHERE campana_id = ? AND estado_envio = 'sent'", (campana_id,))
            pendientes = get_count("SELECT COUNT(*) as c FROM campana_miembros WHERE campana_id = ? AND estado_envio = 'pending'", (campana_id,))
            errores = get_count("SELECT COUNT(*) as c FROM campana_miembros WHERE campana_id = ? AND estado_envio = 'error'", (campana_id,))
            respondidos = get_count("SELECT COUNT(*) as c FROM campana_miembros WHERE campana_id = ? AND respuesta_usuario IS NOT NULL AND respuesta_usuario != ''", (campana_id,))

            respuestas_detalle = self._execute_query('''
                SELECT respuesta_usuario, COUNT(*) as cantidad
                FROM campana_miembros
                WHERE campana_id = ? AND respuesta_usuario IS NOT NULL AND respuesta_usuario != ''
                GROUP BY respuesta_usuario
            ''', (campana_id,), fetch_all=True) or []

            campana = self.get_campana_by_id(campana_id)

            return {
                'campana_id': campana_id,
                'campana_nombre': campana.get('nombre', '') if campana else '',
                'campana_tipo': campana.get('tipo', '') if campana else '',
                'total_miembros': total,
                'enviados': enviados,
                'pendientes_envio': pendientes,
                'errores_envio': errores,
                'total_respondidos': respondidos,
                'sin_respuesta': enviados - respondidos,
                'tasa_respuesta': round(respondidos / enviados * 100, 2) if enviados > 0 else 0,
                'respuestas_detalle': {r.get('respuesta_usuario', ''): int(r.get('cantidad', 0)) for r in respuestas_detalle}
            }
        except Exception as e:
            print(f"Error obteniendo stats de campaña: {str(e)}")
            return {}

    def delete_campana(self, campana_id: int) -> Tuple[bool, str]:
        """Elimina una campaña y sus miembros."""
        try:
            self._execute_query("DELETE FROM campana_miembros WHERE campana_id = ?", (campana_id,))
            self._execute_query("DELETE FROM campanas WHERE id = ?", (campana_id,))
            return True, f"Campaña {campana_id} eliminada"
        except Exception as e:
            return False, f"Error eliminando campaña: {str(e)}"

    # =================================================================
    # OPERACIONES MASIVAS / RESET
    # =================================================================

    def clear_all_estudiantes(self) -> Tuple[bool, str]:
        """Elimina TODOS los estudiantes. ⚠️ PELIGRO."""
        def _execute():
            with self._lock:
                if self.use_turso:
                    count_result = self._execute_query('SELECT COUNT(*) as total FROM estudiantes', fetch_one=True)
                    if count_result and 'total' in count_result:
                        total_value = count_result['total']
                        count = int(total_value.get('value', 0)) if isinstance(total_value, dict) else int(total_value)
                    else:
                        count = 0
                    self._execute_query('DELETE FROM estudiantes')
                    return True, f"{count} estudiante(s) eliminado(s)"
                else:
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
        """Elimina TODOS los bootcamps. ⚠️ PELIGRO."""
        def _execute():
            with self._lock:
                if self.use_turso:
                    count_result = self._execute_query('SELECT COUNT(*) as total FROM bootcamps', fetch_one=True)
                    if count_result and 'total' in count_result:
                        total_value = count_result['total']
                        count = int(total_value.get('value', 0)) if isinstance(total_value, dict) else int(total_value)
                    else:
                        count = 0
                    self._execute_query('DELETE FROM bootcamps')
                    return True, f"{count} bootcamp(s) eliminado(s)"
                else:
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
        """Elimina TODO el contenido de la base de datos. ⚠️ PELIGRO EXTREMO."""
        try:
            # Primero campana_miembros (FK), luego campanas, luego estudiantes, luego bootcamps
            self._execute_query('DELETE FROM campana_miembros')
            self._execute_query('DELETE FROM campanas')
            success1, msg1 = self.clear_all_estudiantes()
            success2, msg2 = self.clear_all_bootcamps()

            if success1 and success2:
                return True, f"Base de datos vaciada: {msg1}, {msg2}, campañas eliminadas"
            else:
                errors = []
                if not success1:
                    errors.append(msg1)
                if not success2:
                    errors.append(msg2)
                return False, f"Errores: {'; '.join(errors)}"
        except Exception as e:
            return False, f"Error reseteando base de datos: {str(e)}"
