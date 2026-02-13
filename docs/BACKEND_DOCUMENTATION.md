# Agent_T_T Backend - Documentación Técnica v2.0

## Índice

1. [Descripción General](#descripción-general)
2. [Arquitectura](#arquitectura)
3. [Estructura del Proyecto](#estructura-del-proyecto)
4. [Instalación](#instalación)
5. [Configuración](#configuración)
6. [API Reference](#api-reference)
7. [Servicios](#servicios)
8. [Base de Datos](#base-de-datos)
9. [Testing](#testing)
10. [Deployment](#deployment)

---

## Descripción General

**Agent_T_T** es un backend Flask para gestión de mensajería WhatsApp orientado a la administración de bootcamps y estudiantes. Permite:

- Envío masivo de mensajes de plantilla a estudiantes
- Recepción y procesamiento automático de respuestas (Sí/No)
- Sincronización bidireccional con Google Drive
- Gestión CRUD de estudiantes y bootcamps
- Tracking de estados de envío y respuestas

### Stack Tecnológico

| Componente | Tecnología |
|------------|------------|
| Framework | Flask 3.0 |
| Base de Datos | Turso (libSQL) / SQLite |
| API Externa | WhatsApp Business API (Meta) |
| Almacenamiento | Google Drive API |
| Servidor WSGI | Gunicorn |
| Hosting | Render |

---

## Arquitectura

El proyecto sigue el patrón **MVC (Model-View-Controller)** adaptado para APIs REST:

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENTE                                 │
│              (Frontend React / WhatsApp / Drive)                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     CONTROLLERS (Vista)                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ webhook  │ │ message  │ │ student  │ │ bootcamp │           │
│  │controller│ │controller│ │controller│ │controller│           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
│  ┌──────────┐ ┌──────────┐                                      │
│  │  drive   │ │  system  │                                      │
│  │controller│ │controller│                                      │
│  └──────────┘ └──────────┘                                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      CORE (Lógica)                              │
│              ┌─────────────────────────┐                        │
│              │    ResponseLogic        │                        │
│              │  (Procesa respuestas)   │                        │
│              └─────────────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SERVICES (Modelo)                            │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │ DatabaseHand │ │ WhatsAppServ │ │ GoogleDrive  │            │
│  │   (Turso)    │ │   (Meta)     │ │   Service    │            │
│  └──────────────┘ └──────────────┘ └──────────────┘            │
│              ┌─────────────────────────┐                        │
│              │     SyncService         │                        │
│              │   (Scheduler 5min)      │                        │
│              └─────────────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Estructura del Proyecto

```
Agent_T_T/
├── app/                          # Paquete principal
│   ├── __init__.py               # Factory pattern + WSGI entry point
│   │
│   ├── controllers/              # Endpoints HTTP (Blueprints)
│   │   ├── webhook_controller.py    # POST/GET /webhook
│   │   ├── message_controller.py    # /api/messages/*
│   │   ├── student_controller.py    # /api/estudiantes/*
│   │   ├── bootcamp_controller.py   # /api/bootcamps/*
│   │   ├── drive_controller.py      # /api/google/*, /api/sync/*
│   │   └── system_controller.py     # /, /health, /privacy
│   │
│   ├── services/                 # Conexiones externas
│   │   ├── db_handler.py            # Turso/SQLite handler
│   │   ├── whatsapp_service.py      # WhatsApp Business API
│   │   ├── google_drive_service.py  # Google Drive API
│   │   └── sync_service.py          # Scheduler de sincronización
│   │
│   ├── core/                     # Lógica de negocio
│   │   └── logic.py                 # ResponseLogic (Sí/No)
│   │
│   ├── agent/                    # [Futuro] Agente IA LangGraph
│   │   ├── graph.py
│   │   ├── state.py
│   │   └── nodes.py
│   │
│   └── utils/                    # Utilidades
│       └── data_normalizer.py       # Limpieza de datos Excel/CSV
│
├── tests/                        # Tests unitarios e integración
│   ├── test_db_handler.py           # 20 tests
│   ├── test_data_normalizer.py      # 20 tests
│   ├── test_controllers.py          # 12 tests
│   └── test_logic.py                # 10 tests
│
├── templates/                    # HTML estático
│   └── privacy.html
│
├── run.py                        # Entry point desarrollo
├── requirements.txt              # Dependencias
├── pytest.ini                    # Configuración tests
└── .env                          # Variables de entorno
```

---

## Instalación

### Requisitos
- Python 3.10+
- pip

### Pasos

```bash
# 1. Clonar repositorio
git clone https://github.com/tu-usuario/Agent_T_T.git
cd Agent_T_T

# 2. Crear entorno virtual
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
copy .env.example .env
# Editar .env con tus credenciales

# 5. Ejecutar en desarrollo
python run.py
```

---

## Configuración

### Variables de Entorno (.env)

```env
# WhatsApp Business API
ACCESS_TOKEN=your_meta_access_token
PHONE_NUMBER_ID=your_phone_number_id
VERIFY_TOKEN=your_webhook_verify_token
VERSION=v22.0

# Base de Datos (Producción - Turso)
TURSO_DATABASE_URL=libsql://your-db.turso.io
TURSO_AUTH_TOKEN=your_turso_token

# Configuración Opcional
DELAY_SECONDS=1.5
FLASK_ENV=development
PORT=5000
```

### Modos de Base de Datos

| Variable | Modo |
|----------|------|
| `TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN` definidos | Turso (cloud) |
| Variables no definidas | SQLite local (`data/whatsapp_tracking.db`) |

---

## API Reference

### Sistema

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/` | Información del servicio |
| GET | `/health` | Health check |
| GET | `/privacy` | Política de privacidad |
| DELETE | `/api/database/reset` | ⚠️ Borrar toda la BD |

**Ejemplo respuesta GET `/`:**
```json
{
  "service": "WhatsApp Messaging API Server",
  "version": "2.0 (MVC Refactored)",
  "status": "running",
  "database": "Turso (cloud)"
}
```

---

### Webhook WhatsApp

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/webhook` | Verificación de Meta |
| POST | `/webhook` | Recibir mensajes entrantes |

**Query params (GET):**
- `hub.mode`: Debe ser "subscribe"
- `hub.verify_token`: Token configurado en .env
- `hub.challenge`: Challenge de Meta

---

### Mensajes

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/messages/send-simple` | Envío individual |
| POST | `/api/messages/send-template` | Envío de plantilla |
| POST | `/api/messages/send-batch` | Envío masivo a pendientes |

**POST `/api/messages/send-simple` - Mensaje de texto:**
```json
{
  "phone": "573001234567",
  "message": "Hola, este es un mensaje de prueba"
}
```

**POST `/api/messages/send-simple` - Mensaje de plantilla:**
```json
{
  "phone": "573001234567",
  "template_name": "prueba_matricula",
  "parameters": ["Juan", "Virtual", "Python", "Lunes", "Viernes", "15/02", "9AM-12PM", "Zoom"],
  "language_code": "es"
}
```

**POST `/api/messages/send-batch`:**
```json
{
  "template_name": "prueba_matricula",
  "language_code": "es"
}
```

**Respuesta exitosa:**
```json
{
  "success": true,
  "message_id": "wamid.xxx",
  "type": "template"
}
```

---

### Estudiantes

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/estudiantes/all` | Listar con paginación |
| GET | `/api/estudiantes/bootcamp/<id>` | Filtrar por bootcamp |
| GET | `/api/estudiantes/phone/<phone>` | Buscar por teléfono |
| PUT | `/api/estudiantes/update-field` | Actualizar campo específico |
| DELETE | `/api/estudiantes/delete/<phone>` | Eliminar estudiante |
| GET | `/api/estadisticas` | Estadísticas generales |
| GET | `/api/contacts/pending` | Pendientes de envío |
| GET | `/api/contacts/stats` | Alias de estadísticas |

**GET `/api/estudiantes/all?limit=50&offset=0`:**
```json
{
  "success": true,
  "total": 150,
  "estudiantes": [
    {
      "id": 1,
      "telefono_e164": "573001234567",
      "nombre": "Juan Pérez",
      "bootcamp_id": "BOOT001",
      "bootcamp_nombre": "Python Básico",
      "modalidad": "Virtual",
      "estado_envio": "sent",
      "respuesta": "Sí",
      "fecha_respuesta": "2026-02-13T10:30:00"
    }
  ]
}
```

**PUT `/api/estudiantes/update-field`:**
```json
{
  "telefono": "573001234567",
  "field": "modalidad",
  "value": "Presencial"
}
```

**GET `/api/estadisticas`:**
```json
{
  "success": true,
  "stats": {
    "total_estudiantes": 150,
    "mensajes_enviados": 120,
    "mensajes_error": 5,
    "confirmaron_si": 80,
    "confirmaron_no": 20,
    "pendientes_respuesta": 20,
    "total_bootcamps": 3,
    "tasa_respuesta": 83.33
  }
}
```

---

### Bootcamps

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/bootcamps` | Listar todos |
| DELETE | `/api/bootcamps/delete/<id>` | Eliminar uno |
| DELETE | `/api/bootcamps/clear-all` | Eliminar todos |

**GET `/api/bootcamps`:**
```json
{
  "success": true,
  "bootcamps": [
    {
      "bootcamp_id": "BOOT001",
      "bootcamp_nombre": "Python Básico",
      "fecha_creacion": "2026-02-10T08:00:00"
    }
  ]
}
```

---

### Google Drive

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/google/upload` | Cargar archivo de Drive |
| POST | `/api/sync/drive-manual` | Forzar sincronización |

**POST `/api/google/upload`:**
```json
{
  "fileId": "1abc123...",
  "accessToken": "ya29.xxx..."
}
```

**Respuesta:**
```json
{
  "success": true,
  "message": "Procesado y Sincronizado",
  "total_rows": 150,
  "columns": ["nombre", "telefono_e164", "bootcamp_id", "estado_envio", "respuesta"]
}
```

---

## Servicios

### DatabaseHandler (`services/db_handler.py`)

Gestiona la conexión a Turso (producción) o SQLite (desarrollo).

**Métodos principales:**

```python
# Bootcamps
insert_or_update_bootcamp(bootcamp_id: str, bootcamp_nombre: str) -> Tuple[bool, str]
get_all_bootcamps() -> List[Dict]
delete_bootcamp(bootcamp_id: str) -> Tuple[bool, str]
clear_all_bootcamps() -> Tuple[bool, str]

# Estudiantes
insert_or_update_estudiante(estudiante_data: Dict) -> Tuple[bool, str]
get_all_estudiantes(limit: int, offset: int) -> Tuple[List[Dict], int]
get_estudiantes_by_bootcamp(bootcamp_id: str) -> List[Dict]
get_estudiante_by_phone(telefono: str) -> List[Dict]
get_estudiantes_pendientes_envio() -> List[Dict]
update_estado_envio(telefono: str, estado: str, message_id: str) -> Tuple[bool, str]
update_respuesta(telefono: str, respuesta: str, fecha: str) -> Tuple[bool, str]
get_respuesta_existente(telefono: str) -> Tuple[bool, Optional[str]]
delete_estudiante(telefono: str) -> Tuple[bool, str]
update_estudiante_field(telefono: str, field: str, value: Any) -> Tuple[bool, str]

# Sistema
get_estadisticas() -> Dict
reset_database() -> Tuple[bool, str]
```

---

### WhatsAppService (`services/whatsapp_service.py`)

Comunicación con WhatsApp Business API.

```python
validate_credentials() -> Tuple[bool, str]
send_text_message(phone: str, text: str) -> Tuple[bool, str]
send_template_message(
    phone: str, 
    template_name: str, 
    parameters: List[str], 
    language_code: str = 'es'
) -> Tuple[bool, str]
```

---

### GoogleDriveService (`services/google_drive_service.py`)

Interacción con Google Drive API.

```python
get_file_metadata(file_id: str, token: str) -> Tuple[bool, Dict, str]
download_file_content(file_id: str, token: str, is_sheet: bool) -> Tuple[bool, bytes, str]
parse_file_content(content: bytes) -> Tuple[bool, pd.DataFrame, str]
update_google_sheet(spreadsheet_id: str, token: str, df: pd.DataFrame) -> Tuple[bool, str]
update_csv_file(file_id: str, token: str, df: pd.DataFrame) -> Tuple[bool, str]
update_xlsx_file(file_id: str, token: str, df: pd.DataFrame) -> Tuple[bool, str]
```

---

### SyncService (`services/sync_service.py`)

Sincronización automática cada 5 minutos usando APScheduler.

```python
start()  # Inicia scheduler
shutdown()  # Detiene scheduler
set_current_file(file_id: str, token: str, mime_type: str)  # Configura archivo activo
mark_pending()  # Marca cambios pendientes para sincronizar
```

---

### ResponseLogic (`core/logic.py`)

Procesa respuestas de estudiantes desde el webhook.

```python
process_webhook_event(data: Dict)  # Entrada del webhook
_handle_response(phone: str, text: str)  # Lógica Sí/No
```

**Flujo de respuesta:**
1. Recibe mensaje de WhatsApp via webhook
2. Extrae teléfono y texto del mensaje
3. Verifica si el estudiante ya respondió → ignora duplicados
4. Detecta variantes de "sí" (si, sí, yes, confirmar, acepto) → guarda "Sí"
5. Detecta variantes de "no" (no, rechazar, cancelar) → guarda "No"
6. Otro texto → envía mensaje pidiendo clarificación
7. Envía confirmación al usuario

---

## Base de Datos

### Esquema

```sql
-- Tabla de bootcamps
CREATE TABLE bootcamps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bootcamp_id TEXT UNIQUE NOT NULL,
    bootcamp_nombre TEXT NOT NULL,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de estudiantes
CREATE TABLE estudiantes (
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
    estado_envio TEXT,           -- 'pending', 'sent', 'error'
    fecha_envio TIMESTAMP,
    message_id TEXT,
    respuesta TEXT,              -- 'Sí', 'No', NULL
    fecha_respuesta TIMESTAMP,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para optimización
CREATE INDEX idx_estudiantes_telefono ON estudiantes(telefono_e164);
CREATE INDEX idx_estudiantes_bootcamp ON estudiantes(bootcamp_id);
CREATE INDEX idx_estudiantes_fecha_envio ON estudiantes(fecha_envio);
CREATE INDEX idx_estudiantes_respuesta ON estudiantes(respuesta);
```

### Estados de Envío

| Estado | Descripción |
|--------|-------------|
| `NULL` o `''` | Pendiente (no enviado) |
| `pending` | En cola de envío |
| `sent` | Enviado exitosamente |
| `error` | Error en el envío |

### Estados de Respuesta

| Estado | Descripción |
|--------|-------------|
| `NULL` o `''` | Sin respuesta |
| `Sí` | Confirmó asistencia |
| `No` | Rechazó/canceló |

---

## Testing

### Ejecutar Tests

```bash
# Todos los tests
python -m pytest tests/ -v

# Tests específicos
python -m pytest tests/test_db_handler.py -v
python -m pytest tests/test_controllers.py -v
python -m pytest tests/test_logic.py -v
python -m pytest tests/test_data_normalizer.py -v

# Con coverage
pip install pytest-cov
python -m pytest tests/ --cov=app --cov-report=html
```

### Cobertura de Tests

| Módulo | Tests | Cobertura |
|--------|-------|-----------|
| db_handler | 20 | CRUD completo |
| data_normalizer | 20 | Normalización de datos |
| controllers | 12 | Endpoints HTTP |
| logic | 10 | Procesamiento respuestas |
| **Total** | **64** | - |

### Configuración (pytest.ini)

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

---

## Deployment

### Render (Producción)

**Start Command:**
```bash
gunicorn app:app
```

> Nota: No se requiere Procfile. El paquete `app/` expone `app = create_app()` al final de `__init__.py`.

**Variables de Entorno en Render:**

| Variable | Descripción |
|----------|-------------|
| `ACCESS_TOKEN` | Token de Meta WhatsApp |
| `PHONE_NUMBER_ID` | ID del número de WhatsApp |
| `VERIFY_TOKEN` | Token de verificación webhook |
| `TURSO_DATABASE_URL` | URL de Turso |
| `TURSO_AUTH_TOKEN` | Token de Turso |

### Local (Desarrollo)

```bash
# Con Flask directamente
python run.py

# Con Gunicorn (simular producción)
gunicorn app:app --bind 0.0.0.0:5000
```

---

## Changelog v2.0.0

### Nuevas Características
- ✅ Refactorización completa a arquitectura MVC
- ✅ Separación en Blueprints (6 controllers)
- ✅ Factory pattern (`create_app()`)
- ✅ Soporte dual Turso (cloud) / SQLite (local)
- ✅ Suite de tests completa (64 tests)
- ✅ Sincronización automática con Google Drive (cada 5 min)
- ✅ Procesamiento inteligente de respuestas Sí/No
- ✅ Entry point WSGI compatible con Gunicorn
- ✅ Normalización robusta de datos Excel/CSV

### Estructura Anterior vs Nueva

| Antes | Después |
|-------|---------|
| `app.py` (monolítico 1400 líneas) | `app/` (paquete modular) |
| Sin tests | 64 tests unitarios |
| Solo SQLite | Turso + SQLite |
| Sin sincronización | SyncService automático |

---

## Próximos Pasos (Roadmap)

- [ ] Implementar agente IA con LangGraph (`app/agent/`)
- [ ] Agregar autenticación JWT
- [ ] Dashboard de métricas
- [ ] Soporte para múltiples templates
- [ ] Rate limiting avanzado

---

## Autores

- **Agent_T_T Team**
- Versión: 2.0.0
- Última actualización: Febrero 2026
