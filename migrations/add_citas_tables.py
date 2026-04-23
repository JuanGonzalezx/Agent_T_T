"""
Migración: Agregar tablas de Citas al sistema.

Este script crea las tablas 'horarios_disponibles' y 'citas'
SIN tocar las tablas existentes (bootcamps, estudiantes, campanas, campana_miembros).

Uso:
    python -m migrations.add_citas_tables

Compatible con Turso (cloud) y SQLite local.
"""

import os
import sys

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def run_migration():
    """Ejecuta la migración para crear las tablas de citas."""
    from app.services.db_handler import DatabaseHandler

    db_path = os.path.join(os.getcwd(), 'data', 'whatsapp_tracking.db')
    db = DatabaseHandler(db_path)

    queries = [
        # ─── horarios_disponibles ───
        # Configuración de slots disponibles para agendar citas
        '''CREATE TABLE IF NOT EXISTS horarios_disponibles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dia_semana INTEGER NOT NULL,
            hora_inicio TEXT NOT NULL,
            hora_fin TEXT NOT NULL,
            duracion_minutos INTEGER DEFAULT 30,
            max_citas_simultaneas INTEGER DEFAULT 1,
            activo INTEGER DEFAULT 1,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''',

        # ─── citas ───
        # Registro de cada cita solicitada/agendada
        '''CREATE TABLE IF NOT EXISTS citas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            estudiante_id INTEGER,
            telefono_e164 TEXT NOT NULL,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            fecha_cita TEXT NOT NULL,
            hora_cita TEXT NOT NULL,
            duracion_minutos INTEGER DEFAULT 30,
            estado TEXT DEFAULT 'PENDIENTE',
            motivo_rechazo TEXT,
            notas_internas TEXT,
            fecha_solicitud TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(estudiante_id) REFERENCES estudiantes(id)
        )''',

        # ─── índices citas ───
        'CREATE INDEX IF NOT EXISTS idx_citas_estado ON citas(estado)',
        'CREATE INDEX IF NOT EXISTS idx_citas_telefono ON citas(telefono_e164)',
        'CREATE INDEX IF NOT EXISTS idx_citas_fecha ON citas(fecha_cita)',
        'CREATE INDEX IF NOT EXISTS idx_horarios_dia ON horarios_disponibles(dia_semana)',
    ]

    print("=" * 60)
    print("🔄 Migración: Agregando tablas de Citas")
    print("=" * 60)

    if db.use_turso:
        print(f"📡 Conectado a Turso: {db.turso_url}")
        for i, query in enumerate(queries):
            try:
                db._execute_turso_query(query)
                print(f"  ✅ Query {i+1}/{len(queries)} ejecutada")
            except Exception as e:
                print(f"  ⚠️  Query {i+1} (ya existe o error): {e}")
    else:
        print(f"💾 Usando SQLite local: {db.db_path}")
        import sqlite3
        conn = sqlite3.connect(db.db_path, timeout=30.0)
        cursor = conn.cursor()
        for i, query in enumerate(queries):
            try:
                cursor.execute(query)
                print(f"  ✅ Query {i+1}/{len(queries)} ejecutada")
            except Exception as e:
                print(f"  ⚠️  Query {i+1} (ya existe o error): {e}")
        conn.commit()
        conn.close()

    print("=" * 60)
    print("✅ Migración completada exitosamente")
    print("   Tablas creadas: horarios_disponibles, citas")
    print("   Tablas existentes: NO fueron modificadas")
    print("=" * 60)


if __name__ == '__main__':
    run_migration()
