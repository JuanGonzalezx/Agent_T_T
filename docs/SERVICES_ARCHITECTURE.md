# Arquitectura de Servicios

## WhatsApp Messaging API - Talento Tech

Documentación técnica de la capa de servicios del backend.

---

## Diagrama de Servicios

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              app.py                                      │
│                         (Flask Application)                              │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
            ▼                   ▼                   ▼
┌───────────────────┐ ┌─────────────────┐ ┌─────────────────────┐
│  WhatsAppService  │ │ DatabaseHandler │ │ GoogleDriveService  │
│                   │ │                 │ │                     │
│ - send_text       │ │ - Turso cloud   │ │ - Download files    │
│ - send_template   │ │ - SQLite local  │ │ - Update Sheets     │
│ - validate creds  │ │ - CRUD ops      │ │ - Sync data         │
└─────────┬─────────┘ └────────┬────────┘ └──────────┬──────────┘
          │                    │                     │
          ▼                    ▼                     ▼
┌───────────────────┐ ┌─────────────────┐ ┌─────────────────────┐
│   Meta Graph API  │ │  Turso HTTP API │ │  Google Drive API   │
│   (WhatsApp)      │ │  (libSQL)       │ │  (REST)             │
└───────────────────┘ └─────────────────┘ └─────────────────────┘
```

---

## 1. WhatsAppService

**Ubicación**: `services/whatsapp_service.py`

### Responsabilidad

Gestiona toda la comunicación con la API de WhatsApp Business (Meta Graph API).

### Configuración

```python
# Variables de entorno requeridas
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERSION = os.getenv("VERSION", "v22.0")
```

### Métodos Públicos

#### `validate_credentials() -> Tuple[bool, str]`

Valida que las credenciales estén configuradas.

```python
service = WhatsAppService()
valid, message = service.validate_credentials()
# (True, "Credenciales válidas")
```

#### `send_text_message(phone: str, text: str) -> Tuple[bool, str]`

Envía un mensaje de texto simple.

```python
success, result = service.send_text_message(
    "+573001234567",
    "Hola, este es un mensaje de prueba"
)
# (True, "wamid.HBgNNTczMTU0OTYzNDgz...")
```

#### `send_template_message(phone, template_name, parameters, language_code) -> Tuple[bool, str]`

Envía un mensaje usando una plantilla pre-aprobada.

```python
success, result = service.send_template_message(
    "+573001234567",
    "prueba_matricula",
    ["Juan", "Presencial", "IA", "15", "18 oct", "20 oct", "6pm-10pm", "Sede X"],
    "es"
)
```

### Manejo de Errores

El servicio captura y procesa errores de la API de Meta:

```python
try:
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        return True, message_id
    else:
        error = response.json().get('error', {})
        return False, error.get('message', 'Error desconocido')
except Exception as e:
    return False, str(e)
```

---

## 2. DatabaseHandler

**Ubicación**: `services/db_handler.py`

### Responsabilidad

Gestiona todas las operaciones de base de datos, soportando tanto Turso (cloud) como SQLite (local).

### Auto-detección de Modo

```python
def __init__(self, db_path: str = "whatsapp_tracking.db"):
    self.turso_url = os.getenv('TURSO_DATABASE_URL')
    self.turso_token = os.getenv('TURSO_AUTH_TOKEN')
    
    if self.turso_url and self.turso_token:
        self.use_turso = True
        # Modo cloud
    else:
        self.use_turso = False
        # Modo local SQLite
```

### Métodos Principales

#### Estudiantes

```python
# Insertar o actualizar estudiante
db.insert_or_update_estudiante(estudiante_data: dict) -> Tuple[bool, str]

# Obtener todos los estudiantes
db.get_all_estudiantes() -> List[Dict]

# Obtener por bootcamp
db.get_estudiantes_by_bootcamp(bootcamp_id: str) -> List[Dict]

