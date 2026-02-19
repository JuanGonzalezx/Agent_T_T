# Prompt para Migrar el Frontend al Esquema Normalizado v3

> **Copia y pega TODO este prompt en Copilot dentro del proyecto frontend.**

---

## CONTEXTO

El backend Flask de `Agent_T_T` fue migrado de un esquema **plano/desnormalizado** (todo en tabla `estudiantes`) a un esquema **normalizado v3** con 4 tablas:

```
bootcamps          → Info logística del grupo (modalidad, horario, lugar, fechas)
estudiantes        → Datos maestros del alumno (simplificado, sin tracking de envíos)
campanas           → Contenedores de envíos masivos tipados (MATRICULA, EVENTO, INFO)
campana_miembros   → Tracking individual de cada envío/respuesta por campaña
```

**El frontend actual asume el esquema viejo** donde `estudiantes` tenía campos como `estado_envio`, `respuesta`, `message_id`, `fecha_envio`, `fecha_respuesta`, `bootcamp_nombre`, `modalidad`, etc. directamente. Ahora esos campos vienen por JOIN o están en `campana_miembros`.

---

## CAMBIOS EN EL BACKEND QUE AFECTAN AL FRONTEND

### 1. Tabla `estudiantes` — Campos ELIMINADOS

Los siguientes campos **YA NO EXISTEN** en la tabla `estudiantes`:
```
ELIMINADOS:
- bootcamp_nombre    → ahora viene por JOIN como b.nombre AS bootcamp_nombre
- modalidad          → ahora viene por JOIN como b.modalidad
- horario            → ahora viene por JOIN como b.horario
- lugar              → ahora viene por JOIN como b.lugar
- ingles_inicio      → renombrado a b.fecha_inicio_ingles (en bootcamps)
- ingles_fin         → ELIMINADO completamente
- inicio_formacion   → renombrado a b.fecha_inicio_tecnica (en bootcamps)
- opt_in TEXT         → CAMBIADO a opt_in INTEGER (0 o 1, no "TRUE"/"FALSE")
- estado_envio       → MOVIDO a campana_miembros.estado_envio
- fecha_envio        → MOVIDO a campana_miembros.fecha_envio
- message_id         → MOVIDO a campana_miembros.message_id
- respuesta          → REEMPLAZADO por estudiantes.estado_academico + campana_miembros.respuesta_usuario
- fecha_respuesta    → MOVIDO a campana_miembros.fecha_respuesta
```

### 2. Tabla `estudiantes` — Campos NUEVOS/CAMBIADOS

```sql
CREATE TABLE estudiantes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telefono_e164 TEXT UNIQUE NOT NULL,
    nombre TEXT NOT NULL,
    documento TEXT,                              -- NUEVO
    email TEXT,                                  -- NUEVO
    bootcamp_id INTEGER,                         -- AHORA es FK numérica a bootcamps(id)
    opt_in INTEGER DEFAULT 0,                    -- CAMBIADO: era TEXT, ahora INTEGER (0/1)
    estado_academico TEXT DEFAULT 'INSCRITO',     -- NUEVO: INSCRITO|MATRICULADO|RECHAZADO|GRADUADO
    fecha_creacion TIMESTAMP,
    fecha_actualizacion TIMESTAMP
);
```

### 3. Tabla `bootcamps` — Campos NUEVOS

```sql
CREATE TABLE bootcamps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE NOT NULL,          -- antes era "bootcamp_id TEXT"
    nombre TEXT NOT NULL,                 -- antes era "bootcamp_nombre"
    modalidad TEXT,                       -- NUEVO (antes en estudiantes)
    horario TEXT,                         -- NUEVO (antes en estudiantes)
    lugar TEXT,                           -- NUEVO (antes en estudiantes)
    fecha_inicio_ingles TEXT,             -- NUEVO (antes ingles_inicio en estudiantes)
    fecha_inicio_tecnica TEXT,            -- NUEVO (antes inicio_formacion en estudiantes)
    fecha_creacion TIMESTAMP
);
```

### 4. Tablas NUEVAS: `campanas` y `campana_miembros`

