# Agent_T_T — Agente Virtual WhatsApp para Talento Tech

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Flask-3.0-green?logo=flask" alt="Flask">
  <img src="https://img.shields.io/badge/LangGraph-0.2-orange?logo=langchain" alt="LangGraph">
  <img src="https://img.shields.io/badge/Gemini-2.5_Flash_Lite-4285F4?logo=google" alt="Gemini">
  <img src="https://img.shields.io/badge/Database-Turso%20%7C%20SQLite-purple" alt="Turso/SQLite">
  <img src="https://img.shields.io/badge/WhatsApp-Business%20API%20v22.0-25D366?logo=whatsapp" alt="WhatsApp">
  <img src="https://img.shields.io/badge/Tests-173+-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/Deploy-Render-46E3B7" alt="Render">
</p>

Backend Flask con agente conversacional de IA (LangGraph + Gemini 2.5 Flash Lite) que funciona como asistente virtual de WhatsApp para el programa **Talento Tech** del MinTIC (Colombia). Gestiona matrículas, confirmación de eventos, captación de interesados, envíos masivos por campañas multi-tipo, importación de datos desde Google Drive, y consultas automáticas de estudiantes con respuestas determinísticas de costo cero en IA.

---

## 📋 Tabla de Contenidos

- [Características](#-características)
- [Stack Tecnológico](#-stack-tecnológico)
- [Arquitectura](#-arquitectura)
- [Agente IA — Grafo LangGraph](#-agente-ia--grafo-langgraph)
- [Base de Datos](#-base-de-datos)
- [Protección de Datos en Upload](#-protección-de-datos-en-upload)
- [Sistema de Campañas Multi-Tipo](#-sistema-de-campañas-multi-tipo)
- [Requisitos Previos](#-requisitos-previos)
- [Instalación](#-instalación)
- [Configuración](#-configuración)
- [Uso](#-uso)
- [API REST — Endpoints](#-api-rest--endpoints)
- [Tests](#-tests)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Despliegue](#-despliegue)
- [Seguridad](#-seguridad)
- [Monitoreo](#-monitoreo)
- [Historial de Cambios](#-historial-de-cambios)
- [Contribución](#-contribución)
- [Contacto](#-contacto)

---

## ✨ Características

| Funcionalidad | Descripción |
|---|---|
| **Agente IA conversacional** | Grafo LangGraph de 8 nodos con router inteligente (fast-path por keywords + fallback Gemini 2.5 Flash Lite) |
| **Respuestas determinísticas (0 tokens)** | Saludos, 7 categorías de FAQ, despedidas, OK y agradecimientos — costo cero de IA |
| **Campañas multi-tipo** | Creación y envío de campañas `MATRICULA`, `EVENTO`, `INFO` y `CAPTACION` con tracking individual por estudiante |
| **Confirmación de matrícula** | Flujo Sí/No con actualización de `estado_academico` (`INSCRITO` → `MATRICULADO`/`RECHAZADO`) |
| **Confirmación de eventos** | Flujo Asisto/No Asisto independiente del estado académico (solo actualiza `campana_miembros`) |
| **Captación de interesados** | Campañas de tipo `CAPTACION` con template `mensaje_interesados` para leads |
| **Catálogo de plantillas INFO** | Sistema extensible con `recordatorio_presencial`, `recordatorio_virtual` y `mensaje_interesados`, cada uno con parámetros definidos |
| **Consulta de estado** | Respuesta determinística del estado de inscripción: `INSCRITO`, `MATRICULADO`, `RECHAZADO`, `GRADUADO` |
| **Acceso a plataforma** | Credenciales de talentotech2.com.co/campus basadas en número de cédula |
| **Envío masivo seguro** | Batch hasta 10,000 estudiantes con `skip_already_sent` para evitar duplicados por tipo de campaña |
| **Envío incremental** | Modo A (campaña existente) permite agregar estudiantes progresivamente sin crear nuevas campañas |
| **Resolución dinámica de plantillas** | Cada tipo de campaña resuelve automáticamente su plantilla Meta y `language_code` (ej: `es_CO` para EVENTO) |
| **Integración Google Drive** | Importación desde Sheets/CSV/XLSX con normalización automática de teléfonos, alias de columnas y concatenación de nombres |
| **Protección de datos existentes** | En re-upload, los datos originales del estudiante (nombre, documento, email, bootcamp, estado) se preservan — nunca se sobrescriben |
| **Sincronización bidireccional** | Scheduler APScheduler cada 5 min para sync automático con Drive |
| **Deduplicación en RAM** | Cache LRU thread-safe (TTL 5 min, max 5000 entradas) para evitar procesamiento de mensajes duplicados |
| **Modo dual** | Agente IA (LangGraph) o modo legacy (regex) configurable con `USE_AI_AGENT=True/False` |
| **173+ tests** | Suite completa: agente IA (~47), controladores (~28), normalización (~33), BD (~45), inserciones (5), lógica legacy (10), integración Turso (5) |

---

## 🛠 Stack Tecnológico

| Capa | Tecnología |
|---|---|
| Framework Web | Flask 3.0 + Flask-CORS + Gunicorn + Werkzeug |
| Agente IA | LangGraph 0.2 + LangChain Core 0.3 + LangChain Google GenAI |
| Modelo LLM | Gemini 2.5 Flash Lite (`temp=0.0, max_tokens=10` para router · `temp=0.3` para FAQ) |
| Base de Datos | Turso/libSQL vía HTTP Pipeline API (producción) · SQLite con WAL mode (desarrollo) |
| Mensajería | WhatsApp Business Cloud API v22.0 (Meta Graph API) |
| Almacenamiento | Google Drive API v3 + Google Sheets API v4 |
| Scheduler | APScheduler 3.10 (BackgroundScheduler, intervalo 5 min) |
| Datos | Pandas + OpenPyXL |
| Deploy | Render (backend) · Vercel (frontend) |

---

## 🏗 Arquitectura

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USUARIO (WhatsApp)                                │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │ POST /webhook
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    BACKEND FLASK (Render/Gunicorn)                           │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    webhook_controller.py                            │    │
│  │  1. Parsear JSON del mensaje                                       │    │
│  │  2. Filtrar statuses (sent/delivered/read)                         │    │
│  │  3. Filtro de antigüedad (>5 min → descartado)                    │    │
│  │  4. Deduplicación atómica en RAM (LRU, TTL 5 min)                │    │
│  │  5. Soporte: text, button_reply, list_reply, button legacy         │    │
│  │  6. Responder 200 inmediato → procesar en daemon thread            │    │
│  └────────────────────────────┬────────────────────────────────────────┘    │
│                               │                                             │
│               ┌───────────────┴───────────────┐                             │
│               │  USE_AI_AGENT = True?          │                            │
│               ├──── Sí ───────┤──── No ────────┤                            │
│               ▼               ▼                                             │
│  ┌────────────────┐  ┌─────────────────┐                                   │
│  │  AGENTE IA     │  │  ResponseLogic  │                                   │
│  │  (LangGraph)   │  │  (Regex legacy) │                                   │
│  │  8 nodos       │  │  Sí/No → BD     │                                   │
│  └───────┬────────┘  └─────────────────┘                                   │
│          ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      SERVICIOS                                      │    │
│  │  WhatsAppService      ◄──► Meta Graph API (v22.0)                   │    │
│  │  DatabaseHandler      ◄──► Turso HTTP Pipeline (prod) / SQLite (dev)│    │
│  │  GoogleDriveService   ◄──► Google Drive API v3 + Sheets API v4      │    │
│  │  SyncService          ◄──► APScheduler (cada 5 min)                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Flujo de Datos

1. **Importación** → Google Drive → `/api/google/upload` → normalización Pandas → UPSERT en Turso (preserva datos existentes)
2. **Campañas** → Crear campaña (4 tipos) → agregar miembros → enviar → WhatsApp Business API → tracking por estudiante
3. **Respuesta entrante** → WhatsApp → Webhook → Deduplicación → Agente IA (grafo LangGraph) → respuesta + actualización BD
4. **Visualización** → Turso → API REST → Frontend React (Vercel)
5. **Sincronización** → APScheduler cada 5 min → Turso ↔ Google Drive

---

## 🤖 Agente IA — Grafo LangGraph

El agente procesa cada mensaje entrante a través de un grafo dirigido (StateGraph) con 8 nodos especializados:

```
                    ┌── confirm_event    ─► END   (Asisto / No Asisto)
                    ├── confirm_response ─► END   (Sí / No matrícula)
load_context ──►    ├── check_status     ─► END   (Estado académico)
     │          ┌──►├── platform_access  ─► END   (Credenciales plataforma)
 (Busca datos   │   ├── quick_response  ─► END   (0 tokens: saludos, FAQ)
  en Turso +    │   └── general_response ─► END   (Gemini FAQ fallback)
  campaña   )   │
     │          │
     ▼          │
router_gemini ──┘
 (fast-path keywords → Gemini fallback si no clasifica)
```

### AgentState (TypedDict)

```python
{
  "messages":        List[dict]      # Historial de mensajes (auto-acumulación)
  "phone":           str             # Teléfono E.164
  "student_name":    Optional[str]   # Nombre del estudiante
  "student_data":    Optional[dict]  # Contexto completo desde BD
  "active_campaign": Optional[dict]  # Campaña activa pendiente de respuesta
  "intent":          Optional[str]   # Clasificación del router
}
```

### Router — Sistema de Prioridades

| Prioridad | Condición | Intent | Costo IA |
|---|---|---|---|
| 0 | Campaña `EVENTO` activa sin respuesta | `CONFIRM_EVENT` | 0 tokens |
| 0 | Campaña `MATRICULA` activa sin respuesta | `CONFIRM` | 0 tokens |
| 1 | Keywords de estado/matrícula (`estado`, `matrícula`, `cómo voy`) | `STATUS` | 0 tokens |
| 1 | Keywords de acceso/plataforma (`acceso`, `plataforma`, `clave`, `contraseña`) | `ACCESS` | 0 tokens |
| 1 | Saludos (`hola`, `buenos`, `hey`) | `SALUDO` | 0 tokens |
| 1 | Agradecimientos (`gracias`, `thanks`) | `GRACIAS` | 0 tokens |
| 1 | Confirmaciones (`ok`, `listo`, `perfecto`) | `OK` | 0 tokens |
| 1 | Despedidas (`chao`, `adiós`, `bye`) | `DESPEDIDA` | 0 tokens |
| 1 | FAQ Talento Tech, inscripción, bootcamps, horarios, certificados, costos, contacto | `INFO_TALENTO` `INFO_INSCRIPCION` `INFO_BOOTCAMPS` `INFO_HORARIO` `INFO_CERTIFICADO` `INFO_COSTO` `INFO_CONTACTO` | 0 tokens |
| 2 | Mensaje no clasificado por fast-path | `STATUS` / `ACCESS` / `GENERAL` | ~10 tokens (Gemini router) |

### Nodos del Grafo

| Nodo | Archivo | Función |
|---|---|---|
| `load_context` | `nodes/load_context.py` | Busca estudiante por teléfono + carga campaña activa (tipo EVENTO/MATRICULA, sin respuesta) |
| `router_gemini` | `graph.py` | Clasifica intención: fast-path por keywords (prioridad 0-1) → Gemini fallback (prioridad 2) |
| `confirm_event` | `nodes/confirm_event.py` | Procesa Asisto/No Asisto → actualiza `campana_miembros.respuesta_usuario` (ASISTE/NO_ASISTE) |
| `confirm_response` | `nodes/confirm.py` | Procesa Sí/No → actualiza `estado_academico` (MATRICULADO/RECHAZADO) + `campana_miembros` |
| `check_status` | `nodes/status.py` | Respuesta determinística según `estado_academico` (INSCRITO/MATRICULADO/RECHAZADO/GRADUADO) |
| `platform_access` | `nodes/platform.py` | Credenciales de talentotech2.com.co/campus (usuario y contraseña = número de cédula) |
| `quick_response` | `nodes/quick_response.py` | 11+ respuestas determinísticas (0 tokens): saludos, FAQ, despedidas, OK, agradecimientos |
| `general_response` | `nodes/fallback.py` | FAQ con Gemini 2.5 Flash Lite (`temp=0.3`, máx 3 líneas), con fallback estático si falla |

---

## 🗄 Base de Datos

Esquema normalizado v3 con 4 tablas + 7 índices. Soporte dual: **Turso** (producción vía HTTP Pipeline `/v2/pipeline`) y **SQLite** (desarrollo local con WAL mode). Detección automática por variables de entorno.

### Diagrama Relacional

```
┌──────────────┐       ┌──────────────────┐
│  bootcamps   │       │   estudiantes    │
│──────────────│       │──────────────────│
│ id (PK)      │◄──FK──│ bootcamp_id      │
│ codigo (UQ)  │       │ id (PK)          │
│ nombre       │       │ telefono_e164(UQ)│
│ modalidad    │       │ nombre           │
│ horario      │       │ documento        │
│ lugar        │       │ email            │
│ fecha_*      │       │ opt_in           │
└──────┬───────┘       │ estado_academico │
       │               └────────┬─────────┘
       │                        │
       │    ┌───────────────┐   │
       │    │   campanas    │   │
       │    │───────────────│   │
       └─FK─│ bootcamp_obj  │   │
            │ id (PK)       │   │
            │ nombre        │   │
            │ tipo          │   │
            │ plantilla_wa  │   │
            │ estado        │   │
            └───────┬───────┘   │
                    │           │
            ┌───────┴───────────┴──────┐
            │   campana_miembros       │
            │──────────────────────────│
            │ id (PK)                  │
            │ campana_id (FK)          │
            │ estudiante_id (FK)       │
            │ UNIQUE(campana, estud.)  │
            │ variables_contexto       │
            │ estado_envio             │
            │ message_id               │
            │ respuesta_usuario        │
            │ mensaje_respuesta_raw    │
            │ fecha_envio              │
            │ fecha_respuesta          │
            └──────────────────────────┘
```

### DDL — Tablas

#### `bootcamps`
```sql
CREATE TABLE IF NOT EXISTS bootcamps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE NOT NULL,
    nombre TEXT NOT NULL,
    modalidad TEXT,
    horario TEXT,
    lugar TEXT,
    fecha_inicio_ingles TEXT,
    fecha_fin_ingles TEXT,
    fecha_inicio_tecnica TEXT,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `codigo` | TEXT UNIQUE | Código único (ej: `IA_2024_01`) |
| `nombre` | TEXT NOT NULL | Nombre del bootcamp |
| `modalidad` | TEXT | Presencial / Virtual / Híbrido |
| `horario` | TEXT | Horario de clases |
| `lugar` | TEXT | Sede / ubicación |
| `fecha_inicio_ingles` | TEXT | Inicio módulo inglés |
| `fecha_fin_ingles` | TEXT | Fin módulo inglés |
| `fecha_inicio_tecnica` | TEXT | Inicio formación técnica |
| `fecha_creacion` | TIMESTAMP | Creación automática |

#### `estudiantes`
```sql
CREATE TABLE IF NOT EXISTS estudiantes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telefono_e164 TEXT UNIQUE NOT NULL,
    nombre TEXT NOT NULL,
    documento TEXT,
    email TEXT,
    bootcamp_id INTEGER,
    opt_in INTEGER DEFAULT 1,
    estado_academico TEXT DEFAULT 'INSCRITO',
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(bootcamp_id) REFERENCES bootcamps(id)
);
-- Índices: idx_estudiantes_telefono, idx_estudiantes_bootcamp, idx_estudiantes_estado
```

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `telefono_e164` | TEXT UNIQUE | Formato E.164 (ej: `573001234567`) |
| `nombre` | TEXT NOT NULL | Nombre completo |
| `documento` | TEXT | Cédula / ID |
| `email` | TEXT | Correo electrónico |
| `bootcamp_id` | INTEGER FK | Referencia a `bootcamps(id)` |
| `opt_in` | INTEGER | `0`=No contactar, `1`=Contactable |
| `estado_academico` | TEXT | `INSCRITO` → `MATRICULADO` / `RECHAZADO` / `GRADUADO` |
| `fecha_creacion` | TIMESTAMP | Fecha de registro |

#### `campanas`
```sql
CREATE TABLE IF NOT EXISTS campanas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    tipo TEXT NOT NULL,
    bootcamp_objetivo_id INTEGER,
    plantilla_whatsapp TEXT,
    estado TEXT DEFAULT 'DRAFT',
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(bootcamp_objetivo_id) REFERENCES bootcamps(id)
);
-- Índices: idx_campanas_tipo, idx_campanas_estado
```

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `nombre` | TEXT NOT NULL | Nombre de la campaña |
| `tipo` | TEXT NOT NULL | `MATRICULA` / `EVENTO` / `INFO` / `CAPTACION` |
| `bootcamp_objetivo_id` | INTEGER FK | Filtro opcional por bootcamp |
| `plantilla_whatsapp` | TEXT | Nombre del template en Meta Business |
| `estado` | TEXT | `DRAFT` → `SENDING` → `COMPLETED` |
| `fecha_creacion` | TIMESTAMP | Fecha de creación |

#### `campana_miembros`
```sql
CREATE TABLE IF NOT EXISTS campana_miembros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campana_id INTEGER NOT NULL,
    estudiante_id INTEGER NOT NULL,
    variables_contexto TEXT,
    estado_envio TEXT DEFAULT 'pending',
    message_id TEXT,
    respuesta_usuario TEXT,
    mensaje_respuesta_raw TEXT,
    fecha_envio TIMESTAMP,
    fecha_respuesta TIMESTAMP,
    FOREIGN KEY(campana_id) REFERENCES campanas(id),
    FOREIGN KEY(estudiante_id) REFERENCES estudiantes(id),
    UNIQUE(campana_id, estudiante_id)
);
-- Índices: idx_cm_campana, idx_cm_estudiante, idx_cm_estado, idx_cm_campana_estudiante
```

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `campana_id` | INTEGER FK | Referencia a `campanas(id)` |
| `estudiante_id` | INTEGER FK | Referencia a `estudiantes(id)` |
| `variables_contexto` | TEXT | JSON con parámetros del template WhatsApp |
| `estado_envio` | TEXT | `pending` → `sent` / `failed` |
| `message_id` | TEXT | ID de WhatsApp (`wamid.xxx`) |
| `respuesta_usuario` | TEXT | `ASISTE` / `NO_ASISTE` / `Sí` / `No` / `NULL` |
| `mensaje_respuesta_raw` | TEXT | Texto literal del usuario |
| `fecha_envio` | TIMESTAMP | Momento del envío |
| `fecha_respuesta` | TIMESTAMP | Momento de la respuesta |

### Métodos Principales de `DatabaseHandler`

| Grupo | Método | Descripción |
|---|---|---|
| **Bootcamps** | `insert_or_update_bootcamp(codigo, nombre, ...)` | UPSERT por `codigo` |
| | `get_bootcamp_by_codigo(codigo)` | Buscar por código |
| | `get_bootcamp_by_id(id)` | Buscar por ID numérico |
| | `get_all_bootcamps()` | Listar todos |
| | `delete_bootcamp(codigo)` | Eliminar por código |
| **Estudiantes** | `insert_or_update_estudiante(data)` | UPSERT por `telefono_e164` (preserva datos existentes) |
| | `get_estudiante_by_phone(telefono)` | Buscar con JOIN a bootcamp |
| | `get_estudiantes_by_bootcamp(id)` | Filtrar por bootcamp |
| | `get_estudiantes_by_bootcamp_and_estado(id, estado)` | Filtrar por bootcamp + estado académico |
| | `get_estudiantes_opt_in()` | Todos los contactables |
| | `get_estudiantes_sin_campana_enviada(tipo)` | Sin campaña enviada del tipo dado |
| | `get_all_estudiantes(limit, offset, campana_id)` | Paginado con filtro opcional |
| | `update_estudiante_field(tel, campo, valor)` | Actualizar campo individual |
| | `update_estudiante_fields(tel, dict)` | Actualizar múltiples campos |
| | `delete_estudiante(telefono)` | Eliminar por teléfono |
| **Respuestas** | `get_respuesta_existente(telefono)` | Verificar si ya respondió |
| | `update_respuesta(tel, respuesta, fecha)` | Actualizar respuesta + estado académico |
| **Campañas** | `insert_campana(nombre, tipo, plantilla, bootcamp_id)` | Crear campaña |
| | `get_campana_by_id(id)` | Obtener por ID |
| | `get_all_campanas()` | Listar todas |
| | `delete_campana(id)` | Eliminar campaña + miembros |
| | `update_campana_estado(id, estado)` | Cambiar estado |
| | `get_campana_stats(id)` | Estadísticas detalladas |
| **Miembros** | `insert_campana_miembros(campana_id, est_ids, vars)` | Agregar en lote |
| | `get_miembros_pendientes_envio(campana_id)` | Pendientes con JOIN |
| | `update_miembro_estado_envio(id, estado, msg_id)` | Marcar enviado/fallido |
| | `update_miembro_respuesta(id, respuesta, raw)` | Registrar respuesta |
| | `get_campana_activa_for_student(est_id)` | Campaña activa pendiente |
| | `get_estudiantes_by_campana(campana_id)` | Miembros de una campaña |
| | `count_miembros_campana(campana_id)` | Contar miembros |

---

## 🛡 Protección de Datos en Upload

Cuando se cargan estudiantes que ya existen en la base de datos (mismo `telefono_e164`), el sistema **preserva los datos originales** del estudiante. Esto evita que un re-upload o una segunda campaña sobrescriba información crítica.

### Comportamiento del UPSERT (`ON CONFLICT`)

| Campo | Estudiante nuevo | Estudiante existente |
|---|---|---|
| `nombre` | Se inserta el valor del archivo | Se preserva el existente |
| `documento` | Se inserta el valor del archivo | Se preserva si ya tenía uno; solo se llena si estaba vacío |
| `email` | Se inserta el valor del archivo | Se preserva si ya tenía uno; solo se llena si estaba vacío |
| `bootcamp_id` | Se inserta el valor del archivo | Se preserva el existente; solo se asigna si no tenía |
| `opt_in` | Se establece en `1` | Se re-activa a `1` (contactable) |
| `estado_academico` | Default: `INSCRITO` | Se preserva el existente siempre |

**Ejemplo práctico:** Si un estudiante fue cargado en la Campaña 1 (Bootcamp 2) y luego aparece en el archivo de la Campaña 2 (Bootcamp 3), su `bootcamp_id` sigue siendo el del Bootcamp 2 y su `estado_academico` no cambia.

---

## 📨 Sistema de Campañas Multi-Tipo

El backend soporta 4 tipos de campaña, cada uno con su plantilla Meta WhatsApp, parámetros y `language_code` específico:

### Tipos de Campaña y Plantillas

| Tipo | Plantilla por defecto | Language Code | Parámetros | Descripción |
|---|---|---|---|---|
| `MATRICULA` | `prueba_matricula` | `es` | nombre, modalidad, bootcamp_nombre, fecha_inicio_ingles, fecha_fin_ingles, fecha_inicio_tecnica, horario, lugar | Confirmación de matrícula con flujo Sí/No |
| `EVENTO` | `confirmacion_evento_quindio` | `es_CO` | nombre | Confirmación de asistencia Asisto/No Asisto |
| `INFO` | `recordatorio_presencial` | `es` | (según catálogo) | Recordatorios y anuncios informativos |
| `CAPTACION` | `mensaje_interesados` | `es` | nombre | Captación de leads / interesados |

### Catálogo de Plantillas INFO

| Plantilla | Parámetros | Uso |
|---|---|---|
| `recordatorio_presencial` | nombre, bootcamp_nombre, fecha_inicio_tecnica, horario, lugar | Recordatorio inicio bootcamp presencial |
| `recordatorio_virtual` | nombre, bootcamp_nombre, fecha_inicio_tecnica, horario, link_plataforma | Recordatorio inicio bootcamp virtual |
| `mensaje_interesados` | nombre | Mensaje para captación de interesados |

### Flujo de Envío Masivo (send-batch)

El endpoint `send-batch` opera en 8 pasos atómicos:

1. **Resolver campaña** — Modo A (existente) o Modo B (crear nueva)
2. **Filtrar duplicados** — `skip_already_sent` excluye estudiantes ya enviados en campaña del mismo tipo
3. **Crear campaña** — Solo modo B, si todos fueron filtrados no se crea
4. **Agregar miembros** — INSERT OR IGNORE (duplicados se ignoran)
5. **Validar pendientes** — Verifica que haya miembros sin enviar
6. **Resolver plantilla** — Determina template y `language_code` por tipo
7. **Obtener pendientes** — Solo miembros con `estado_envio = 'pending'`
8. **Enviar mensajes** — Secuencial con `DELAY_SECONDS` entre cada envío

---

## 📦 Requisitos Previos

- **Python** 3.10 o superior
- **Cuenta Meta Business** con WhatsApp Business API configurada
- **Cuenta Turso** (base de datos cloud) o SQLite local para desarrollo
- **Cuenta Google Cloud** (opcional, para integración con Google Drive/Sheets)
- **Google Gemini API Key** (para el agente IA)

---

## 🚀 Instalación

### 1. Clonar el Repositorio

```bash
git clone https://github.com/JuanGonzalezx/Agent_T_T.git
cd Agent_T_T
```

### 2. Crear Entorno Virtual

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### Dependencias (14 paquetes principales)

| Grupo | Paquetes |
|---|---|
| Framework Web | `Flask>=3.0.0`, `flask-cors>=4.0.0`, `gunicorn>=21.0.0`, `Werkzeug>=3.0.0` |
| Base de Datos | `libsql-experimental>=0.0.47` |
| APIs Externas | `requests>=2.31.0`, `python-dotenv>=1.0.0` |
| Procesamiento | `pandas>=2.0.0`, `openpyxl>=3.1.0` |
| Scheduler | `APScheduler>=3.10.0` |
| Agente IA | `langgraph>=0.2.0`, `langgraph-cli>=0.1.0`, `langchain-google-genai>=2.0.0`, `langchain-core>=0.3.0` |
| Testing | `pytest>=7.0.0` |

### 4. Configurar Variables de Entorno

```bash
# Copiar plantilla
cp .env.example .env

# Editar con tus credenciales
code .env
```

---

## ⚙️ Configuración

### Variables de Entorno

Crear archivo `.env` en la raíz del proyecto:

```env
# ═══════════════════════════════════════════════════════════════════════
# WhatsApp Business API (Meta)
# ═══════════════════════════════════════════════════════════════════════
ACCESS_TOKEN=EAAxxxxxxxxxxxxxxxx        # Token de Meta for Developers
PHONE_NUMBER_ID=123456789012345         # ID del número de WhatsApp Business
VERSION=v22.0                           # Versión de la Graph API
VERIFY_TOKEN=tu_token_verificacion      # Token de verificación del webhook

# ═══════════════════════════════════════════════════════════════════════
# Turso Database (Cloud SQLite) — omitir ambas para usar SQLite local
# ═══════════════════════════════════════════════════════════════════════
TURSO_DATABASE_URL=libsql://tu-database.turso.io
TURSO_AUTH_TOKEN=eyJhbGciOiJxxxxxxxxxxxxxxxx

# ═══════════════════════════════════════════════════════════════════════
# Google Gemini (IA)
# ═══════════════════════════════════════════════════════════════════════
GOOGLE_API_KEY=AIzaxxxxxxxxxxxxxxxxxxxxxxxxx

# ═══════════════════════════════════════════════════════════════════════
# Configuración de la Aplicación
# ═══════════════════════════════════════════════════════════════════════
PORT=5000                               # Puerto del servidor Flask
DELAY_SECONDS=1.5                       # Pausa entre envíos masivos (rate limit)
USE_AI_AGENT=True                       # True=LangGraph, False=modo legacy regex
```

> **Nota:** Si `TURSO_DATABASE_URL` y `TURSO_AUTH_TOKEN` no están definidos, el sistema usa SQLite local automáticamente (`data/whatsapp_tracking.db`). Si `USE_AI_AGENT=False`, se activa el modo legacy (regex en `ResponseLogic`).

### Obtener Credenciales

#### WhatsApp Business API
1. Acceder a [Meta for Developers](https://developers.facebook.com/)
2. Crear una aplicación de tipo "Business"
3. Agregar el producto "WhatsApp"
4. Obtener `ACCESS_TOKEN` y `PHONE_NUMBER_ID` desde el panel de WhatsApp

#### Turso Database
1. Crear cuenta en [Turso](https://turso.tech/)
2. Crear una base de datos:
   ```bash
   turso db create whatsapp-tracking
   ```
3. Obtener URL y token:
   ```bash
   turso db show whatsapp-tracking --url
   turso db tokens create whatsapp-tracking
   ```

#### Google Gemini
1. Acceder a [Google AI Studio](https://aistudio.google.com/)
2. Crear una API Key
3. Asignarla a `GOOGLE_API_KEY` en `.env`

---

## 💻 Uso

### Iniciar el Servidor (Desarrollo)

```bash
python run.py
```

El servidor estará disponible en `http://localhost:5000`. Lee `PORT` y `FLASK_ENV` de las variables de entorno (debug activo si `FLASK_ENV=development`).

### Iniciar con Gunicorn (Producción)

```bash
gunicorn --bind 0.0.0.0:$PORT "app:create_app()"
```

### Verificar Estado

```bash
curl http://localhost:5000/health
```

Respuesta exitosa:
```json
{
  "status": "OK",
  "whatsapp_configured": true,
  "database": "turso",
  "version": "v22.0"
}
```

---

## 📚 API REST — Endpoints

### Sistema

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/` | Info de la API (versión, estado, tipo de BD, modo agente) |
| GET | `/health` | Health check (credenciales WhatsApp + BD) |
| GET | `/privacy` | Política de privacidad (HTML, requerido por Meta) |
| DELETE | `/api/database/reset` | **⚠️ PELIGRO** — Borra todas las tablas y las recrea vacías |

### Webhook WhatsApp

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/webhook` | Verificación handshake con Meta (`hub.mode`, `hub.verify_token`, `hub.challenge`) |
| POST | `/webhook` | Recepción de mensajes/eventos WhatsApp → dedup → procesamiento async |

### Mensajes

| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/api/messages/send-simple` | Envía mensaje de texto o plantilla individual |
| POST | `/api/messages/send-template` | Alias de send-simple (compatibilidad legacy) |
| POST | `/api/messages/send-batch` | Envío masivo seguro con soporte multi-tipo (MATRICULA/EVENTO/INFO/CAPTACION), `skip_already_sent`, envío incremental |

**`send-batch` Body — Modo A (Campaña existente):**
```json
{
  "campana_id": 1,
  "estudiante_ids": [1, 2, 3],
  "skip_already_sent": true,
  "plantilla_whatsapp": "confirmacion_evento_quindio"
}
```

**`send-batch` Body — Modo B (Crear campaña nueva):**
```json
{
  "campana_nombre": "Evento Quindío 2026",
  "tipo": "EVENTO",
  "estudiante_ids": [1, 2, 3],
  "plantilla_whatsapp": "confirmacion_evento_quindio",
  "skip_already_sent": true
}
```

### Estudiantes

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/estudiantes/all` | Lista paginada (`limit`, `offset`) con filtro opcional `campana_id` |
| GET | `/api/estudiantes/bootcamp/<bootcamp_id>` | Filtrar por bootcamp |
| GET | `/api/estudiantes/phone/<phone>` | Buscar por teléfono (normalizado) |
| PUT | `/api/estudiantes/update-field` | Actualizar campo específico (`telefono`, `field`, `value`) |
| DELETE | `/api/estudiantes/delete/<phone>` | Eliminar estudiante por teléfono |

### Estadísticas

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/estadisticas` | Stats generales (alias) |
| GET | `/api/contacts/stats` | Stats generales: total, por estado, por bootcamp |
| GET | `/api/contacts/pending` | Lista de estudiantes pendientes de envío |

### Bootcamps

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/bootcamps` | Lista todos los bootcamps |
| DELETE | `/api/bootcamps/delete/<bootcamp_id>` | Eliminar un bootcamp por ID |
| DELETE | `/api/bootcamps/clear-all` | **⚠️ PELIGRO** — Eliminar todos los bootcamps |

### Campañas

| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/api/campaigns` | Crear campaña (`nombre`, `tipo`, `plantilla_whatsapp`, `bootcamp_objetivo_id`) |
| GET | `/api/campaigns` | Listar todas las campañas |
| GET | `/api/campaigns/<id>` | Obtener campaña con estadísticas detalladas |
| GET | `/api/campaigns/templates` | Plantillas por defecto por tipo (MATRICULA/EVENTO/INFO/CAPTACION) + catálogo INFO |
| POST | `/api/campaigns/<id>/members` | Agregar miembros (3 modos: por IDs, por bootcamp, o `all_opt_in` con filtro inteligente) |
| POST | `/api/campaigns/<id>/send` | Enviar campaña a todos los miembros pendientes |
| GET | `/api/campaigns/<id>/stats` | Estadísticas: total, pendientes, enviados, respondidos, tasa de respuesta, desglose |
| DELETE | `/api/campaigns/<id>` | Eliminar campaña + todos sus miembros |

### Google Drive

| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/api/google/upload` | Procesar archivo de Drive → normalizar → guardar en BD (preserva datos existentes, auto-detecta columnas) |
| POST | `/api/sync/drive-manual` | Forzar sincronización manual con Drive |

> Documentación detallada de cada endpoint con ejemplos de request/response en [docs/API_DOCUMENTATION.md](./docs/API_DOCUMENTATION.md)

---

## 🧪 Tests

El proyecto cuenta con **173+ tests** organizados en 7 archivos:

| Archivo | Tests | Cobertura |
|---|---|---|
| `test_agent_optimizations.py` | ~47 | MessageDeduplicator, Router fast-path (todos los intents), quick_response, gemini_logger, decide_next_node, integración del grafo |
| `test_controllers.py` | ~28 | Endpoints HTTP de todos los controladores, batch safety, error handling |
| `test_data_normalizer.py` | ~33 | Normalización de teléfonos E.164, alias de columnas, concatenación de nombres, validación de DataFrames |
| `test_db_handler.py` | ~45 | CRUD completo en las 4 tablas, upsert de estudiantes, estado académico, campañas + miembros, filtros |
| `test_insertions.py` | 5 | Flujo completo de inserción con integridad referencial en las 4 tablas |
| `test_logic.py` | 10 | ResponseLogic webhook processing, variantes Sí/No (modo legacy) |
| `test_turso_integration.py` | 5 | Integración en vivo con Turso (requiere `TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN`) |

### Ejecutar Tests

```bash
# Todos los tests
python -m pytest

# Con detalle
python -m pytest -v --tb=short

# Por archivo
python -m pytest tests/test_db_handler.py

# Por patrón
python -m pytest -k "test_router"

# Solo tests sin integración Turso (no requiere credenciales)
python -m pytest --ignore=tests/test_turso_integration.py
```

### Configuración pytest (`pytest.ini`)

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
```

---

## 📁 Estructura del Proyecto

```
Agent_T_T/
│
├── run.py                          # Punto de entrada (desarrollo): carga .env, inicia Flask
├── requirements.txt                # 14 dependencias principales
├── langgraph.json                  # Config LangGraph → app/agent/graph.py:get_agent
├── pytest.ini                      # Configuración de pytest
├── .env                            # Variables de entorno (NO versionado)
│
├── app/                            # PAQUETE PRINCIPAL
│   ├── __init__.py                 # Factory Flask (create_app) + singletons globales
│   │                               #   → db_handler, whatsapp_service, google_drive_service
│   │                               #   → sync_service, logic_brain
│   │                               #   → 7 Blueprints registrados
│   │                               #   → Error handlers 404/500
│   │
│   ├── agent/                      # AGENTE IA (LangGraph + Gemini 2.5 Flash Lite)
│   │   ├── state.py                # AgentState (TypedDict: messages, phone, student_data, ...)
│   │   ├── graph.py                # StateGraph: 8 nodos, router con fast-path + Gemini fallback
│   │   │                           #   → build_agent_graph() compila el grafo
│   │   │                           #   → get_agent() singleton cacheado
│   │   └── nodes/                  # Nodos especializados del grafo
│   │       ├── load_context.py     # Carga datos estudiante + campaña activa desde BD
│   │       ├── status.py           # Estado de matrícula (determinístico, 0 tokens)
│   │       ├── platform.py         # Credenciales plataforma educativa
│   │       ├── confirm.py          # Confirmación Sí/No → MATRICULADO/RECHAZADO
│   │       ├── confirm_event.py    # Confirmación Asisto/No → ASISTE/NO_ASISTE (solo campana_miembros)
│   │       ├── quick_response.py   # 11+ respuestas pre-definidas (saludos, 7 FAQ, OK, etc.)
│   │       └── fallback.py         # FAQ con Gemini 2.5 Flash Lite (temp=0.3)
│   │
│   ├── controllers/                # CAPA HTTP — 7 Blueprints Flask
│   │   ├── system_controller.py    # /, /health, /privacy, /api/database/reset
│   │   ├── webhook_controller.py   # GET/POST /webhook (WhatsApp Cloud API)
│   │   ├── message_controller.py   # /api/messages/send-simple, send-batch (multi-tipo), send-template
│   │   ├── student_controller.py   # /api/estudiantes/*, /api/contacts/*, /api/estadisticas
│   │   ├── bootcamp_controller.py  # /api/bootcamps/*
│   │   ├── campaign_controller.py  # /api/campaigns/* (CRUD + envío + stats + templates + catálogo INFO)
│   │   └── drive_controller.py     # /api/google/upload, /api/sync/drive-manual
│   │
│   ├── services/                   # CAPA DE NEGOCIO
│   │   ├── whatsapp_service.py     # Cliente Meta Graph API v22.0 (texto + templates, soporte header params)
│   │   ├── db_handler.py           # CRUD Turso (HTTP Pipeline) / SQLite (600+ líneas)
│   │   ├── google_drive_service.py # Download/parse/update Drive (v3) + Sheets (v4)
│   │   └── sync_service.py         # APScheduler BackgroundScheduler (5 min)
│   │
│   ├── core/
│   │   └── logic.py                # ResponseLogic — modo legacy sin IA (Sí/No por regex)
│   │
│   └── utils/                      # UTILIDADES
│       ├── data_normalizer.py      # Normalización teléfonos E.164, alias columnas, concat nombres
│       ├── gemini_logger.py        # Log de tokens (input/output/total) por llamada Gemini
│       └── message_dedup.py        # MessageDeduplicator: LRU thread-safe (TTL 5min, max 5000)
│
├── data/                           # BD SQLite local (desarrollo, auto-creada)
├── templates/
│   └── privacy.html                # Política de privacidad (requerido por Meta)
├── docs/                           # Documentación técnica detallada
│   ├── API_DOCUMENTATION.md        # Referencia completa de endpoints con ejemplos
│   ├── BACKEND_DOCUMENTATION.md    # Arquitectura técnica
│   ├── DATABASE_SCHEMA.md          # DDL, campos, índices, relaciones
│   └── SERVICES_ARCHITECTURE.md    # Diagramas de servicios y flujos
│
└── tests/                          # 173+ tests
    ├── test_agent_optimizations.py  # ~47 tests — Agente IA completo
    ├── test_controllers.py          # ~28 tests — Endpoints HTTP
    ├── test_data_normalizer.py      # ~33 tests — Normalización de datos
    ├── test_db_handler.py           # ~45 tests — CRUD base de datos
    ├── test_insertions.py           #   5 tests — Inserciones con integridad
    ├── test_logic.py                #  10 tests — Modo legacy
    └── test_turso_integration.py    #   5 tests — Integración Turso cloud
```

---

## 🌐 Despliegue

### Render (Producción actual)

| Configuración | Valor |
|---|---|
| Build command | `pip install -r requirements.txt` |
| Start command | `gunicorn "app:create_app()"` |
| Auto-deploy | Push a `main` |
| URL | [agent-t-t.onrender.com](https://agent-t-t.onrender.com) |

**Variables de entorno en Render:**

| Variable | Requerida | Descripción |
|---|---|---|
| `ACCESS_TOKEN` | Sí | Token WhatsApp Business API |
| `PHONE_NUMBER_ID` | Sí | ID del número de teléfono |
| `VERSION` | No | Versión API (default: `v22.0`) |
| `VERIFY_TOKEN` | Sí | Token de verificación webhook |
| `TURSO_DATABASE_URL` | Sí | URL de la base de datos Turso |
| `TURSO_AUTH_TOKEN` | Sí | Token de autenticación Turso |
| `GOOGLE_API_KEY` | Sí | API Key de Google Gemini |
| `USE_AI_AGENT` | No | `True` (default) o `False` |
| `DELAY_SECONDS` | No | Pausa entre envíos (default: `1.5`) |

### Docker (Alternativo)

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:create_app()"]
```

```bash
docker build -t agent-tt .
docker run -p 5000:5000 --env-file .env agent-tt
```

---

## 🔒 Seguridad

| Medida | Implementación |
|---|---|
| Credenciales | Exclusivamente en variables de entorno (`.env` en `.gitignore`) |
| CORS | Flask-CORS habilitado, configurable para dominios específicos |
| Webhook | Verificado con `VERIFY_TOKEN` secreto contra Meta |
| Comunicaciones | HTTPS a todas las APIs externas (Meta, Turso, Google) |
| Base de datos | Turso con autenticación Bearer token por request |
| Deduplicación | Cache atómica thread-safe para evitar procesamiento repetido |
| Filtro temporal | Mensajes de más de 5 minutos se descartan automáticamente |
| Batch safety | `send-batch` requiere `estudiante_ids` explícitos (nunca auto-enrolla todos) |
| Protección de datos | UPSERT preserva datos existentes en re-upload de estudiantes |
| Queries parametrizadas | Todas las consultas usan placeholders `?` (prevención SQL injection) |

---

## 📊 Monitoreo

### Tags de Logs Estructurados

| Tag | Descripción |
|---|---|
| `[ROUTER]` | Clasificación de intención del agente (fast-path o Gemini) |
| `[QUICK]` | Respuestas determinísticas servidas (0 tokens IA) |
| `[EVENT]` | Confirmación de asistencia a eventos |
| `[CONFIRM]` | Confirmación de matrícula (Sí/No) |
| `[WH]` | Eventos del webhook (dedup, filtros, tipo de mensaje) |
| `[BG]` | Procesamiento en background daemon thread |
| `[DB]` | Operaciones de base de datos (Turso/SQLite) |
| `[SEND]` | Envío de mensajes WhatsApp (texto/template) |
| `[DRIVE]` | Operaciones con Google Drive (upload/sync) |
| `[SYNC]` | Sincronización automática (APScheduler) |
| `[GEMINI]` | Uso de tokens por llamada a Gemini (input/output/total) |
| `[BATCH]` | Flujo send-batch: pasos, filtrado, envío, estadísticas |
| `[CAMPAIGN]` | Operaciones CRUD de campañas |

### Ejemplo de Logs

```
[DB] Usando Turso (cloud): libsql://whatsapp-tracking-xxx.turso.io
[WH] Mensaje recibido de 573001234567: 'hola' (text)
[ROUTER] Fast-Path: SALUDO (sin IA)
[QUICK] Respuesta determinística para intent=SALUDO (0 tokens IA)
[BG] ✅ Respuesta enviada a 573001234567

[WH] Mensaje recibido de 573009876543: 'sí, acepto' (button_reply)
[ROUTER] Prioridad 0: Campaña MATRICULA activa → CONFIRM
[CONFIRM] Estudiante confirmó matrícula → estado_academico=MATRICULADO
[BG] ✅ Respuesta enviada a 573009876543

[BATCH] Campaña nueva: #5 'Evento Quindío 2026' tipo=EVENTO, estudiantes=120
[BATCH] skip_already_sent: 120 originales → 95 elegibles, 25 omitidos
[BATCH] [1/95] → 573001111111
[CAMPAIGN] Enviando campaña 5 (confirmacion_evento_quindio) a 95 miembros
```

---

## 📝 Historial de Cambios

### v2.0.0 → v2.1.0 — Sistema de Campañas Multi-Tipo (Marzo–Abril 2026)

**Campañas de Evento y Captación:**
- Nuevo tipo de campaña `EVENTO` con flujo Asisto/No Asisto independiente del estado académico
- Nuevo tipo de campaña `CAPTACION` con template `mensaje_interesados` para leads
- Nodo `confirm_event` en el grafo LangGraph para manejar respuestas de eventos
- Resolución dinámica de `language_code` por tipo (`es_CO` para EVENTO, `es` para el resto)

**Catálogo de Plantillas INFO:**
- Diccionario `INFO_TEMPLATES` extensible con definición de parámetros por plantilla
- Soporte para `recordatorio_presencial`, `recordatorio_virtual`, `mensaje_interesados`
- Builder inteligente `_build_template_params()` que resuelve parámetros según tipo y plantilla

**Envío Masivo Mejorado (send-batch):**
- Flujo de 8 pasos atómicos con logs detallados
- Modo A (campaña existente) con envío incremental: permite agregar estudiantes sin crear nueva campaña
- `skip_already_sent` filtra estudiantes que ya recibieron campaña del mismo tipo
- Override de plantilla vía `plantilla_whatsapp` en el payload

**Mejoras en WhatsApp Service:**
- Soporte `has_header_param` para plantillas con parámetros en header
- Logs de debug detallados para payload/response (diagnóstico de errores Meta)
- Resolución de `language_code` desde `TEMPLATE_DEFAULTS` (prioridad sobre frontend)

**Investigación y Gestión de WhatsApp Business API:**
- Investigación sobre políticas de mensajería de Meta tras bloqueo por "tráfico inusual"
- Redacción de correo para verificación de negocio (Business Verification) ante Meta
- Estrategia de uso de múltiples cuentas de Meta Business como contingencia
- Implementación de pausas estratégicas (`DELAY_SECONDS`) para rate limiting

**DB Handler:**
- Nuevo método `get_estudiantes_by_bootcamp_and_estado()` para filtro combinado
- Endpoint `/api/campaigns/templates` retorna catálogo completo con plantillas INFO

### v1.0.0 → v2.0.0 — Arquitectura MVC + Agente IA (Febrero 2026)

- Refactorización completa a MVC con 7 Blueprints
- Integración LangGraph + Gemini 2.5 Flash Lite
- Sistema de campañas con 4 tablas normalizadas
- 173+ tests automatizados
- Deploy en Render + Turso

---

## 🤝 Contribución

1. Fork el repositorio
2. Crear rama de feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -m 'feat: agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

### Convención de Commits

| Prefijo | Uso |
|---|---|
| `feat:` | Nueva funcionalidad |
| `fix:` | Corrección de bug |
| `docs:` | Documentación |
| `refactor:` | Refactorización |
| `test:` | Nuevos tests o correcciones |
| `chore:` | Mantenimiento, dependencias |

---

## 📄 Licencia

Este proyecto fue desarrollado para el programa **Talento Tech** del Ministerio de las TIC de Colombia.

---

## 📞 Contacto

| | |
|---|---|
| **Proyecto** | Talento Tech — MinTIC Colombia |
| **Repositorio** | [github.com/JuanGonzalezx/Agent_T_T](https://github.com/JuanGonzalezx/Agent_T_T) |
| **API Producción** | [agent-t-t.onrender.com](https://agent-t-t.onrender.com) |
| **Frontend** | [panel-agent-tt.vercel.app](https://panel-agent-tt.vercel.app) |

---

*Documentación actualizada — Abril 2026*