# Buscar por teléfono
db.get_estudiante_by_phone(telefono: str) -> List[Dict]

# Obtener pendientes de envío
db.get_estudiantes_pendientes_envio() -> List[Dict]

# Actualizar estado de envío
db.update_estado_envio(telefono: str, estado: str, message_id: str) -> Tuple[bool, str]

# Actualizar respuesta
db.update_respuesta(telefono: str, respuesta: str, fecha: str) -> Tuple[bool, str]

# Verificar si ya tiene respuesta
db.get_respuesta_existente(telefono: str) -> Tuple[bool, Optional[str]]
```

#### Bootcamps

```python
# Insertar o actualizar bootcamp
db.insert_or_update_bootcamp(bootcamp_id: str, nombre: str) -> Tuple[bool, str]

# Listar bootcamps
db.get_all_bootcamps() -> List[Dict]
```

#### Estadísticas

```python
db.get_estadisticas() -> Dict[str, Any]
# {
#     "total_estudiantes": 1234,
#     "mensajes_enviados": 1100,
#     "respuestas_si": 890,
#     ...
# }
```

### Manejo de Valores Turso

Turso devuelve valores en formato especial que requiere extracción:

```python
def _extract_turso_value(self, cell):
    """
    Turso devuelve: {'type': 'text', 'value': 'actual_value'}
    Esta función extrae 'actual_value'
    """
    if cell is None:
        return None
    if isinstance(cell, dict):
        if cell.get('type') == 'null':
            return None
        return cell.get('value', '')
    return cell
```

### Thread Safety

El handler usa locks para operaciones concurrentes:

```python
self._lock = threading.RLock()

def _execute_with_retry(self, operation, max_retries=3):
    with self._lock:
        # Operación protegida
```

---

## 3. GoogleDriveService

**Ubicación**: `services/google_drive_service.py`

### Responsabilidad

Gestiona la integración con Google Drive para importar y sincronizar datos.

### APIs Utilizadas

- **Google Drive API v3**: Descargar archivos, obtener metadata
- **Google Sheets API v4**: Actualizar hojas de cálculo

### Métodos Principales

#### Metadata

```python
service.get_file_metadata(file_id: str, access_token: str) -> Tuple[bool, Dict, str]
# Obtiene información del archivo (nombre, tipo MIME, tamaño)
```

#### Descarga

```python
service.download_file_content(file_id: str, access_token: str, is_google_sheet: bool) -> Tuple[bool, bytes, str]
# Descarga el contenido del archivo
# Para Google Sheets, exporta como CSV
```

#### Parsing

```python
service.parse_file_content(content: bytes) -> Tuple[bool, pd.DataFrame, str]
# Convierte el contenido a DataFrame de pandas
# Soporta CSV y XLSX
```

#### Actualización

```python
# Google Sheets
service.update_google_sheet(file_id, access_token, df) -> Tuple[bool, str]

# CSV en Drive
service.update_csv_file(file_id, access_token, df) -> Tuple[bool, str]

# XLSX en Drive
service.update_xlsx_file(file_id, access_token, df) -> Tuple[bool, str]
```

### Tipos MIME Soportados

| Tipo | MIME Type |
|------|-----------|
| Google Sheets | `application/vnd.google-apps.spreadsheet` |
| CSV | `text/csv` |
| Excel | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |

---

## 4. Utils

### data_normalizer.py

**Ubicación**: `utils/data_normalizer.py`

Funciones de utilidad para normalizar datos importados.

```python
# Normalizar columna de teléfono
normalize_phone_column(df: pd.DataFrame) -> Tuple[bool, pd.DataFrame, str]

# Limpiar números de teléfono (formato E.164)
clean_phone_numbers(df: pd.DataFrame) -> pd.DataFrame

# Agregar columnas de tracking
add_tracking_columns(df: pd.DataFrame) -> pd.DataFrame

