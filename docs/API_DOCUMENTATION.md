# API Documentation

## WhatsApp Messaging API - Talento Tech

**Base URL**: `https://agent-t-t.onrender.com`  
**Versión**: 2.0  
**Formato**: JSON

---

## Tabla de Contenidos

1. [Información General](#1-información-general)
2. [Autenticación](#2-autenticación)
3. [Endpoints Públicos](#3-endpoints-públicos)
4. [Endpoints de Mensajería](#4-endpoints-de-mensajería)
5. [Endpoints de Estudiantes](#5-endpoints-de-estudiantes)
6. [Endpoints de Bootcamps](#6-endpoints-de-bootcamps)
7. [Endpoints de Integración](#7-endpoints-de-integración)
8. [Webhook](#8-webhook)
9. [Códigos de Error](#9-códigos-de-error)

---

## 1. Información General

### Headers Comunes

```http
Content-Type: application/json
Accept: application/json
```

### Formato de Respuesta Estándar

**Éxito:**
```json
{
  "success": true,
  "message": "Descripción del resultado",
  "data": { ... }
}
```

**Error:**
```json
{
  "success": false,
  "error": "Descripción del error"
}
```

---

## 2. Autenticación

La API actualmente no requiere autenticación para endpoints públicos. El webhook de WhatsApp utiliza verificación mediante token secreto.

---

## 3. Endpoints Públicos

### GET `/`

Información general de la API.

**Response:**
```json
{
  "service": "WhatsApp Messaging API Server",
  "version": "2.0",
  "status": "running",
  "database": "Turso (cloud)",
  "endpoints": {
    "health": "/health",
    "privacy": "/privacy",
    "estudiantes": "/api/estudiantes/all",
    "bootcamps": "/api/bootcamps",
    "estadisticas": "/api/estadisticas",
    "send_message": "/api/messages/send-simple",
    "send_batch": "/api/messages/send-batch",
    "webhook": "/webhook"
  }
}
```

---

### GET `/health`

Verificación del estado del servidor y credenciales.

**Response 200:**
```json
{
  "status": "healthy",
  "service": "WhatsApp Messaging API",
  "credentials": "Credenciales válidas",
  "database": "Turso (libSQL)"
}
```

**Response 503:**
```json
{
  "status": "warning",
  "service": "WhatsApp Messaging API",
  "credentials": "ACCESS_TOKEN no configurado o inválido",
  "database": "Turso (libSQL)"
}
```

---

### GET `/privacy`

Página de política de privacidad (requerida por Meta).

**Response:** HTML

---

## 4. Endpoints de Mensajería

### POST `/api/messages/send-simple`

Envía un mensaje de texto simple o una plantilla a un número.

**Request Body:**

*Mensaje de texto:*
```json
{
  "phone": "+573001234567",
  "message": "Hola, este es un mensaje de prueba"
}
```

*Mensaje de plantilla:*
```json
{
  "phone": "+573001234567",
  "template_name": "hello_world",
  "language_code": "es"
}
```

**Response 200:**
```json
{
  "success": true,
  "message_id": "wamid.HBgNNTczMTU0OTYzNDgzFQIAERgSM...",
  "recipient": "+573001234567"
}
```

**Response 400:**
```json
{
  "success": false,
  "error": "El campo 'phone' es requerido"
}
```

---

### POST `/api/messages/send-template`

Envía un mensaje con plantilla personalizada y parámetros.

**Request Body:**
```json
{
  "phone": "+573001234567",
  "template_name": "prueba_matricula",
  "parameters": [
    "Juan García",
    "Presencial",
    "Inteligencia Artificial",
    "15",
    "18 de octubre",
    "20 de octubre",
    "Lunes a viernes 6pm-10pm",
    "Universidad XYZ"
  ],
  "language_code": "es"
}
```

**Response 200:**
```json
{
  "success": true,
  "message_id": "wamid.HBgNNTczMTU0OTYzNDgzFQIAERgSM...",
  "template_name": "prueba_matricula",
  "recipient": "+573001234567"
}
```

---

### POST `/api/messages/send-batch`

Envío masivo de mensajes a estudiantes pendientes.

**Request Body:**
```json
{
  "template_name": "prueba_matricula",
  "language_code": "es"
}
```

**Response 200:**
```json
{
  "success": true,
  "message": "Envio masivo completado",
  "template_name": "prueba_matricula",
  "language_code": "es",
  "stats": {
    "sent": 145,
    "errors": 5,
    "total_processed": 150
  },
  "results": [
    {
      "name": "Juan García",
      "phone": "+573001234567",
      "success": true,
      "result": "wamid.xxx",
      "error": null
    }
  ]
}
```

---

## 5. Endpoints de Estudiantes

### GET `/api/estudiantes/all`

Lista todos los estudiantes con paginación.

**Query Parameters:**
| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `limit` | int | 100 | Máximo de resultados |
| `offset` | int | 0 | Desplazamiento |

**Request:**
```http
GET /api/estudiantes/all?limit=50&offset=0
```

**Response 200:**
```json
{
  "success": true,
  "count": 50,
  "total": 1234,
  "limit": 50,
  "offset": 0,
  "estudiantes": [
    {
      "id": 1,
      "telefono_e164": "+573001234567",
      "nombre": "Juan García",
      "bootcamp_id": "BT001",
      "bootcamp_nombre": "Inteligencia Artificial",
      "modalidad": "Presencial",
      "ingles_inicio": "15",
      "ingles_fin": "18 de octubre",
      "inicio_formacion": "20 de octubre",
      "horario": "Lunes a viernes 6pm-10pm",
      "lugar": "Universidad XYZ",
      "opt_in": "TRUE",
      "estado_envio": "sent",
      "fecha_envio": "2026-02-01T10:30:00",
      "message_id": "wamid.xxx",
      "respuesta": "Si",
      "fecha_respuesta": "2026-02-01T11:45:00"
    }
  ]
}
```

---

### GET `/api/estudiantes/bootcamp/:bootcamp_id`

Estudiantes filtrados por bootcamp.

**Request:**
```http
GET /api/estudiantes/bootcamp/BT001
```

**Response 200:**
```json
{
  "success": true,
  "bootcamp_id": "BT001",
  "count": 25,
  "estudiantes": [ ... ]
}
```

---

### GET `/api/estudiantes/phone/:phone`

Buscar estudiante por número de teléfono.

**Request:**
```http
GET /api/estudiantes/phone/573001234567
```

**Response 200:**
```json
{
  "success": true,
  "count": 1,
  "estudiantes": [
    {
      "id": 1,
      "telefono_e164": "+573001234567",
      "nombre": "Juan García",
      ...
    }
  ]
}
```

---

### GET `/api/estudiantes/date-range`

Estudiantes por rango de fechas de envío.

**Query Parameters:**
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `start_date` | string | Fecha inicio (YYYY-MM-DD) |
| `end_date` | string | Fecha fin (YYYY-MM-DD) |

**Request:**
```http
GET /api/estudiantes/date-range?start_date=2026-02-01&end_date=2026-02-28
```

---

### PUT `/api/estudiantes/update-field`

Actualiza un campo específico de un estudiante.

**Request Body:**
```json
{
  "telefono": "+573001234567",
  "field": "respuesta",
  "value": "Si"
}
```

**Response 200:**
```json
{
  "success": true,
  "message": "Campo 'respuesta' actualizado correctamente"
}
```

---

### PUT `/api/estudiantes/update-fields`

Actualiza múltiples campos de un estudiante.

**Request Body:**
```json
{
  "telefono": "+573001234567",
  "fields": {
    "respuesta": "Si",
    "estado_envio": "sent"
  }
}
```

---

### DELETE `/api/estudiantes/delete/:phone`

Elimina un estudiante por teléfono.

**Request:**
```http
DELETE /api/estudiantes/delete/573001234567
```

**Response 200:**
```json
{
  "success": true,
  "message": "Estudiante eliminado correctamente"
}
```

---

## 6. Endpoints de Bootcamps

### GET `/api/bootcamps`

Lista todos los bootcamps registrados.

**Response 200:**
```json
{
  "success": true,
  "count": 5,
  "bootcamps": [
    {
      "id": "BT001",
      "nombre": "Inteligencia Artificial",
      "fecha_creacion": "2026-01-15T00:00:00"
    },
    {
      "id": "BT002",
      "nombre": "Desarrollo Web Full Stack",
      "fecha_creacion": "2026-01-15T00:00:00"
    }
  ]
}
```

---

### DELETE `/api/bootcamps/delete/:bootcamp_id`

Elimina un bootcamp por ID.

**Request:**
```http
DELETE /api/bootcamps/delete/BT001
```

---

## 7. Endpoints de Integración

### POST `/api/google/upload`

Importa datos desde un archivo de Google Drive.

**Request Body:**
```json
{
  "fileId": "1abc123def456...",
  "accessToken": "ya29.xxxxx..."
}
```

**Tipos de archivo soportados:**
- Google Sheets
- CSV
- XLSX (Excel)

**Response 200:**
```json
{
  "success": true,
  "message": "Archivo procesado y sincronizado correctamente",
  "file_name": "estudiantes_talento_tech.xlsx",
  "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "total_rows": 150,
  "total_columns": 15,
  "columns": ["nombre", "telefono", "bootcamp_id", ...],
  "drive_updated": true,
  "update_message": "Archivo actualizado en Drive"
}
```

---

### GET `/api/contacts/stats`

Estadísticas de contactos.

**Response 200:**
```json
{
  "success": true,
  "stats": {
    "total_estudiantes": 1234,
    "enviados": 1100,
    "pendientes": 134,
    "respondieron_si": 890,
    "respondieron_no": 110,
    "sin_respuesta": 234
  }
}
```

---

### GET `/api/contacts/pending`

Lista estudiantes pendientes de envío.

**Response 200:**
```json
{
  "success": true,
  "count": 134,
  "contacts": [
    {
      "nombre": "María López",
      "telefono": "+573009876543",
      "bootcamp": "Desarrollo Web",
      "modalidad": "Virtual",
      "opt_in": "TRUE",
      "estado_envio": ""
    }
  ]
}
```

---

### GET `/api/estadisticas`

Estadísticas generales del sistema.

**Response 200:**
```json
{
  "success": true,
  "stats": {
    "total_estudiantes": 1234,
    "total_bootcamps": 5,
    "mensajes_enviados": 1100,
    "mensajes_pendientes": 134,
    "respuestas_si": 890,
    "respuestas_no": 110,
    "sin_respuesta": 234,
    "tasa_respuesta": "85.5%",
    "tasa_confirmacion": "89.0%"
  }
}
```

---

### POST `/api/sync/drive-manual`

Fuerza sincronización manual con Google Drive.

**Request Body:**
```json
{
  "fileId": "1abc123def456...",
  "accessToken": "ya29.xxxxx..."
}
```

---

## 8. Webhook

### GET `/webhook`

Verificación del webhook (handshake con Meta).

**Query Parameters:**
| Parámetro | Descripción |
|-----------|-------------|
| `hub.mode` | Debe ser "subscribe" |
| `hub.verify_token` | Token de verificación configurado |
| `hub.challenge` | Challenge a devolver |

**Response 200:**
```
<hub.challenge value>
```

---

### POST `/webhook`

Recibe notificaciones de WhatsApp.

**Eventos Procesados:**
- Mensajes de texto (respuestas de usuarios)
- Mensajes interactivos (botones, listas)
- Estados de mensajes (enviado, entregado, leído)

**Respuestas Válidas:**
- `Si`, `Sí`, `si`, `sí`, `yes`, `y`, `YES`, `Y`
- `No`, `no`, `n`, `NO`, `N`

**Comportamiento:**
1. Valida que la respuesta sea válida
2. Verifica si el estudiante ya respondió
3. Guarda la respuesta en Turso
4. Envía mensaje de confirmación

---

## 9. Códigos de Error

| Código | Descripción |
|--------|-------------|
| 200 | Éxito |
| 400 | Solicitud inválida (faltan parámetros, formato incorrecto) |
| 404 | Recurso no encontrado |
| 500 | Error interno del servidor |
| 503 | Servicio no disponible (credenciales no configuradas) |

### Errores Comunes

```json
{
  "success": false,
  "error": "No se recibio JSON en el body"
}
```

```json
{
  "success": false,
  "error": "El campo 'phone' es requerido"
}
```

```json
{
  "success": false,
  "error": "Token inválido o expirado"
}
```

---

## Ejemplos con cURL

### Enviar mensaje simple
```bash
curl -X POST https://agent-t-t.onrender.com/api/messages/send-simple \
  -H "Content-Type: application/json" \
  -d '{"phone": "+573001234567", "message": "Hola mundo"}'
```

### Obtener estudiantes
```bash
curl https://agent-t-t.onrender.com/api/estudiantes/all?limit=10
```

### Envío masivo
```bash
curl -X POST https://agent-t-t.onrender.com/api/messages/send-batch \
  -H "Content-Type: application/json" \
  -d '{"template_name": "prueba_matricula", "language_code": "es"}'
```

### Estadísticas
```bash
curl https://agent-t-t.onrender.com/api/estadisticas
```

---

## Rate Limits

La API de WhatsApp Business tiene límites de envío:

| Tier | Mensajes/día |
|------|-------------|
| Tier 1 | 1,000 |
| Tier 2 | 10,000 |
| Tier 3 | 100,000 |
| Tier 4 | Ilimitado |

El tier se incrementa automáticamente según el historial de calidad de mensajes.

---

## Soporte

Para reportar problemas o solicitar funcionalidades:
- Crear issue en el repositorio de GitHub
- Contactar al equipo de desarrollo
