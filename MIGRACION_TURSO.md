# Documentación: Migración a Turso como Fuente Única de Verdad

**Fecha:** 1-2 de febrero de 2026  
**Versión:** 2.0.0

---

## Resumen Ejecutivo

Se realizó una migración completa del sistema para eliminar la dependencia del archivo CSV local (`bd_envio.csv`) y usar **Turso (libSQL cloud)** como única fuente de verdad para todos los datos de estudiantes.

---

## Problemas Identificados y Solucionados

### 1. Desincronización CSV/Turso
**Problema:** El webhook verificaba respuestas en el CSV, pero el frontend leía de Turso, causando inconsistencias.

**Solución:** Eliminación completa del CSV como fuente de datos. Turso es ahora la única fuente de verdad.

### 2. Valores de Turso como Objetos
**Problema:** Turso devuelve valores en formato:
```python
{'type': 'text', 'value': 'Cristian'}
{'type': 'null'}
```
En lugar de valores simples, causando que los mensajes de WhatsApp mostraran literalmente `{'type': 'text', 'value': 'Cristian'}`.

**Solución:** Se creó el método `_extract_turso_value()` para extraer valores correctamente:
```python
def _extract_turso_value(self, cell):
    if cell is None:
        return None
    if isinstance(cell, dict):
        if cell.get('type') == 'null':
            return None
        return cell.get('value', '')
    return cell
```

### 3. Error de Tipos en Comparaciones
**Problema:** `'>' not supported between instances of 'str' and 'int'` al comparar COUNT(*) de Turso.

**Solución:** Conversión explícita a int antes de comparar:
```python
count = int(check_result['count']) if check_result and check_result.get('count') else 0
```

### 4. Respuestas "default" Tratadas como Válidas
**Problema:** El valor "default" en la columna `respuesta` era detectado como respuesta existente.

**Solución:** Se agregó condición para ignorar "default" como respuesta válida:
```sql
AND (respuesta IS NULL OR respuesta = '' OR LOWER(respuesta) = 'default')
```

### 5. Logging con Emojis
**Problema:** Logs con emojis no profesionales y difíciles de parsear.

**Solución:** Estándar de logging profesional con tags:
- `[SEND]` - Operaciones de envío de mensajes
- `[WEBHOOK]` - Eventos del webhook de WhatsApp
- `[DB]` - Operaciones de base de datos
- `[DRIVE]` - Operaciones con Google Drive
- `[SYNC]` - Sincronización automática

---

## Cambios en Archivos

### `services/db_handler.py`

#### Nuevos Métodos:

```python
def _extract_turso_value(self, cell):
    """Extrae el valor real de una celda de Turso."""
    
def get_estudiantes_pendientes_envio(self) -> List[Dict[str, Any]]:
    """Obtiene estudiantes con opt_in=TRUE y estado_envio != 'sent'."""
    
def update_estado_envio(self, telefono: str, estado: str, message_id: str = None):
    """Actualiza el estado de envío de un estudiante."""
```

#### Modificaciones:

- `_execute_query()`: Ahora usa `_extract_turso_value()` para convertir resultados
- `update_respuesta()`: Convierte count a int y permite actualizar respuestas "default"
- `get_respuesta_existente()`: Ignora valores 'default', 'null', 'none' como respuestas válidas

### `app.py`

#### Eliminado:
- Import de `CSVHandler`
- Variable `CSV_PATH`
- Instancia `csv_handler`
- Todas las operaciones con CSV local

#### Endpoints Modificados:

| Endpoint | Antes | Después |
|----------|-------|---------|
| `/api/messages/send-batch` | Leía de CSV | Lee de Turso |
| `/api/contacts/stats` | Estadísticas del CSV | Estadísticas de Turso |
| `/api/contacts/pending` | Pendientes del CSV | Pendientes de Turso |
| `/api/google/upload` | Guardaba en CSV + Turso | Solo guarda en Turso |
| `sync_to_drive_if_needed()` | Sincronizaba CSV a Drive | Sincroniza Turso a Drive |

---

## Arquitectura Final

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Google Drive   │◄───►│   Flask API     │◄───►│     Turso       │
│  (importación)  │     │   (Render)      │     │ (fuente única)  │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │  WhatsApp API   │
                        │     (Meta)      │
                        └─────────────────┘
```

### Flujo de Datos:

1. **Importación:** Google Drive → API → Turso
2. **Envío de mensajes:** Turso → API → WhatsApp
3. **Respuestas:** WhatsApp → Webhook → Turso
4. **Frontend:** Turso → API → Panel Vercel
5. **Sincronización:** Turso → API → Google Drive (cada 5 min si hay cambios)

---

## Archivos Obsoletos (pueden eliminarse)

| Archivo | Razón |
|---------|-------|
| `bd_envio.csv` | Ya no se usa como fuente de datos |
| `utils/csv_handler.py` | Ya no se importa en app.py |

---

## Endpoints API Actualizados

### POST `/api/messages/send-batch`
Envía mensajes masivos a estudiantes pendientes.

**Request:**
```json
{
  "template_name": "prueba_matricula",
  "language_code": "es"
}
```

**Comportamiento:**
1. Consulta `get_estudiantes_pendientes_envio()` en Turso
2. Filtra por `opt_in = TRUE` y `estado_envio != 'sent'`
3. Envía mensaje vía WhatsApp API
4. Actualiza `estado_envio` a 'sent' en Turso

### GET `/api/contacts/pending`
Lista estudiantes pendientes de envío.

**Response:**
```json
{
  "success": true,
  "count": 5,
  "contacts": [
    {
      "nombre": "Juan García",
      "telefono": "+573001234567",
      "bootcamp": "Inteligencia Artificial",
      "modalidad": "Presencial",
      "opt_in": "TRUE",
      "estado_envio": ""
    }
  ]
}
```

### POST `/webhook`
Recibe respuestas de WhatsApp y las guarda en Turso.

**Comportamiento:**
1. Valida que la respuesta sea "Sí" o "No"
2. Verifica en Turso si ya tiene respuesta (ignora "default")
3. Guarda respuesta en Turso
4. Envía mensaje de confirmación

---

## Variables de Entorno Requeridas

```env
# WhatsApp Business API
WHATSAPP_PHONE_NUMBER_ID=your_phone_id
WHATSAPP_ACCESS_TOKEN=your_token
WEBHOOK_VERIFY_TOKEN=your_verify_token

# Turso Database
TURSO_DATABASE_URL=libsql://your-db.turso.io
TURSO_AUTH_TOKEN=your_turso_token

# Opcional
DELAY_SECONDS=1.5
PORT=5000
```

---

## Testing

### Verificar conexión a Turso:
```bash
curl https://agent-t-t.onrender.com/api/health
```

### Verificar estudiantes pendientes:
```bash
curl https://agent-t-t.onrender.com/api/contacts/pending
```

### Verificar estadísticas:
```bash
curl https://agent-t-t.onrender.com/api/estadisticas
```

---

## Commits Relacionados

1. `refactor: migración a Turso como única fuente de verdad, eliminado CSV`
2. `fix: convertir valores de Turso a string antes de usar replace`
3. `fix: extraer valores de objetos Turso correctamente`
4. `fix: convertir count a int y permitir actualizar respuestas 'default'`

---

## Notas Adicionales

- El frontend en Vercel (`panel-agent-tt.vercel.app`) ya consumía de Turso, por lo que no requirió cambios.
- La sincronización a Google Drive sigue funcionando, pero ahora exporta datos de Turso en lugar del CSV local.
- Los backups del CSV ya no son necesarios; Turso maneja su propia persistencia en la nube.
