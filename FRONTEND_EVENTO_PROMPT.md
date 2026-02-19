# Prompt para Frontend: Soporte de Campañas Dinámicas (MATRICULA + EVENTO)

## Contexto

El backend ya soporta múltiples tipos de campaña (MATRICULA, EVENTO, INFO). Actualmente el frontend solo gestiona el flujo de MATRÍCULA con template hardcodeado. Necesitamos hacerlo dinámico para soportar distintas plantillas de Meta WhatsApp según el tipo de campaña.

**Base URL**: `https://agent-t-t.onrender.com`

---

## Cambios Requeridos en el Frontend

### 1. FLUJO DE ENVÍO MASIVO (Panel de Control → "Enviar Mensajes Masivos")

#### Estado actual
El botón "Enviar Mensajes Masivos" llama a `POST /api/messages/send-batch` con:
```json
{ "template_name": "prueba_matricula", "language_code": "es" }
```
Siempre crea una campaña MATRICULA automáticamente.

#### Nuevo comportamiento
Antes de enviar, el usuario debe poder:

**A) Seleccionar el tipo de campaña** (dropdown obligatorio):
- MATRICULA → template por defecto: `prueba_matricula` (8 parámetros: nombre, modalidad, bootcamp, fechas, horario, lugar)
- EVENTO → template por defecto: `confirmacion_evento_quindio` (1 parámetro: nombre)
- INFO → template por defecto: `confirmacion_evento_quindio` (1 parámetro: nombre)

La lista de tipos+templates viene de: `GET /api/campaigns/templates`
```json
{
  "success": true,
  "templates": [
    {"tipo": "MATRICULA", "plantilla": "prueba_matricula", "descripcion": "Confirmación de matrícula"},
    {"tipo": "EVENTO", "plantilla": "confirmacion_evento_quindio", "descripcion": "Confirmación de evento"},
    {"tipo": "INFO", "plantilla": "confirmacion_evento_quindio", "descripcion": "Mensaje informativo"}
  ]
}
```

**B) Seleccionar campaña existente O crear nueva**:

Opción 1: **Seleccionar campaña existente** (dropdown con campañas del sistema)
- Endpoint: `GET /api/campaigns` → retorna `{ success, campanas: [{id, nombre, tipo, plantilla_whatsapp, estado, ...}], total }`
- Solo mostrar campañas en estado `DRAFT` o permitir cualquiera
- Al seleccionar, se usan sus datos (tipo, plantilla)

Opción 2: **Crear campaña nueva** (inputs inline)
- Campo: "Nombre de la campaña" (texto libre, ej: "Evento Quindío Feb 2026")
- El tipo ya se seleccionó arriba

**C) Nuevo payload del POST /api/messages/send-batch**:
```json
{
  "tipo": "EVENTO",
  "campana_id": 5,                          // opción A: usar campaña existente
  "campana_nombre": "Evento Quindío",       // opción B: crear nueva (si no hay campana_id)
  "plantilla_whatsapp": "confirmacion_evento_quindio",  // opcional: override
  "language_code": "es",
  "skip_already_sent": true                 // omitir estudiantes ya enviados en este tipo
}
```

**Respuesta exitosa:**
```json
{
  "success": true,
  "message": "Envío masivo completado: 2 enviados, 0 errores",
  "campana_id": 5,
  "template": "confirmacion_evento_quindio",
  "tipo": "EVENTO",
  "stats": { "processed": 2, "sent": 2, "errors": 0 }
}
```

#### UI sugerida para el panel de envío

```
┌──────────────────────────────────────────────────────────────┐
│  📋 Configuración de Envío                                    │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│  Tipo de campaña:  [ MATRICULA ▼ ]                            │
│                                                                │
│  ○ Crear nueva campaña                                         │
│     Nombre: [________________________________]                 │
│                                                                │
│  ○ Usar campaña existente                                      │
│     Campaña: [ Seleccionar campaña... ▼ ]                     │
│                                                                │
│  Plantilla Meta:  prueba_matricula  (auto según tipo)         │
│                                                                │
│  ☑ Omitir estudiantes ya enviados en campañas del mismo tipo  │
│                                                                │
│  [  📤  Enviar Mensajes Masivos  ]                            │
│                                                                │
└──────────────────────────────────────────────────────────────┘
```

Al cambiar el tipo en el dropdown, automáticamente se actualiza el nombre de la plantilla mostrada (solo informativo). Si se selecciona campaña existente, los campos tipo y plantilla se rellenan con los de esa campaña.

---

### 2. CARGA DE EXCEL (Upload desde Drive)