# Validar DataFrame
validate_dataframe(df: pd.DataFrame) -> Tuple[bool, str]
```

### Normalización de Teléfonos

```python
def normalize_phone(phone: str) -> str:
    """
    Convierte cualquier formato de teléfono a E.164
    
    Ejemplos:
    - "301 234 5678" -> "+573012345678"
    - "3012345678" -> "+573012345678"
    - "+57 301 234 5678" -> "+573012345678"
    """
```

---

## Patrones de Diseño

### 1. Service Layer Pattern

Toda la lógica de negocio está encapsulada en servicios:

```
app.py (Controller) → services/* (Business Logic) → APIs externas
```

### 2. Repository Pattern

`DatabaseHandler` actúa como repositorio abstracto sobre Turso/SQLite.

### 3. Singleton (implícito)

Los servicios se instancian una vez en `app.py`:

```python
whatsapp_service = WhatsAppService()
google_drive_service = GoogleDriveService()
db_handler = DatabaseHandler(DB_PATH)
```

### 4. Strategy Pattern

`DatabaseHandler` cambia de estrategia según el entorno:

```python
if self.use_turso:
    # Estrategia HTTP para Turso
else:
    # Estrategia SQLite local
```

---

## Flujos de Datos

### Flujo: Envío Masivo

```
1. POST /api/messages/send-batch
       │
2. db_handler.get_estudiantes_pendientes_envio()
       │
3. Para cada estudiante:
       │
4.     whatsapp_service.send_template_message()
       │
5.     db_handler.update_estado_envio()
       │
6. Respuesta con estadísticas
```

### Flujo: Recepción de Respuesta (Webhook)

```
1. POST /webhook (desde Meta)
       │
2. Parsear mensaje entrante
       │
3. Validar respuesta (Si/No)
       │
4. db_handler.get_respuesta_existente()
       │
5. Si no existe:
       │
6.     db_handler.update_respuesta()
       │
7.     whatsapp_service.send_text_message() (confirmación)
```

### Flujo: Importación desde Drive

```
1. POST /api/google/upload
       │
2. google_drive_service.get_file_metadata()
       │
3. google_drive_service.download_file_content()
       │
4. google_drive_service.parse_file_content()
       │
5. normalize_phone_column() + clean_phone_numbers()
       │
6. add_tracking_columns()
       │
7. Para cada fila:
       │
8.     db_handler.insert_or_update_estudiante()
       │
9. google_drive_service.update_*() (sincronizar de vuelta)
```

---

## Manejo de Errores

### Estrategia General

1. **Capturar** excepciones a nivel de servicio
2. **Loggear** con tags específicos (`[SEND]`, `[DB]`, etc.)
3. **Retornar** tuplas `(success: bool, result/error: str)`
4. **Propagar** al controlador para respuesta HTTP apropiada

### Ejemplo

```python
# En servicio
def send_message(self, phone, text):
    try:
        response = requests.post(url, json=payload)
        if response.ok:
            return True, response.json()['messages'][0]['id']
        else:
            return False, response.json()['error']['message']
    except Exception as e:
        return False, str(e)

# En controlador (app.py)
success, result = whatsapp_service.send_message(phone, text)
if success:
    return jsonify({'success': True, 'message_id': result}), 200
else:
    return jsonify({'success': False, 'error': result}), 400
```

---

## Testing

### Mocks Recomendados

```python
# Mock de WhatsApp Service
@patch('services.whatsapp_service.requests.post')
def test_send_message(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        'messages': [{'id': 'wamid.test'}]
    }
    
    service = WhatsAppService()
    success, result = service.send_text_message('+573001234567', 'test')
    
    assert success
    assert result == 'wamid.test'
```

### Variables de Entorno para Tests

```bash
export ACCESS_TOKEN=test_token
export PHONE_NUMBER_ID=123456789
export TURSO_DATABASE_URL=  # vacío para usar SQLite local
```
