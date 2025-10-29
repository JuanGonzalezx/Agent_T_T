# API de Consultas SQLite - Documentación

## Base de Datos SQLite

El sistema utiliza SQLite como persistencia local para evitar dependencias de sincronización con Google Drive.

### Archivo de Base de Datos
- **Archivo**: `whatsapp_tracking.db` (en la raíz del proyecto)
- **Motor**: SQLite3 (incluido en Python)
- **Estructura**: 2 tablas principales con índices optimizados

---

## Tablas de la Base de Datos

### Tabla: `bootcamps`
Catálogo de bootcamps disponibles.

| Columna           | Tipo      | Descripción                          |
|-------------------|-----------|--------------------------------------|
| id                | INTEGER   | ID autoincremental (PK)              |
| bootcamp_id       | TEXT      | Código único del bootcamp (UNIQUE)   |
| bootcamp_nombre   | TEXT      | Nombre del bootcamp                  |
| fecha_creacion    | TIMESTAMP | Fecha de creación del registro       |

### Tabla: `estudiantes`
Información completa de estudiantes y sus respuestas.

| Columna              | Tipo      | Descripción                               |
|----------------------|-----------|-------------------------------------------|
| id                   | INTEGER   | ID autoincremental (PK)                   |
| telefono_e164        | TEXT      | Número de teléfono en formato E.164       |
| nombre               | TEXT      | Nombre completo del estudiante            |
| bootcamp_id          | TEXT      | Código del bootcamp                       |
| bootcamp_nombre      | TEXT      | Nombre del bootcamp                       |
| modalidad            | TEXT      | Virtual/Presencial/Híbrido                |
| ingles_inicio        | TEXT      | Fecha inicio inglés                       |
| ingles_fin           | TEXT      | Fecha fin inglés                          |
| inicio_formacion     | TEXT      | Fecha inicio formación                    |
| horario              | TEXT      | Horario de clases                         |
| lugar                | TEXT      | Ubicación física o virtual                |
| opt_in               | TEXT      | Estado de opt-in                          |
| estado_envio         | TEXT      | sent/error/pending                        |
| fecha_envio          | TIMESTAMP | Fecha y hora del envío                    |
| message_id           | TEXT      | ID del mensaje de WhatsApp                |
| respuesta            | TEXT      | Sí/No/null                                |
| fecha_respuesta      | TIMESTAMP | Fecha y hora de la respuesta              |
| fecha_creacion       | TIMESTAMP | Fecha de creación del registro            |
| fecha_actualizacion  | TIMESTAMP | Fecha de última actualización             |

**Índices**:
- `idx_estudiantes_telefono` (telefono_e164)
- `idx_estudiantes_bootcamp` (bootcamp_id)
- `idx_estudiantes_fecha_envio` (fecha_envio)
- `idx_estudiantes_respuesta` (respuesta)

**Constraint**: UNIQUE(telefono_e164, bootcamp_id)

---

## Endpoints de Consulta

### 1. Obtener Todos los Estudiantes
**GET** `/api/estudiantes/all`

Obtiene todos los estudiantes con paginación.

**Query Parameters**:
- `limit` (int, opcional): Número máximo de registros. Default: 100
- `offset` (int, opcional): Número de registros a saltar. Default: 0

**Ejemplo**:
```bash
GET /api/estudiantes/all?limit=50&offset=0
```

**Respuesta Exitosa (200)**:
```json
{
  "success": true,
  "total": 150,
  "limit": 50,
  "offset": 0,
  "count": 50,
  "estudiantes": [
    {
      "id": 1,
      "telefono_e164": "+573001234567",
      "nombre": "Juan Pérez",
      "bootcamp_id": "IA_2024_01",
      "bootcamp_nombre": "Inteligencia Artificial",
      "modalidad": "Virtual",
      "estado_envio": "sent",
      "fecha_envio": "2024-01-15 10:30:00",
      "respuesta": "Sí",
      "fecha_respuesta": "2024-01-15 11:00:00"
    }
  ]
}
```

