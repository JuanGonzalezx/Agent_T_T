# API de Consultas SQLite - Documentación

## Resumen de Endpoints

| Método | Endpoint | Descripción | Tipo |
|--------|----------|-------------|------|
| **GET** | `/api/estudiantes/all` | Listar todos los estudiantes (paginado) | Consulta |
| **GET** | `/api/estudiantes/bootcamp/<id>` | Filtrar por bootcamp | Consulta |
| **GET** | `/api/estudiantes/phone/<phone>` | Buscar por teléfono | Consulta |
| **GET** | `/api/estudiantes/date-range` | Filtrar por rango de fechas | Consulta |
| **GET** | `/api/bootcamps` | Listar todos los bootcamps | Consulta |
| **GET** | `/api/estadisticas` | Estadísticas del sistema | Consulta |
| **PUT** | `/api/estudiantes/update-field` | Actualizar 1 campo | CRUD |
| **PUT** | `/api/estudiantes/update-fields` | Actualizar múltiples campos | CRUD |
| **DELETE** | `/api/estudiantes/delete/<phone>` | Eliminar estudiante | CRUD |
| **DELETE** | `/api/bootcamps/delete/<id>` | Eliminar bootcamp | CRUD |
| **DELETE** | `/api/estudiantes/clear-all` | ⚠️ Vaciar tabla estudiantes | CRUD |
| **DELETE** | `/api/bootcamps/clear-all` | ⚠️ Vaciar tabla bootcamps | CRUD |
| **DELETE** | `/api/database/reset` | ⚠️ Resetear base de datos completa | CRUD |

---

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

**Constraint**: UNIQUE(telefono_e164) - Un teléfono solo puede tener un registro

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

## Endpoints CRUD - Editar y Eliminar

### 7. Actualizar UN Campo de Estudiante
**PUT** `/api/estudiantes/update-field`

Actualiza un solo campo de un estudiante identificado por su teléfono.

**Request Body**:
```json
{
  "telefono": "+573001234567",
  "field": "nombre",
  "value": "Juan Pérez Actualizado"
}
```

**Campos permitidos para actualizar**:
- `nombre`, `bootcamp_id`, `bootcamp_nombre`, `modalidad`
- `ingles_inicio`, `ingles_fin`, `inicio_formacion`, `horario`
- `lugar`, `opt_in`, `estado_envio`, `fecha_envio`, `message_id`
- `respuesta`, `fecha_respuesta`

**Ejemplo con curl**:
```bash
curl -X PUT https://agent-t-t.onrender.com/api/estudiantes/update-field \
  -H "Content-Type: application/json" \
  -d '{
    "telefono": "+573001234567",
    "field": "modalidad",
    "value": "Virtual"
  }'
```

**Respuesta Exitosa (200)**:
```json
{
  "success": true,
  "message": "Campo 'modalidad' actualizado exitosamente"
}
```

**Respuesta Error (400)**:
```json
{
  "success": false,
  "error": "Campo no válido: campo_invalido"
}
```

---

### 8. Actualizar MÚLTIPLES Campos de Estudiante
**PUT** `/api/estudiantes/update-fields`

Actualiza varios campos de un estudiante en una sola operación.

**Request Body**:
```json
{
  "telefono": "+573001234567",
  "fields": {
    "nombre": "Juan Pérez",
    "modalidad": "Virtual",
    "horario": "Lunes a viernes 6pm-10pm",
    "bootcamp_nombre": "Data Science Avanzado"
  }
}
```

**Ejemplo con curl**:
```bash
curl -X PUT https://agent-t-t.onrender.com/api/estudiantes/update-fields \
  -H "Content-Type: application/json" \
  -d '{
    "telefono": "+573001234567",
    "fields": {
      "modalidad": "Híbrido",
      "horario": "Sábados 8am-12pm",
      "bootcamp_id": "DS_2025_01"
    }
  }'
```

**Respuesta Exitosa (200)**:
```json
{
  "success": true,
  "message": "3 campo(s) actualizado(s) exitosamente"
}
```