```sql
CREATE TABLE campanas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    tipo TEXT NOT NULL,                   -- 'MATRICULA' | 'EVENTO' | 'INFO'
    bootcamp_objetivo_id INTEGER,
    plantilla_whatsapp TEXT,
    estado TEXT DEFAULT 'DRAFT',          -- 'DRAFT' | 'SENDING' | 'COMPLETED'
    fecha_creacion TIMESTAMP
);

CREATE TABLE campana_miembros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campana_id INTEGER NOT NULL,
    estudiante_id INTEGER NOT NULL,
    variables_contexto TEXT,              -- JSON con params del template
    estado_envio TEXT DEFAULT 'pending',  -- 'pending' | 'sent' | 'error'
    message_id TEXT,
    respuesta_usuario TEXT,              -- 'ASISTE' | 'NO_ASISTE' | 'Sí' | 'No' | NULL
    mensaje_respuesta_raw TEXT,
    fecha_envio TIMESTAMP,
    fecha_respuesta TIMESTAMP
);
```

---

## ENDPOINTS EXISTENTES (RESPUESTAS ACTUALIZADAS)

### GET `/api/estudiantes/all?limit=100&offset=0`
**Respuesta actualizada:** Los datos de bootcamp vienen por JOIN.
```json
{
  "success": true,
  "total": 250,
  "estudiantes": [
    {
      "id": 1,
      "telefono_e164": "573001234567",
      "nombre": "Juan Pérez",
      "documento": "1234567890",
      "email": "juan@email.com",
      "bootcamp_id": 3,
      "opt_in": 1,
      "estado_academico": "MATRICULADO",
      "fecha_creacion": "2026-02-01T10:00:00",
      "fecha_actualizacion": "2026-02-15T14:30:00",
      "bootcamp_codigo": "IA_2024_01",
      "bootcamp_nombre": "Inteligencia Artificial",
      "modalidad": "Presencial",
      "horario": "L-V 6pm-10pm",
      "lugar": "Campus Norte"
    }
  ]
}
```
**NOTA:** Ya NO vienen: `estado_envio`, `fecha_envio`, `message_id`, `respuesta`, `fecha_respuesta`, `ingles_inicio`, `ingles_fin`, `inicio_formacion`.

### GET `/api/estudiantes/bootcamp/{bootcamp_id}`
Misma estructura que el anterior (sin paginación).

### GET `/api/estudiantes/phone/{phone}`
Misma estructura + incluye `fecha_inicio_ingles` y `fecha_inicio_tecnica` del bootcamp.

### GET `/api/estadisticas`
**Respuesta COMPLETAMENTE CAMBIADA:**
```json
{
  "success": true,
  "stats": {
    "total_estudiantes": 250,
    "total_bootcamps": 5,
    "total_campanas": 12,
    "inscritos": 100,
    "matriculados": 80,
    "rechazados": 20,
    "graduados": 50,
    "mensajes_enviados": 200,
    "mensajes_error": 5,
    "total_respuestas": 150,
    "tasa_respuesta": 75.0
  }
}
```
**NOTA:** Ya NO vienen: `confirmaron_si`, `confirmaron_no`, `pendientes_respuesta`. Se reemplazan por `matriculados`, `rechazados`, `inscritos`, `graduados`. Los conteos de envío/respuesta ahora vienen de `campana_miembros`.

### GET `/api/bootcamps`
**Respuesta actualizada:**
```json
{
  "success": true,
  "bootcamps": [
    {
      "id": 1,
      "codigo": "IA_2024_01",
      "nombre": "Inteligencia Artificial",
      "modalidad": "Presencial",
      "horario": "L-V 6pm-10pm",
      "lugar": "Campus Norte",
      "fecha_inicio_ingles": "2026-03-01",
      "fecha_inicio_tecnica": "2026-04-01",
      "fecha_creacion": "2026-01-15T09:00:00"
    }
  ]
}
```

### POST `/api/messages/send-batch`
**Respuesta actualizada** (ahora crea una campaña implícita):
```json
{
  "success": true,
  "message": "Envío masivo completado: 45 enviados, 2 errores",
  "campana_id": 15,
  "stats": {
    "processed": 47,
    "sent": 45,
    "errors": 2
  }
}
```

---

## ENDPOINTS NUEVOS: API DE CAMPAÑAS (`/api/campaigns`)

