"""
Script para recrear la base de datos SQLite desde cero.

Este script:
1. Elimina la base de datos existente
2. Crea una nueva base de datos limpia
3. Carga los datos del CSV actual a SQLite
"""

import os
import pandas as pd
from services.db_handler import DatabaseHandler

def recreate_database():
    print("🔄 Recreando base de datos SQLite...")
    print("=" * 70)
    
    # 1. Eliminar base de datos existente
    db_path = "whatsapp_tracking.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"✅ Base de datos antigua eliminada: {db_path}")
    else:
        print(f"ℹ️  No existía base de datos anterior")
    
    # 2. Crear nueva base de datos
    print("\n📦 Creando nueva base de datos...")
    db = DatabaseHandler(db_path)
    print("✅ Base de datos creada con tablas: estudiantes, bootcamps")
    
    # 3. Cargar datos del CSV
    csv_path = "bd_envio.csv"
    if not os.path.exists(csv_path):
        print(f"⚠️  No se encontró {csv_path}")
        return
    
    print(f"\n📂 Cargando datos desde {csv_path}...")
    df = pd.read_csv(csv_path)
    print(f"   Total registros en CSV: {len(df)}")
    print(f"   Columnas: {', '.join(df.columns.tolist())}")
    
    # 4. Registrar bootcamps únicos
    print("\n🏫 Registrando bootcamps...")
    bootcamp_ids = df['bootcamp_id'].dropna().unique()
    bootcamp_count = 0
    
    for bootcamp_id in bootcamp_ids:
        if bootcamp_id and str(bootcamp_id).strip():
            bootcamp_row = df[df['bootcamp_id'] == bootcamp_id].iloc[0]
            bootcamp_nombre = bootcamp_row.get('bootcamp_nombre', '')
            
            success, msg = db.insert_or_update_bootcamp(
                str(bootcamp_id), 
                str(bootcamp_nombre)
            )
            if success:
                print(f"   ✓ {bootcamp_id} - {bootcamp_nombre}")
                bootcamp_count += 1
            else:
                print(f"   ✗ Error: {msg}")
    
    print(f"\n✅ {bootcamp_count} bootcamp(s) registrado(s)")
    
    # 5. Registrar estudiantes
    print("\n👥 Registrando estudiantes...")
    success_count = 0
    error_count = 0
    
    for idx, row in df.iterrows():
        estudiante_data = {
            'telefono_e164': str(row.get('telefono_e164', '')),
            'nombre': str(row.get('nombre', '')),
            'bootcamp_id': str(row.get('bootcamp_id', '')),
            'bootcamp_nombre': str(row.get('bootcamp_nombre', '')),
            'modalidad': str(row.get('modalidad', '')),
            'ingles_inicio': str(row.get('ingles_inicio', '')),
            'ingles_fin': str(row.get('ingles_fin', '')),
            'inicio_formacion': str(row.get('inicio_formacion', '')),
            'horario': str(row.get('horario', '')),
            'lugar': str(row.get('lugar', '')),
            'opt_in': str(row.get('opt_in', '')),
            'estado_envio': str(row.get('estado_envio', '')),
            'fecha_envio': row.get('fecha_envio', None),
            'message_id': str(row.get('message_id', '')),
            'respuesta': str(row.get('respuesta', '')) if pd.notna(row.get('respuesta')) else '',
            'fecha_respuesta': row.get('fecha_respuesta', None)
        }
        
        success, msg = db.insert_or_update_estudiante(estudiante_data)
        if success:
            success_count += 1
            print(f"   ✓ {estudiante_data['telefono_e164']} - {estudiante_data['nombre']}")
        else:
            error_count += 1
            print(f"   ✗ {estudiante_data['telefono_e164']}: {msg}")
    
    print(f"\n✅ {success_count} estudiante(s) registrado(s)")
    if error_count > 0:
        print(f"⚠️  {error_count} error(es)")
    
    # 6. Verificar datos cargados
    print("\n📊 Verificación final:")
    bootcamps = db.get_all_bootcamps()
    estudiantes, total = db.get_all_estudiantes()
    stats = db.get_estadisticas()
    
    print(f"   Bootcamps en DB: {len(bootcamps)}")
    for bc in bootcamps:
        print(f"     - {bc['bootcamp_id']}: {bc['bootcamp_nombre']}")
    
    print(f"\n   Estudiantes en DB: {total}")
    print(f"   Mensajes enviados: {stats.get('mensajes_enviados', 0)}")
    print(f"   Confirmaron Sí: {stats.get('confirmaron_si', 0)}")
    print(f"   Confirmaron No: {stats.get('confirmaron_no', 0)}")
    print(f"   Pendientes: {stats.get('pendientes_respuesta', 0)}")
    
    print("\n" + "=" * 70)
    print("✅ Base de datos recreada exitosamente!")
    print(f"\nArchivo: {db_path}")
    print("\n💡 Ahora puedes iniciar el servidor con: python app.py")

if __name__ == "__main__":
    recreate_database()