**Respuesta Error (400)**:
```json
{
  "success": false,
  "error": "Campos no válidos: campo1, campo2"
}
```

---

### 9. Eliminar Un Estudiante
**DELETE** `/api/estudiantes/delete/<phone>`

Elimina un estudiante específico por su número de teléfono.

**Path Parameters**:
- `phone` (string): Número de teléfono (con o sin +)

**Ejemplo**:
```bash
curl -X DELETE https://agent-t-t.onrender.com/api/estudiantes/delete/573001234567
```

**Respuesta Exitosa (200)**:
```json
{
  "success": true,
  "message": "Estudiante eliminado (1 registro(s))"
}
```

**Respuesta Error (404)**:
```json
{
  "success": false,
  "error": "No se encontró estudiante con teléfono +573001234567"
}
```

---

### 10. Eliminar Un Bootcamp
**DELETE** `/api/bootcamps/delete/<bootcamp_id>`

Elimina un bootcamp del catálogo.

**Path Parameters**:
- `bootcamp_id` (string): Código del bootcamp

**Ejemplo**:
```bash
curl -X DELETE https://agent-t-t.onrender.com/api/bootcamps/delete/IA_2024_01
```

**Respuesta Exitosa (200)**:
```json
{
  "success": true,
  "message": "Bootcamp IA_2024_01 eliminado"
}
```

**Respuesta Error (404)**:
```json
{
  "success": false,
  "error": "No se encontró bootcamp IA_2024_01"
}
```

---

### 11. Vaciar Tabla de Estudiantes
**DELETE** `/api/estudiantes/clear-all`

⚠️ **PELIGRO**: Elimina TODOS los estudiantes de la base de datos. Esta operación no se puede deshacer.

**Ejemplo**:
```bash
curl -X DELETE https://agent-t-t.onrender.com/api/estudiantes/clear-all
```

**Respuesta Exitosa (200)**:
```json
{
  "success": true,
  "message": "150 estudiante(s) eliminado(s)"
}
```

**Respuesta Error (500)**:
```json
{
  "success": false,
  "error": "Base de datos ocupada. Intenta de nuevo en unos segundos."
}
```

---

### 12. Vaciar Tabla de Bootcamps
**DELETE** `/api/bootcamps/clear-all`

⚠️ **PELIGRO**: Elimina TODOS los bootcamps de la base de datos. Esta operación no se puede deshacer.

**Ejemplo**:
```bash
curl -X DELETE https://agent-t-t.onrender.com/api/bootcamps/clear-all
```

**Respuesta Exitosa (200)**:
```json
{
  "success": true,
  "message": "4 bootcamp(s) eliminado(s)"
}
```

---

### 13. Resetear Base de Datos Completa
**DELETE** `/api/database/reset`

⚠️ **PELIGRO EXTREMO**: Elimina TODO el contenido de la base de datos (estudiantes + bootcamps). Esta operación no se puede deshacer.

**Ejemplo**:
```bash
curl -X DELETE https://agent-t-t.onrender.com/api/database/reset
```

**Respuesta Exitosa (200)**:
```json
{
  "success": true,
  "message": "Base de datos vaciada: 150 estudiante(s) eliminado(s), 4 bootcamp(s) eliminado(s)"
}
```

---

## Ejemplos de Uso Completos

### Ejemplo 1: Actualizar modalidad de un estudiante
```bash
curl -X PUT https://agent-t-t.onrender.com/api/estudiantes/update-field \
  -H "Content-Type: application/json" \
  -d '{
    "telefono": "573001234567",
    "field": "modalidad",
    "value": "Híbrido"
  }'
```

### Ejemplo 2: Actualizar varios campos a la vez
```bash
curl -X PUT https://agent-t-t.onrender.com/api/estudiantes/update-fields \
  -H "Content-Type: application/json" \
  -d '{
    "telefono": "573001234567",
    "fields": {
      "bootcamp_id": "DS_2025_01",
      "bootcamp_nombre": "Data Science 2025",
      "modalidad": "Presencial",
      "horario": "Lunes a Viernes 2pm-6pm"
    }
  }'
```