### POST `/api/campaigns` — Crear campaña
```json
// Request body
{
  "nombre": "Confirmación Matrícula IA Enero",
  "tipo": "MATRICULA",                        // MATRICULA | EVENTO | INFO
  "plantilla_whatsapp": "prueba_matricula",    // Nombre del template en Meta
  "bootcamp_objetivo_id": 3                    // Optional: filtrar por bootcamp
}

// Response (201)
{
  "success": true,
  "campana_id": 15,
  "message": "Campaña \"Confirmación Matrícula IA Enero\" creada con ID 15"
}
```

### GET `/api/campaigns` — Listar campañas
```json
// Response
{
  "success": true,
  "total": 12,
  "campanas": [
    {
      "id": 15,
      "nombre": "Confirmación Matrícula IA Enero",
      "tipo": "MATRICULA",
      "bootcamp_objetivo_id": 3,
      "plantilla_whatsapp": "prueba_matricula",
      "estado": "COMPLETED",
      "fecha_creacion": "2026-02-10T08:00:00"
    }
  ]
}
```

### GET `/api/campaigns/{id}` — Obtener campaña con stats
```json
// Response
{
  "success": true,
  "campana": {
    "id": 15,
    "nombre": "Confirmación Matrícula IA Enero",
    "tipo": "MATRICULA",
    "plantilla_whatsapp": "prueba_matricula",
    "bootcamp_objetivo_id": 3,
    "estado": "COMPLETED",
    "fecha_creacion": "2026-02-10T08:00:00"
  },
  "stats": {
    "campana_id": 15,
    "campana_nombre": "Confirmación Matrícula IA Enero",
    "campana_tipo": "MATRICULA",
    "total_miembros": 50,
    "enviados": 48,
    "pendientes_envio": 0,
    "errores_envio": 2,
    "total_respondidos": 40,
    "sin_respuesta": 8,
    "tasa_respuesta": 83.33,
    "respuestas_detalle": {
      "Sí": 30,
      "No": 10
    }
  }
}
```

### POST `/api/campaigns/{id}/members` — Agregar miembros
```json
// Request body — Opción 1: por IDs directos
{
  "estudiante_ids": [1, 2, 3, 5, 8]
}

// Request body — Opción 2: por bootcamp
{
  "bootcamp_id": "IA_2024_01"
}

// Request body — Opción 3: todos con opt_in
{
  "all_opt_in": true
}

// Response
{
  "success": true,
  "message": "5 miembros agregados a campaña 15",
  "total_added": 5
}
```

### POST `/api/campaigns/{id}/send` — Enviar campaña
```json
// Request body (optional)
{
  "language_code": "es",
  "has_header_param": false
}

// Response
{
  "success": true,
  "message": "Campaña enviada: 48 exitosos, 2 errores",
  "stats": {
    "processed": 50,
    "sent": 48,
    "errors": 2
  }
}
```

### GET `/api/campaigns/{id}/stats` — Estadísticas de campaña
```json
// Response (misma estructura que stats de GET /api/campaigns/{id})
{
  "success": true,
  "stats": {
    "campana_id": 15,
    "campana_nombre": "...",
    "campana_tipo": "MATRICULA",
    "total_miembros": 50,
    "enviados": 48,
    "pendientes_envio": 0,
    "errores_envio": 2,
    "total_respondidos": 40,
    "sin_respuesta": 8,
    "tasa_respuesta": 83.33,
    "respuestas_detalle": { "Sí": 30, "No": 10 }
  }
}
```

### DELETE `/api/campaigns/{id}` — Eliminar campaña
```json
// Response
{
  "success": true,
  "message": "Campaña 15 eliminada"
}
```

---

## ARCHIVOS DEL FRONTEND QUE DEBEN MODIFICARSE

### 1. `src/types/messages.ts` — Actualizar tipos

