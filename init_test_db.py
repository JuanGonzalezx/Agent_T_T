"""
Script para inicializar las tablas en la base de datos de test (Turso).

Uso:
    python init_test_db.py

Requisitos:
    - Token con permisos de escritura (rw/full), NO read-only.
    - Si el token actual es read-only, genera uno nuevo:
        turso db tokens create agenttest --permission full
"""

import os
import sys

# ─── Configuración de la DB de test ───
# Sobreescribir las variables de entorno ANTES de importar DatabaseHandler
os.environ['TURSO_DATABASE_URL'] = 'libsql://agenttest-juangonzalezx.aws-us-west-2.turso.io'
os.environ['TURSO_AUTH_TOKEN'] = 'eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3NzI1NDM1ODMsImlkIjoiMDE5Y2IzYTQtMmYwMS03NTU5LTlkNzYtMTAxOWY5MjQ3OWY3IiwicmlkIjoiYmNkZjc4MDEtYjllYi00NTQ5LWFmMGUtZTc1MTVlODA0ZjU3In0.XrH_oIQfmTh-8t11_-YWSbQ9CKujhF87KKA95sOUD9LLWo5XKGGdChgFouQnVIC0_UlZQp77hX1gj3XoNk7PBw'

# ⚠️  CAMBIA EL TOKEN DE ARRIBA POR UNO CON PERMISOS DE ESCRITURA (rw/full)
# El token actual es read-only (ro) y NO podrá crear tablas.

# Importar DatabaseHandler directamente sin pasar por app/__init__.py
# (que requiere apscheduler y otras dependencias no necesarias aquí)
import importlib.util

_root = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "db_handler", os.path.join(_root, "app", "services", "db_handler.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
DatabaseHandler = _mod.DatabaseHandler


def main():
    print("=" * 60)
    print("  Inicializando DB de test en Turso")
    print("=" * 60)
    print(f"  URL: {os.environ['TURSO_DATABASE_URL']}")
    print(f"  Token: ...{os.environ['TURSO_AUTH_TOKEN'][-20:]}")
    print()

    try:
        # Al instanciar DatabaseHandler, _init_database() crea las 4 tablas:
        #   - bootcamps
        #   - estudiantes
        #   - campanas
        #   - campana_miembros (con UNIQUE index campana_id + estudiante_id)
        db = DatabaseHandler()

        print("[OK] Tablas creadas exitosamente.")
        print()

        # Verificar que las tablas existan
        print("  Verificando tablas...")
        for tabla in ['bootcamps', 'estudiantes', 'campanas', 'campana_miembros']:
            try:
                result = db._execute_query(f"SELECT COUNT(*) as total FROM {tabla}", fetch_one=True)
                count = result.get('total', 0) if result else 0
                # Manejar el formato Turso {type: ..., value: ...}
                if isinstance(count, dict):
                    count = count.get('value', 0)
                print(f"    ✓ {tabla}: {count} registros")
            except Exception as e:
                print(f"    ✗ {tabla}: ERROR - {e}")

        print()
        print("[LISTO] Base de datos de test inicializada correctamente.")

    except Exception as e:
        print(f"[ERROR] No se pudo inicializar la DB: {e}")
        print()
        if "read" in str(e).lower() or "authorization" in str(e).lower() or "403" in str(e):
            print("  → El token probablemente es read-only.")
            print("  → Genera uno con permisos de escritura:")
            print("       turso db tokens create agenttest --permission full")
        sys.exit(1)


if __name__ == '__main__':
    main()