### Ejemplo 3: Eliminar estudiante específico
```bash
curl -X DELETE https://agent-t-t.onrender.com/api/estudiantes/delete/573001234567
```

### Ejemplo 4: Vaciar base de datos y recargar desde CSV
```bash
# Paso 1: Resetear base de datos
curl -X DELETE https://agent-t-t.onrender.com/api/database/reset

# Paso 2: Recargar desde CSV (localmente)
python recreate_db.py

# O usar el endpoint de Google Drive
curl -X POST https://agent-t-t.onrender.com/api/google/upload \
  -H "Content-Type: application/json" \
  -d '{
    "fileId": "tu_google_drive_file_id",
    "accessToken": "tu_access_token"
  }'
```

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

### Errores Comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `Campo no válido: X` | Campo no permitido para actualización | Verificar lista de campos permitidos |
| `No se encontró estudiante con teléfono X` | Teléfono no existe en DB | Verificar formato del teléfono |
| `Base de datos ocupada. Intenta de nuevo...` | Operación concurrente en progreso | Esperar 1-2 segundos y reintentar |
| `Campos requeridos: X, Y` | Faltan campos obligatorios | Incluir todos los campos requeridos |

---

## Validaciones y Reglas de Negocio

### Prevención de Duplicados
- La tabla `estudiantes` tiene un constraint **UNIQUE** en `telefono_e164`
- Si intentas insertar un teléfono duplicado, se **actualiza** el registro existente (UPSERT)
- **NO** se crean registros duplicados

### Lógica de Actualización Inteligente
Cuando se hace UPSERT, solo se actualizan los campos que **no están vacíos**:

```sql
estado_envio = CASE 
    WHEN excluded.estado_envio != '' THEN excluded.estado_envio 
    ELSE estudiantes.estado_envio 
END
```

Esto evita sobrescribir datos existentes con valores vacíos.

### Normalización de Teléfonos
Los endpoints aceptan teléfonos con o sin el prefijo `+`:
- ✅ `+573001234567`
- ✅ `573001234567`

Internamente se normalizan para búsqueda.

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

### Manejo de Concurrencia
El sistema implementa **3 capas de protección** contra bloqueos de base de datos:

1. **Write-Ahead Logging (WAL)**:
   - Permite lecturas mientras se escribe
   - Múltiples lectores simultáneos sin bloqueos
   - Mejor rendimiento en operaciones concurrentes

2. **Timeouts Configurados**:
   - Timeout de 30 segundos para operaciones bloqueadas
   - Autocommit mode para transacciones rápidas
   - `busy_timeout` de 30 segundos

3. **Sistema de Reintentos**:
   - Reintentos automáticos con backoff exponencial (0.5s, 1s, 1.5s)
   - Thread locks en operaciones críticas (clear-all, reset)
   - Mensajes informativos: "Base de datos ocupada. Intenta de nuevo en unos segundos."

**Resultado**: El webhook puede recibir respuestas mientras se ejecutan operaciones de borrado masivo sin errores de "database is locked".

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
- ✅ WAL mode para operaciones concurrentes

### Limitaciones
- ⚠️ Optimizado para lecturas concurrentes, escrituras serializadas
- ⚠️ Limitado a ~1TB de datos (más que suficiente para este caso)
- ✅ Bloqueos manejados con reintentos automáticos

### Protección contra Bloqueos
El sistema implementa:
- **WAL mode**: Lecturas sin bloqueos durante escrituras
- **Timeouts**: 30 segundos de espera antes de fallar
- **Reintentos**: 3 intentos con backoff exponencial
- **Thread locks**: Serialización de operaciones críticas

### Backup
El archivo `whatsapp_tracking.db` debe incluirse en los backups regulares del sistema junto con `bd_envio.csv`.