**Cambiar `Estudiante`:**
```typescript
// ANTES (esquema viejo)
interface Estudiante {
  id: ApiField<number>;
  telefono_e164: ApiField<string>;
  nombre: ApiField<string>;
  bootcamp_id: ApiField<string>;
  bootcamp_nombre: ApiField<string>;
  modalidad: ApiField<string>;
  ingles_inicio?: ApiField<string>;
  ingles_fin?: ApiField<string>;
  inicio_formacion?: ApiField<string>;
  horario?: ApiField<string>;
  lugar?: ApiField<string>;
  opt_in?: ApiField<string>;
  estado_envio: ApiField<string>;
  fecha_envio?: ApiField<string>;
  message_id?: ApiField<string>;
  respuesta?: ApiField<string | null>;
  fecha_respuesta?: ApiField<string>;
  fecha_creacion?: ApiField<string>;
  fecha_actualizacion?: ApiField<string>;
}

// DESPUÉS (esquema normalizado v3)
interface Estudiante {
  id: ApiField<number>;
  telefono_e164: ApiField<string>;
  nombre: ApiField<string>;
  documento?: ApiField<string>;
  email?: ApiField<string>;
  bootcamp_id: ApiField<number>;                // CAMBIADO: ahora es numérico (FK)
  opt_in: ApiField<number>;                     // CAMBIADO: ahora es 0/1 integer
  estado_academico: ApiField<string>;           // NUEVO: INSCRITO|MATRICULADO|RECHAZADO|GRADUADO
  fecha_creacion?: ApiField<string>;
  fecha_actualizacion?: ApiField<string>;
  // Campos de bootcamp que vienen por JOIN:
  bootcamp_codigo?: ApiField<string>;           // NUEVO
  bootcamp_nombre?: ApiField<string>;
  modalidad?: ApiField<string>;
  horario?: ApiField<string>;
  lugar?: ApiField<string>;
  // NOTA: fecha_inicio_ingles y fecha_inicio_tecnica NO vienen en listados generales,
  // solo en búsqueda por teléfono (get_estudiante_by_phone)
}
```

**Cambiar `Estadisticas`:**
```typescript
// ANTES (esquema viejo)
interface Estadisticas {
  total_estudiantes: number;
  mensajes_enviados: number;
  mensajes_error: number;
  confirmaron_si: number;
  confirmaron_no: number;
  pendientes_respuesta: number;
  total_bootcamps: number;
  tasa_respuesta: number;
}

// DESPUÉS (esquema normalizado v3)
interface Estadisticas {
  total_estudiantes: number;
  total_bootcamps: number;
  total_campanas: number;              // NUEVO
  inscritos: number;                   // NUEVO (reemplaza pendientes_respuesta)
  matriculados: number;                // NUEVO (reemplaza confirmaron_si)
  rechazados: number;                  // NUEVO (reemplaza confirmaron_no)
  graduados: number;                   // NUEVO
  mensajes_enviados: number;           // ahora de campana_miembros
  mensajes_error: number;              // ahora de campana_miembros
  total_respuestas: number;            // NUEVO
  tasa_respuesta: number;
}
```

**Agregar tipos NUEVOS para campañas:**
```typescript
interface Campana {
  id: number;
  nombre: string;
  tipo: 'MATRICULA' | 'EVENTO' | 'INFO';
  bootcamp_objetivo_id?: number;
  plantilla_whatsapp: string;
  estado: 'DRAFT' | 'SENDING' | 'COMPLETED';
  fecha_creacion: string;
}

interface CampanaStats {
  campana_id: number;
  campana_nombre: string;
  campana_tipo: string;
  total_miembros: number;
  enviados: number;
  pendientes_envio: number;
  errores_envio: number;
  total_respondidos: number;
  sin_respuesta: number;
  tasa_respuesta: number;
  respuestas_detalle: Record<string, number>;
}

interface CreateCampanaRequest {
  nombre: string;
  tipo: 'MATRICULA' | 'EVENTO' | 'INFO';
  plantilla_whatsapp?: string;
  bootcamp_objetivo_id?: number;
}

interface AddMembersRequest {
  estudiante_ids?: number[];
  bootcamp_id?: string;
  all_opt_in?: boolean;
  variables_contexto?: string[];
}

interface SendCampanaRequest {
  language_code?: string;
  has_header_param?: boolean;
}

interface SendBatchResponse {
  success: boolean;
  message: string;
  campana_id?: number;                // NUEVO: ID de la campaña creada
  stats: {
    processed: number;                // CAMBIADO: antes era "total"
    sent: number;
    errors: number;
  };
}

interface Bootcamp {
  id: number;
  codigo: string;
  nombre: string;
  modalidad?: string;
  horario?: string;
  lugar?: string;
  fecha_inicio_ingles?: string;
  fecha_inicio_tecnica?: string;
  fecha_creacion?: string;
}
```