---

### 2. Filtrar por Bootcamp
**GET** `/api/estudiantes/bootcamp/<bootcamp_id>`

Obtiene todos los estudiantes de un bootcamp específico.

**Path Parameters**:
- `bootcamp_id` (string): Código del bootcamp

**Ejemplo**:
```bash
GET /api/estudiantes/bootcamp/IA_2024_01
```

**Respuesta Exitosa (200)**:
```json
{
  "success": true,
  "bootcamp_id": "IA_2024_01",
  "count": 25,
  "estudiantes": [...]
}
```

---

### 3. Buscar por Teléfono
**GET** `/api/estudiantes/phone/<phone>`

Busca todos los registros de un estudiante por su número de teléfono.

**Path Parameters**:
- `phone` (string): Número de teléfono (puede incluir o no el +)

**Ejemplo**:
```bash
GET /api/estudiantes/phone/573001234567
GET /api/estudiantes/phone/+573001234567
```

**Respuesta Exitosa (200)**:
```json
{
  "success": true,
  "phone": "+573001234567",
  "count": 2,
  "estudiantes": [
    {
      "id": 1,
      "telefono_e164": "+573001234567",
      "nombre": "Juan Pérez",
      "bootcamp_id": "IA_2024_01",
      "bootcamp_nombre": "Inteligencia Artificial"
    },
    {
      "id": 45,
      "telefono_e164": "+573001234567",
      "nombre": "Juan Pérez",
      "bootcamp_id": "DS_2024_02",
      "bootcamp_nombre": "Data Science"
    }
  ]
}
```

---

### 4. Filtrar por Rango de Fechas
**GET** `/api/estudiantes/date-range`

Obtiene estudiantes filtrados por rango de fechas de envío.

**Query Parameters**:
- `fecha_inicio` (string, opcional): Fecha inicial (YYYY-MM-DD)
- `fecha_fin` (string, opcional): Fecha final (YYYY-MM-DD)

**Ejemplos**:
```bash
# Desde una fecha
GET /api/estudiantes/date-range?fecha_inicio=2024-01-01

# Hasta una fecha
GET /api/estudiantes/date-range?fecha_fin=2024-01-31

# Rango completo
GET /api/estudiantes/date-range?fecha_inicio=2024-01-01&fecha_fin=2024-01-31
```

**Respuesta Exitosa (200)**:
```json
{
  "success": true,
  "fecha_inicio": "2024-01-01",
  "fecha_fin": "2024-01-31",
  "count": 75,
  "estudiantes": [...]
}
```

---

### 5. Listar Bootcamps
**GET** `/api/bootcamps`

Obtiene el catálogo completo de bootcamps registrados.

**Uso**: Este endpoint es ideal para poblar dropdowns en el frontend.

**Ejemplo**:
```bash
GET /api/bootcamps
```

**Respuesta Exitosa (200)**:
```json
{
  "success": true,
  "count": 4,
  "bootcamps": [
    {
      "bootcamp_id": "DS_2024_01",
      "bootcamp_nombre": "Data Science",
      "fecha_creacion": "2024-01-10 08:00:00"
    },
    {
      "bootcamp_id": "IA_2024_01",
      "bootcamp_nombre": "Inteligencia Artificial",
      "fecha_creacion": "2024-01-10 08:00:00"
    }
  ]
}
```

---

### 6. Estadísticas del Sistema
**GET** `/api/estadisticas`

Obtiene métricas generales del sistema de mensajería.

**Ejemplo**:
```bash
GET /api/estadisticas
```

**Respuesta Exitosa (200)**:
```json
{
  "success": true,
  "estadisticas": {
    "total_estudiantes": 150,
    "mensajes_enviados": 150,
    "mensajes_error": 0,
    "confirmaron_si": 120,
    "confirmaron_no": 15,
    "pendientes_respuesta": 15,
    "total_bootcamps": 4,
    "tasa_respuesta": 90.0
  }
}
```