#### Estado actual
El Excel de MATRÍCULA tiene columnas: `telefono_e164, nombre, bootcamp_nombre, modalidad, ingles_inicio, ingles_fin, inicio_formacion, horario, lugar, bootcamp_id`

#### Nuevo comportamiento
El **mismo endpoint** `POST /api/google/upload` ahora soporta ambos formatos de Excel:

**Excel MATRÍCULA** (sin cambios):
| telefono_e164 | nombre | bootcamp_nombre | modalidad | ingles_inicio | ingles_fin | bootcamp_id | ... |

**Excel EVENTO** (nuevo formato):
| Numero_documento | nombre | nombre2 | Apellido1 | Apellido2 | Correo | telefono_e164 | estado_academico |

El backend automáticamente:
- Mapea `Numero_documento` → `documento`, `Correo` → `email`
- Concatena `nombre + nombre2 + Apellido1 + Apellido2` → campo `nombre`
- Detecta si hay bootcamp_id para crear bootcamps, o no

**No se necesitan cambios en la llamada al upload**, el backend detecta las columnas disponibles. La vista previa de la tabla mostrará las columnas normalizadas que retorna el endpoint.

---

### 3. FILTRO DE ESTUDIANTES POR CAMPAÑA (Tab Estudiantes)

#### Estado actual
La vista Estudiantes llama a:
```
GET /api/estudiantes/all?limit=100&offset=0
```
Y tiene filtros por teléfono, programa/bootcamp y estado académico.

#### Nuevo comportamiento
Agregar un dropdown **"Filtrar por campaña"** que pase el parámetro `campana_id`:

```
GET /api/estudiantes/all?limit=100&offset=0&campana_id=5
```

El dropdown se carga desde `GET /api/campaigns`:
```json
{
  "success": true,
  "campanas": [
    { "id": 1, "nombre": "Matrícula Batch 2026-02-19", "tipo": "MATRICULA", "estado": "COMPLETED" },
    { "id": 2, "nombre": "Evento Quindío", "tipo": "EVENTO", "estado": "DRAFT" }
  ]
}
```

Mostrar en el dropdown: `"{nombre} ({tipo}) - {estado}"`, con opción "Todas" que no pasa campana_id.

Cuando se filtra por campaña, la respuesta incluye campos extra por estudiante:
- `cm_estado_envio`: Estado de envío del miembro en esa campaña (pending/sent/error)
- `cm_respuesta`: Respuesta del usuario en esa campaña
- `cm_fecha_envio`: Fecha de envío

Estos campos extra se pueden mostrar como columnas adicionales en la tabla cuando hay filtro de campaña activo.

#### UI sugerida para filtros