**Cambiar `MensajesFilters`:**
```typescript
// ANTES
interface MensajesFilters {
  bootcamp_id?: string;
  telefono?: string;
  fecha_inicio?: string;
  fecha_fin?: string;
  estado_envio?: string;     // 'sent' | 'pending' | 'all'
}

// DESPUÉS — reemplazar estado_envio por estado_academico
interface MensajesFilters {
  bootcamp_id?: string;
  telefono?: string;
  fecha_inicio?: string;
  fecha_fin?: string;
  estado_academico?: string;  // 'INSCRITO' | 'MATRICULADO' | 'RECHAZADO' | 'GRADUADO' | 'all'
}
```

### 2. `src/api/messages.ts` — Agregar funciones de campañas

Agregar estas funciones nuevas:
```typescript
// ─── CAMPAÑAS API ───
export async function getCampanas() {
  return request<{ success: boolean; campanas: Campana[]; total: number }>('/api/campaigns');
}

export async function getCampana(id: number) {
  return request<{ success: boolean; campana: Campana; stats: CampanaStats }>(`/api/campaigns/${id}`);
}

export async function createCampana(data: CreateCampanaRequest) {
  return request<{ success: boolean; campana_id: number; message: string }>('/api/campaigns', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function addCampanaMembers(campanaId: number, data: AddMembersRequest) {
  return request<{ success: boolean; message: string; total_added: number }>(`/api/campaigns/${campanaId}/members`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function sendCampana(campanaId: number, data?: SendCampanaRequest) {
  return request<{ success: boolean; message: string; stats: { processed: number; sent: number; errors: number } }>(`/api/campaigns/${campanaId}/send`, {
    method: 'POST',
    body: JSON.stringify(data || {}),
  });
}

export async function getCampanaStats(campanaId: number) {
  return request<{ success: boolean; stats: CampanaStats }>(`/api/campaigns/${campanaId}/stats`);
}

export async function deleteCampana(campanaId: number) {
  return request<{ success: boolean; message: string }>(`/api/campaigns/${campanaId}`, {
    method: 'DELETE',
  });
}
```

### 3. `src/hooks/use-messages.ts` — Agregar hooks de campañas

```typescript
export function useCampanas() {
  return useQuery({
    queryKey: ['campanas'],
    queryFn: getCampanas,
    staleTime: STALE_TIMES.SHORT,
  });
}

export function useCampana(id: number) {
  return useQuery({
    queryKey: ['campana', id],
    queryFn: () => getCampana(id),
    staleTime: STALE_TIMES.SHORT,
    enabled: !!id,
  });
}
```

### 4. `src/components/messages/MessagesStats.tsx`
- Reemplazar `confirmaron_si` por `matriculados`
- Reemplazar `confirmaron_no` por `rechazados`
- Reemplazar `pendientes_respuesta` por `inscritos`
- Agregar card de `graduados`
- Agregar card o badge de `total_campanas`

### 5. `src/components/messages/MessagesFilters.tsx`
- Reemplazar filtro "Estado" (`sent`/`pending`/`error`) por "Estado Académico" (`INSCRITO`/`MATRICULADO`/`RECHAZADO`/`GRADUADO`)
- Ese filtro se sigue aplicando en frontend (no requiere endpoint nuevo)

### 6. `src/components/messages/MessagesTable.tsx`
- Columna "Estado" → ahora mostrar `estado_academico` en vez de `estado_envio`
- Columna "Respuesta" → ahora mostrar `estado_academico` en vez del campo `respuesta`
- La columna "Fecha" → usar `fecha_creacion` o `fecha_actualizacion` (ya no hay `fecha_envio` directo)
- Agregar columna opcional "Documento" y/o "Email"

### 7. `src/components/messages/StatusBadge.tsx`
- Rediseñar para mostrar estados académicos:
  - `INSCRITO` → badge azul/neutro "Inscrito"
  - `MATRICULADO` → badge verde "Matriculado"
  - `RECHAZADO` → badge rojo "Rechazado"
  - `GRADUADO` → badge dorado/morado "Graduado"
- Eliminar badges de `sent`/`error`/`pending` (o moverlos a vista de campaña)

