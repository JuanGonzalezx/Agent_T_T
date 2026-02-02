# Database Schema

## WhatsApp Messaging API - Talento Tech

Documentación del esquema de base de datos Turso/SQLite.

---

## Diagrama ER

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              BOOTCAMPS                                   │
├─────────────────────────────────────────────────────────────────────────┤
│  PK  │ id                 │ TEXT       │ Identificador único            │
│      │ nombre             │ TEXT       │ Nombre del bootcamp            │
│      │ fecha_creacion     │ TIMESTAMP  │ Fecha de registro              │
│      │ fecha_actualizacion│ TIMESTAMP  │ Última modificación            │
└──────┴────────────────────┴────────────┴────────────────────────────────┘
                                    │
                                    │ 1:N
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                             ESTUDIANTES                                  │
├─────────────────────────────────────────────────────────────────────────┤
│  PK  │ id                 │ INTEGER    │ Auto-increment                 │
│  UK  │ telefono_e164      │ TEXT       │ Teléfono formato E.164         │
│      │ nombre             │ TEXT       │ Nombre completo                │
│  FK  │ bootcamp_id        │ TEXT       │ Referencia a bootcamp          │
│      │ bootcamp_nombre    │ TEXT       │ Nombre del bootcamp (cache)    │
│      │ modalidad          │ TEXT       │ Presencial/Virtual/Híbrido     │
│      │ ingles_inicio      │ TEXT       │ Fecha inicio inglés            │
│      │ ingles_fin         │ TEXT       │ Fecha fin inglés               │
│      │ inicio_formacion   │ TEXT       │ Fecha inicio formación técnica │
│      │ horario            │ TEXT       │ Horario de clases              │
│      │ lugar              │ TEXT       │ Sede/ubicación                 │
│      │ opt_in             │ TEXT       │ Consentimiento (TRUE/FALSE)    │
│      │ estado_envio       │ TEXT       │ sent/error/pending             │
│      │ fecha_envio        │ TEXT       │ Timestamp del envío            │
│      │ message_id         │ TEXT       │ ID de mensaje WhatsApp         │
│      │ respuesta          │ TEXT       │ Si/No/default                  │
│      │ fecha_respuesta    │ TEXT       │ Timestamp de la respuesta      │
│      │ fecha_creacion     │ TIMESTAMP  │ Fecha de registro              │
│      │ fecha_actualizacion│ TIMESTAMP  │ Última modificación            │
└──────┴────────────────────┴────────────┴────────────────────────────────┘
```

---

## DDL (Data Definition Language)

### Tabla: bootcamps

```sql
CREATE TABLE IF NOT EXISTS bootcamps (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Tabla: estudiantes

```sql
CREATE TABLE IF NOT EXISTS estudiantes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telefono_e164 TEXT UNIQUE NOT NULL,
    nombre TEXT,
    bootcamp_id TEXT,
    bootcamp_nombre TEXT,
    modalidad TEXT,
    ingles_inicio TEXT,
    ingles_fin TEXT,
    inicio_formacion TEXT,
    horario TEXT,
    lugar TEXT,
    opt_in TEXT DEFAULT 'FALSE',
    estado_envio TEXT DEFAULT '',
    fecha_envio TEXT,
    message_id TEXT,
    respuesta TEXT DEFAULT 'default',
    fecha_respuesta TEXT,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bootcamp_id) REFERENCES bootcamps(id)
);
```

### Índices

```sql
-- Índice para búsquedas por teléfono
CREATE INDEX IF NOT EXISTS idx_estudiantes_telefono 
ON estudiantes(telefono_e164);

-- Índice para filtrar por bootcamp
CREATE INDEX IF NOT EXISTS idx_estudiantes_bootcamp 
ON estudiantes(bootcamp_id);

-- Índice para filtrar por estado de envío
CREATE INDEX IF NOT EXISTS idx_estudiantes_estado 
ON estudiantes(estado_envio);

-- Índice para filtrar por respuesta
CREATE INDEX IF NOT EXISTS idx_estudiantes_respuesta 
ON estudiantes(respuesta);
```

---

## Descripción de Campos

### Tabla: bootcamps

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | TEXT | Identificador único del bootcamp (ej: "BT001") |
| `nombre` | TEXT | Nombre descriptivo (ej: "Inteligencia Artificial") |
| `fecha_creacion` | TIMESTAMP | Cuándo se registró el bootcamp |
| `fecha_actualizacion` | TIMESTAMP | Última modificación del registro |

### Tabla: estudiantes

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | INTEGER | ID auto-incremental |
| `telefono_e164` | TEXT | Teléfono en formato E.164 (ej: "+573001234567") |
| `nombre` | TEXT | Nombre completo del estudiante |
| `bootcamp_id` | TEXT | FK al bootcamp asignado |
| `bootcamp_nombre` | TEXT | Nombre del bootcamp (desnormalizado para consultas rápidas) |
| `modalidad` | TEXT | "Presencial", "Virtual" o "Híbrido" |
| `ingles_inicio` | TEXT | Fecha de inicio de inglés |
| `ingles_fin` | TEXT | Fecha de fin de inglés |
| `inicio_formacion` | TEXT | Fecha de inicio de formación técnica |
| `horario` | TEXT | Horario de clases |
| `lugar` | TEXT | Sede o ubicación |
| `opt_in` | TEXT | "TRUE" si consintió recibir mensajes |
| `estado_envio` | TEXT | "sent", "error", "" (pendiente) |
| `fecha_envio` | TEXT | ISO timestamp del envío |
| `message_id` | TEXT | ID del mensaje de WhatsApp (wamid.xxx) |
| `respuesta` | TEXT | "Si", "No", "default" (sin responder) |
| `fecha_respuesta` | TEXT | ISO timestamp de la respuesta |
| `fecha_creacion` | TIMESTAMP | Cuándo se creó el registro |
| `fecha_actualizacion` | TIMESTAMP | Última modificación |

---

## Valores Especiales

### Campo: opt_in

| Valor | Significado |
|-------|-------------|
| `TRUE` | Estudiante acepta recibir mensajes |
| `FALSE` | Estudiante NO acepta mensajes |
| `1`, `SI`, `YES` | Tratados como TRUE |

### Campo: estado_envio

| Valor | Significado |
|-------|-------------|
| `""` (vacío) | Pendiente de envío |
| `sent` | Mensaje enviado exitosamente |
| `error` | Error al enviar el mensaje |

### Campo: respuesta

| Valor | Significado |
|-------|-------------|
| `default` | Sin respuesta aún |
| `Si` | Estudiante confirmó asistencia |
| `No` | Estudiante rechazó |

---

## Queries Comunes

### Estudiantes pendientes de envío

```sql
SELECT * FROM estudiantes
WHERE UPPER(opt_in) IN ('TRUE', '1', 'YES', 'SI')
  AND (estado_envio IS NULL OR estado_envio = '' OR estado_envio != 'sent')
ORDER BY id ASC;
```

### Estudiantes que no han respondido

```sql
SELECT * FROM estudiantes
WHERE estado_envio = 'sent'
  AND (respuesta IS NULL OR respuesta = '' OR LOWER(respuesta) = 'default')
ORDER BY fecha_envio DESC;
```

### Estadísticas por bootcamp

```sql
SELECT 
    bootcamp_id,
    bootcamp_nombre,
    COUNT(*) as total,
    SUM(CASE WHEN estado_envio = 'sent' THEN 1 ELSE 0 END) as enviados,
    SUM(CASE WHEN LOWER(respuesta) = 'si' THEN 1 ELSE 0 END) as confirmados,
    SUM(CASE WHEN LOWER(respuesta) = 'no' THEN 1 ELSE 0 END) as rechazados
FROM estudiantes
GROUP BY bootcamp_id, bootcamp_nombre
ORDER BY total DESC;
```

### Buscar por teléfono (normalizado)

```sql
SELECT * FROM estudiantes
WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = '573001234567';
```

### Actualizar respuesta

```sql
UPDATE estudiantes
SET respuesta = 'Si',
    fecha_respuesta = '2026-02-01T10:30:00',
    fecha_actualizacion = CURRENT_TIMESTAMP
WHERE REPLACE(REPLACE(REPLACE(telefono_e164, '+', ''), ' ', ''), '-', '') = '573001234567'
  AND (respuesta IS NULL OR respuesta = '' OR LOWER(respuesta) = 'default');
```

---

## Migración de Datos

### Desde CSV a Turso

```python
import pandas as pd
from services.db_handler import DatabaseHandler

# Cargar CSV
df = pd.read_csv('bd_envio.csv')

# Inicializar handler
db = DatabaseHandler()

# Insertar cada estudiante
for _, row in df.iterrows():
    estudiante = {
        'telefono_e164': row['telefono_e164'],
        'nombre': row['nombre'],
        'bootcamp_id': row['bootcamp_id'],
        # ... resto de campos
    }
    db.insert_or_update_estudiante(estudiante)
```

### Backup a CSV

```python
estudiantes = db.get_all_estudiantes()
df = pd.DataFrame(estudiantes)
df.to_csv('backup_estudiantes.csv', index=False)
```

---

## Conexión a Turso

### Desde Python

```python
from services.db_handler import DatabaseHandler

# Automáticamente usa Turso si están configuradas las variables:
# - TURSO_DATABASE_URL
# - TURSO_AUTH_TOKEN

db = DatabaseHandler()

# Verificar modo
print(f"Usando Turso: {db.use_turso}")
```

### Desde CLI

```bash
# Instalar Turso CLI
curl -sSfL https://get.turso.tech/install.sh | bash

# Conectar a la base de datos
turso db shell whatsapp-tracking

# Ejecutar queries
.tables
SELECT COUNT(*) FROM estudiantes;
```

---

## Consideraciones de Rendimiento

1. **Índices**: Asegurar que existan índices para campos frecuentemente consultados
2. **Desnormalización**: `bootcamp_nombre` está duplicado para evitar JOINs
3. **Paginación**: Usar LIMIT/OFFSET para consultas grandes
4. **Caché**: Turso tiene caché automático a nivel edge

---

## Respaldo y Recuperación

### Turso CLI

```bash
# Crear snapshot
turso db snapshot create whatsapp-tracking

# Listar snapshots
turso db snapshot list whatsapp-tracking

# Restaurar desde snapshot
turso db snapshot restore whatsapp-tracking <snapshot-id>
```

### Export/Import

```bash
# Exportar a SQLite local
turso db shell whatsapp-tracking ".dump" > backup.sql

# Importar desde archivo
turso db shell whatsapp-tracking < backup.sql
```