```
┌─────────────────────────────────────────────────────────────────────────┐
│  🔍 Filtros                                                              │
├─────────────────────────────────────────────────────────────────────────┤
│  Teléfono: [__________]  Programa: [▼ Todos]  Estado: [▼ Todos]        │
│  Campaña: [▼ Todas las campañas]                   [Buscar] [Limpiar]  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### 4. PESTAÑA CAMPAÑAS (Tab Campañas)

#### Estado actual
Probablemente ya lista campañas. Verificar que muestre: nombre, tipo, plantilla, estado, fecha.

#### Mejoras recomendadas
- Mostrar badge de color por tipo: MATRICULA=azul, EVENTO=verde, INFO=gris
- Mostrar badge de estado: DRAFT=amarillo, SENDING=naranja, COMPLETED=verde
- Botón "Ver miembros" que filtre la vista de Estudiantes por esa campaña
- Mostrar estadísticas inline (enviados / total miembros / respuestas)

Endpoint de estadísticas por campaña:
```
GET /api/campaigns/{id}/stats
```
Respuesta:
```json
{
  "success": true,
  "stats": {
    "campana_id": 5,
    "campana_nombre": "Evento Quindío",
    "campana_tipo": "EVENTO",
    "total_miembros": 50,
    "enviados": 48,
    "pendientes_envio": 0,
    "errores_envio": 2,
    "total_respondidos": 30,
    "sin_respuesta": 18,
    "tasa_respuesta": 62.5,
    "respuestas_detalle": { "ASISTE": 25, "NO_ASISTE": 5 }
  }
}
```

---

## Resumen de Endpoints del Backend

### Nuevos / Modificados

| Método | Endpoint | Cambio | Descripción |
|--------|----------|--------|-------------|
| **GET** | `/api/campaigns/templates` | **NUEVO** | Mapeo tipo → plantilla por defecto |
| **POST** | `/api/messages/send-batch` | **MODIFICADO** | Ahora acepta `tipo`, `campana_id`, `campana_nombre`, `plantilla_whatsapp`, `skip_already_sent` |
| **GET** | `/api/estudiantes/all` | **MODIFICADO** | Nuevo query param `campana_id` para filtrar por campaña |
| **POST** | `/api/google/upload` | *Sin cambios en API* | Backend auto-detecta columnas y concatena nombres |

### Existentes (sin cambios)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| **GET** | `/api/campaigns` | Lista todas las campañas |
| **POST** | `/api/campaigns` | Crear campaña manual |
| **GET** | `/api/campaigns/{id}` | Detalle + stats |
| **GET** | `/api/campaigns/{id}/stats` | Estadísticas de campaña |
| **DELETE** | `/api/campaigns/{id}` | Eliminar campaña |
| **POST** | `/api/campaigns/{id}/members` | Agregar miembros |
| **POST** | `/api/campaigns/{id}/send` | Enviar campaña existente |
| **GET** | `/api/bootcamps` | Listar bootcamps |
| **GET** | `/api/estudiantes/all` | Listar estudiantes paginado |
| **GET** | `/api/estadisticas` | Estadísticas generales |

---

## Esquema de BD (Referencia - 4 tablas normalizadas)

### bootcamps
```sql
id INTEGER PK, codigo TEXT UNIQUE, nombre TEXT, modalidad TEXT,
horario TEXT, lugar TEXT, fecha_inicio_ingles TEXT, fecha_fin_ingles TEXT,
fecha_inicio_tecnica TEXT, fecha_creacion TIMESTAMP
```

### estudiantes
```sql
id INTEGER PK, telefono_e164 TEXT UNIQUE, nombre TEXT, documento TEXT,
email TEXT, bootcamp_id INTEGER FK→bootcamps, opt_in INTEGER DEFAULT 1,
estado_academico TEXT DEFAULT 'INSCRITO', fecha_creacion TIMESTAMP
```

### campanas
```sql
id INTEGER PK, nombre TEXT, tipo TEXT (MATRICULA|EVENTO|INFO),
bootcamp_objetivo_id INTEGER FK→bootcamps, plantilla_whatsapp TEXT,
estado TEXT DEFAULT 'DRAFT' (DRAFT|SENDING|COMPLETED), fecha_creacion TIMESTAMP
```

### campana_miembros
```sql
id INTEGER PK, campana_id INTEGER FK→campanas, estudiante_id INTEGER FK→estudiantes,
variables_contexto TEXT, estado_envio TEXT DEFAULT 'pending' (pending|sent|error),
message_id TEXT, respuesta_usuario TEXT, mensaje_respuesta_raw TEXT,
fecha_envio TIMESTAMP, fecha_respuesta TIMESTAMP
```

---

## Notas Importantes

1. **Prevención de duplicados**: El backend con `skip_already_sent: true` (default) excluye automáticamente estudiantes que ya tienen una campaña `sent` del mismo tipo. El frontend NO necesita implementar esta lógica, solo puede mostrar el checkbox para que el usuario lo desactive si quiere reenviar.

2. **Plantillas de Meta**: Las plantillas están aprobadas en Meta Business. El backend sabe qué parámetros enviar según el tipo:
   - `prueba_matricula`: 8 params (nombre, modalidad, bootcamp_nombre, fecha_inicio_ingles, fecha_fin_ingles, fecha_inicio_tecnica, horario, lugar)
   - `confirmacion_evento_quindio`: 1 param (nombre)

3. **Concatenación de nombre**: Si el Excel tiene columnas `nombre`, `nombre2`, `Apellido1`, `Apellido2`, el backend las concatena automáticamente. El frontend solo ve el campo `nombre` consolidado.

4. **Mapeo de columnas**: `Numero_documento` → `documento`, `Correo` → `email`. Automático en backend.

5. **Campos extra en filtro por campaña**: Cuando se filtra estudiantes por `campana_id`, cada registro incluye `cm_estado_envio`, `cm_respuesta`, `cm_fecha_envio`. Mostrar estas columnas extra cuando el filtro está activo.

6. **Flujo completo EVENTO**:
   - Admin sube Excel con datos de evento → Upload normaliza y guarda estudiantes
   - Admin selecciona tipo=EVENTO, crea/selecciona campaña
   - Admin hace clic en "Enviar Mensajes Masivos" → send-batch envía con template `confirmacion_evento_quindio` usando solo el `nombre`
   - Estudiante recibe WhatsApp → Agente bot maneja la respuesta (ASISTE/NO_ASISTE)
   - Admin ve estadísticas en tab Campañas

7. **Estado "2 estudiantes con opt-in"**: Este label en la UI debería cambiar a "X estudiantes cargados" simplemente, ya que opt_in ya no es un filtro activo.