### 8. `src/components/SendBatchCard.tsx`
- Ya no puede calcular "pendientes" filtrando `estado_envio !== 'sent'` en tabla estudiantes
- Ahora el envío masivo crea una campaña implícita. Mostrar `campana_id` en el resultado.
- Los pendientes ahora son los estudiantes con `opt_in = 1` (respuesta de `GET /api/contacts/pending`)
- Considerar agregar selector de tipo de campaña (MATRICULA/EVENTO/INFO) antes de enviar

### 9. `src/components/SendCampaignCard.tsx`
- El upload sigue funcionando igual (`POST /api/google/upload`)
- Datos del preview ya no tendrán `estado_envio`, `respuesta`, etc.
- Columnas del CSV ahora incluirán `opt_in`, `estado_academico`, `documento`, `email`

### 10. NUEVA VISTA SUGERIDA: Campañas (`/campaigns`)
Agregar una nueva página/ruta para gestionar campañas:
- **Lista de campañas** con tabla: nombre, tipo, estado, fecha, acciones
- **Crear campaña**: formulario con nombre, tipo (MATRICULA/EVENTO/INFO), plantilla, bootcamp objetivo
- **Detalle de campaña**: stats (enviados, pendientes, respondidos, tasa_respuesta, respuestas_detalle)
- **Agregar miembros**: por bootcamp, por IDs, o todos con opt_in
- **Enviar campaña**: botón que ejecuta POST `/api/campaigns/{id}/send`
- **Badge de estado**: DRAFT (gris) → SENDING (amarillo) → COMPLETED (verde)

---

## RESUMEN DE TAREAS (CHECKLIST)

1. **Actualizar `src/types/messages.ts`:**
   - [ ] Modificar tipo `Estudiante` (quitar campos viejos, agregar nuevos)
   - [ ] Modificar tipo `Estadisticas` (nuevos campos de estado académico)
   - [ ] Modificar tipo `MensajesFilters` (estado_academico en vez de estado_envio)
   - [ ] Agregar tipos: `Campana`, `CampanaStats`, `CreateCampanaRequest`, `AddMembersRequest`, `SendCampanaRequest`, `Bootcamp`
   - [ ] Actualizar `SendBatchResponse` (agregar `campana_id`, cambiar `total` a `processed`)

2. **Actualizar `src/api/messages.ts`:**
   - [ ] Agregar 7 funciones de campañas (getCampanas, getCampana, createCampana, addCampanaMembers, sendCampana, getCampanaStats, deleteCampana)

3. **Actualizar `src/hooks/use-messages.ts`:**
   - [ ] Agregar hooks: `useCampanas()`, `useCampana(id)`

4. **Actualizar componentes de Messages:**
   - [ ] `MessagesStats.tsx`: Usar nuevos campos de estadísticas (matriculados, rechazados, inscritos, graduados)
   - [ ] `MessagesFilters.tsx`: Reemplazar filtro estado_envio por estado_academico
   - [ ] `MessagesTable.tsx`: Cambiar columnas (estado_academico, quitar fecha_envio)
   - [ ] `StatusBadge.tsx`: Nuevos badges para INSCRITO/MATRICULADO/RECHAZADO/GRADUADO

5. **Actualizar componentes de Dashboard:**
   - [ ] `SendBatchCard.tsx`: Adaptar cálculo de pendientes (usar opt_in, no estado_envio)
   - [ ] `SendCampaignCard.tsx`: Adaptar preview a nuevas columnas del CSV

6. **Crear nueva funcionalidad de Campañas:**
   - [ ] Nueva ruta `/campaigns` en React Router
   - [ ] Agregar tab "Campañas" en Layout.tsx
   - [ ] Página `Campaigns.tsx` con lista, creación, detalle y envío
   - [ ] Componentes: `CampaignList`, `CampaignDetail`, `CampaignCreateForm`

7. **Actualizar constantes (`src/lib/constants.ts`):**
   - [ ] Agregar `ROUTES.CAMPAIGNS = '/campaigns'`
   - [ ] Agregar constantes de tipos de campaña si aplica

8. **Actualizar tests:**
   - [ ] Actualizar mocks de `Estudiante` en tests existentes
   - [ ] Actualizar mocks de `Estadisticas` en tests existentes
   - [ ] Agregar tests para funciones API de campañas
   - [ ] Agregar tests para nuevos hooks