**Métricas incluidas**:
- `total_estudiantes`: Total de registros en la base de datos
- `mensajes_enviados`: Mensajes con estado "sent"
- `mensajes_error`: Mensajes con estado "error"
- `confirmaron_si`: Estudiantes que respondieron "Sí"
- `confirmaron_no`: Estudiantes que respondieron "No"
- `pendientes_respuesta`: Enviados pero sin respuesta aún
- `total_bootcamps`: Número de bootcamps registrados
- `tasa_respuesta`: Porcentaje de respuestas (Sí+No) / enviados

---

## Flujo de Sincronización

### CSV ↔ SQLite

El sistema mantiene **dual-write** para máxima confiabilidad:

1. **Carga desde Drive** (`/api/google/upload`):
   - Descarga archivo de Google Drive
   - Normaliza datos y agrega columnas de tracking
   - Guarda en `bd_envio.csv`
   - **Popular SQLite**: Registra bootcamps y estudiantes
   - Actualiza archivo en Drive

2. **Envío Masivo** (`/api/messages/send-batch`):
   - Lee contactos pendientes del CSV
   - Envía mensajes por WhatsApp
   - Actualiza estado en CSV
   - **Actualiza SQLite**: Guarda estado de envío y message_id

3. **Webhook** (`/webhook`):
   - Recibe respuestas de WhatsApp (Sí/No)
   - Actualiza respuesta en CSV
   - **Actualiza SQLite**: Guarda respuesta y fecha
   - Marca cambios para sync con Drive

---

## Manejo de Errores

Todos los endpoints retornan el siguiente formato en caso de error:

**Error (400/500)**:
```json
{
  "success": false,
  "error": "Descripción del error"
}
```

---

## Consideraciones de Rendimiento

### Índices Optimizados
Los índices se crean automáticamente para optimizar las consultas más frecuentes:
- Búsqueda por teléfono (muy común en webhooks)
- Filtrado por bootcamp (para reportes)
- Ordenamiento por fecha de envío
- Filtrado por estado de respuesta

### Paginación
El endpoint `/api/estudiantes/all` implementa paginación para evitar sobrecarga con grandes datasets.

### Transacciones
Todas las operaciones de escritura utilizan transacciones ACID de SQLite para garantizar consistencia.

---

## Pruebas

Para verificar el funcionamiento de la base de datos, ejecuta:

```bash
python test_db.py
```

Este script realiza pruebas de:
- Inserción de bootcamps
- Inserción de estudiantes
- Consultas por bootcamp, teléfono y fechas
- Actualización de respuestas
- Cálculo de estadísticas
- Manejo de duplicados (UPSERT)

---

## Migración de Datos Existentes

Si ya tienes datos en `bd_envio.csv`, puedes cargarlos a SQLite mediante:

1. **Método recomendado**: Usar el endpoint `/api/google/upload` con tu archivo actual
2. **Método alternativo**: Script Python personalizado

```python
from services.db_handler import DatabaseHandler
import pandas as pd

db = DatabaseHandler()
df = pd.read_csv('bd_envio.csv')

for _, row in df.iterrows():
    estudiante_data = {
        'telefono_e164': row['telefono_e164'],
        'nombre': row['nombre'],
        'bootcamp_id': row['bootcamp_id'],
        # ... resto de campos
    }
    db.insert_or_update_estudiante(estudiante_data)
```

---

## Notas de Implementación

### ¿Por qué SQLite?
- ✅ No requiere servidor externo (archivo local)
- ✅ Transacciones ACID
- ✅ Consultas SQL completas
- ✅ Altamente optimizado para lecturas
- ✅ Incluido en Python (sin instalación)
- ✅ Perfecto para despliegue en Render con volumen persistente

### Limitaciones
- ⚠️ No soporta múltiples escritores concurrentes
- ⚠️ Limitado a ~1TB de datos (más que suficiente para este caso)

### Backup
El archivo `whatsapp_tracking.db` debe incluirse en los backups regulares del sistema junto con `bd_envio.csv`.
