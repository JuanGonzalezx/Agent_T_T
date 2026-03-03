# Agent_T_T — Agente Virtual WhatsApp para Talento Tech

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Flask-3.0-green?logo=flask" alt="Flask">
  <img src="https://img.shields.io/badge/LangGraph-0.2-orange?logo=langchain" alt="LangGraph">
  <img src="https://img.shields.io/badge/Gemini-2.5_Flash-4285F4?logo=google" alt="Gemini">
  <img src="https://img.shields.io/badge/Database-Turso-purple" alt="Turso">
  <img src="https://img.shields.io/badge/WhatsApp-Business%20API-25D366?logo=whatsapp" alt="WhatsApp">
  <img src="https://img.shields.io/badge/Tests-172-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/Deploy-Render-46E3B7" alt="Render">
</p>

Backend Flask con agente conversacional de IA (LangGraph + Gemini) que funciona como asistente virtual de WhatsApp para el programa **Talento Tech** del MinTIC (Colombia). Gestiona matrículas, eventos, envíos masivos y consultas automáticas de estudiantes.

---

## 📋 Tabla de Contenidos

- [Características](#-características)
- [Stack Tecnológico](#-stack-tecnológico)
- [Arquitectura](#-arquitectura)
- [Agente IA — Grafo LangGraph](#-agente-ia--grafo-langgraph)
- [Base de Datos](#-base-de-datos)
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
- [Contribución](#-contribución)
- [Contacto](#-contacto)

---

## ✨ Características

| Funcionalidad | Descripción |
|---|---|
| **Agente IA conversacional** | Grafo LangGraph con router inteligente (fast-path por keywords + fallback Gemini) |
| **Respuestas determinísticas (0 tokens)** | Saludos, FAQs, despedidas y agradecimientos con costo cero de IA |
| **Campañas multi-tipo** | Creación y envío de campañas MATRICULA, EVENTO e INFO con tracking individual |
| **Confirmación de matrícula** | Flujo Sí/No con actualización de estado académico en BD |
| **Confirmación de eventos** | Flujo Asisto/No Asisto independiente del estado académico |
| **Consulta de estado** | Respuesta determinística del estado de inscripción del estudiante |
| **Envío masivo** | Procesamiento batch de plantillas de WhatsApp a todos los pendientes |
| **Integración Google Drive** | Importación de contactos desde Sheets/CSV/XLSX con normalización automática |
| **Sincronización bidireccional** | Scheduler APScheduler cada 5 min para sync con Drive |
| **Deduplicación en RAM** | Cache LRU atómico para evitar procesamiento de mensajes duplicados |
| **Modo dual** | Agente IA (LangGraph) o modo legacy (regex) configurable por variable de entorno |
| **172 tests** | Suite completa cubriendo agente, controladores, BD, normalización e integración Turso |

---

## 🛠 Stack Tecnológico

| Capa | Tecnología |
|---|---|
| Framework Web | Flask 3.0 + Flask-CORS + Gunicorn |
| Agente IA | LangGraph 0.2 + LangChain Core 0.3 |
| Modelo LLM | Gemini 2.5 Flash Lite (router) + Gemini 2.5 Flash Lite (FAQ) |
| Base de Datos | Turso/libSQL (producción) · SQLite (desarrollo) |
| Mensajería | WhatsApp Business Cloud API v22.0 (Meta) |
| Almacenamiento | Google Drive API (Sheets/CSV/XLSX) |
| Scheduler | APScheduler 3.10 |
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
│  │  4. Deduplicación atómica en RAM (LRU)                            │    │
│  │  5. Soporte text, button_reply, list_reply, button legacy          │    │
│  │  6. Responder 200 inmediato → procesar en background thread        │    │
│  └────────────────────────────┬────────────────────────────────────────┘    │
│                               │                                             │
│               ┌───────────────┴───────────────┐                             │
│               │  USE_AI_AGENT = True?          │                            │
│               ├──── Sí ───────┤──── No ────────┤                            │
│               ▼               ▼                                             │
│  ┌────────────────┐  ┌─────────────────┐                                   │
│  │  AGENTE IA     │  │  ResponseLogic  │                                   │
│  │  (LangGraph)   │  │  (Regex legacy) │                                   │
│  └───────┬────────┘  └─────────────────┘                                   │
│          ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      SERVICIOS                                      │    │
│  │  WhatsAppService ◄──► Meta Graph API (v22.0)                        │    │
│  │  DatabaseHandler ◄──► Turso (prod) / SQLite (dev)                   │    │
│  │  GoogleDriveService ◄──► Google Drive API                           │    │
│  │  SyncService ◄──► APScheduler (cada 5 min)                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Flujo de Datos

1. **Importación** → Google Drive → API → normalización → Turso
2. **Envío masivo** → Turso → API → WhatsApp Business API → Usuario
3. **Respuesta** → Usuario → WhatsApp → Webhook → Dedup → Agente IA → Turso
4. **Visualización** → Turso → API REST → Frontend (Vercel)
5. **Sincronización** → Turso → API → Google Drive (cada 5 minutos)

---

## 🤖 Agente IA — Grafo LangGraph

El agente procesa cada mensaje entrante a través de un grafo dirigido con nodos especializados:

```
load_context ──► router ──►┬── confirm_event    ─► END   (Asisto/No Asisto)
     │                     ├── confirm_response  ─► END   (Sí/No matrícula)
 (Busca datos              ├── check_status      ─► END   (Estado inscripción)
  en Turso +               ├── platform_access   ─► END   (Credenciales)
  campaña activa)          ├── quick_response    ─► END   (0 tokens IA)
                           └── general_response  ─► END   (Gemini FAQ)
```

### Router — Sistema de Prioridades

| Prioridad | Condición | Intent | Costo IA |
|---|---|---|---|
| 0 | Campaña EVENTO activa sin respuesta | `CONFIRM_EVENT` | 0 tokens |
| 0 | Campaña MATRICULA activa sin respuesta | `CONFIRM` | 0 tokens |
| 1 | Keywords de estado/matrícula | `STATUS` | 0 tokens |
| 1 | Keywords de acceso/plataforma | `ACCESS` | 0 tokens |
| 1 | Saludos, gracias, OK, despedidas | `SALUDO` `GRACIAS` `OK` `DESPEDIDA` | 0 tokens |
| 1 | FAQs comunes (inscripción, bootcamps, horarios, costos, certificación, contacto) | `INFO_*` | 0 tokens |
| 2 | Consulta no clasificada por fast-path | `STATUS` `ACCESS` `GENERAL` | ~10 tokens (Gemini router) |

### Nodos del Grafo

| Nodo | Archivo | Función |
|---|---|---|
| `load_context` | `nodes/load_context.py` | Busca estudiante en BD por teléfono + carga campaña activa |
| `router` | `graph.py` | Clasifica intención (fast-path keywords → Gemini fallback) |
| `confirm_event` | `nodes/confirm_event.py` | Procesa Asisto/No Asisto → actualiza `campana_miembros` |
| `confirm_response` | `nodes/confirm.py` | Procesa Sí/No → actualiza estado académico + `campana_miembros` |
| `check_status` | `nodes/status.py` | Respuesta determinística con estado de matrícula |
| `platform_access` | `nodes/platform.py` | Info de acceso a plataforma educativa |
| `quick_response` | `nodes/quick_response.py` | 11 respuestas pre-definidas (0 tokens Gemini) |
| `general_response` | `nodes/fallback.py` | FAQ con Gemini (base de conocimiento compacta) |

---

## 🗄 Base de Datos

Esquema normalizado v3 con 4 tablas. Soporte dual: **Turso** (producción vía HTTP) y **SQLite** (desarrollo local con WAL mode).

### Tablas

#### `bootcamps`
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `codigo` | TEXT UNIQUE | Código único (ej: `IA_2024_01`) |
| `nombre` | TEXT | Nombre del bootcamp |
| `modalidad` | TEXT | Presencial / Virtual / Híbrido |
| `horario` | TEXT | Horario de clases |
| `lugar` | TEXT | Sede/ubicación |
| `fecha_inicio_ingles` | TEXT | Inicio módulo inglés |
| `fecha_inicio_tecnica` | TEXT | Inicio formación técnica |

#### `estudiantes`
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `telefono_e164` | TEXT UNIQUE | Formato `+573001234567` |
| `nombre` | TEXT | Nombre completo |
| `documento` | TEXT | Cédula/ID |
| `email` | TEXT | Correo electrónico |
| `bootcamp_id` | INTEGER FK | Referencia a `bootcamps(id)` |
| `opt_in` | INTEGER | 0=No, 1=Sí (consentimiento) |
| `estado_academico` | TEXT | `INSCRITO` / `MATRICULADO` / `RECHAZADO` / `GRADUADO` |

#### `campanas`
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `nombre` | TEXT | Nombre de la campaña |
| `tipo` | TEXT | `MATRICULA` / `EVENTO` / `INFO` |
| `bootcamp_objetivo_id` | TEXT | Filtro opcional por bootcamp |
| `plantilla_whatsapp` | TEXT | Nombre del template en Meta |
| `estado` | TEXT | `DRAFT` / `SENDING` / `COMPLETED` |

#### `campana_miembros`
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `campana_id` | INTEGER FK | Referencia a `campanas(id)` |
| `estudiante_id` | INTEGER FK | Referencia a `estudiantes(id)` |
| `variables_contexto` | TEXT | JSON con parámetros de template |
| `estado_envio` | TEXT | `pending` / `sent` / `error` |
| `message_id` | TEXT | `wamid.xxx` (ID WhatsApp) |
| `respuesta_usuario` | TEXT | `ASISTE` / `NO_ASISTE` / `NULL` |
| `mensaje_respuesta_raw` | TEXT | Texto literal del usuario |

---

## 📦 Requisitos Previos

- **Python** 3.10 o superior
- **Cuenta Meta Business** con WhatsApp Business API configurada
- **Cuenta Turso** (base de datos cloud) o SQLite local para desarrollo
- **Cuenta Google Cloud** (para integración con Drive)
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

El proyecto utiliza 15 dependencias principales:

| Grupo | Paquetes |
|---|---|
| Framework Web | Flask, flask-cors, gunicorn, Werkzeug |
| Base de Datos | libsql-experimental |
| APIs Externas | requests, python-dotenv |
| Procesamiento | pandas, openpyxl |
| Scheduler | APScheduler |
| Agente IA | langgraph, langgraph-cli, langchain-google-genai, langchain-core |

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
ACCESS_TOKEN=EAAxxxxxxxxxxxxxxxx
PHONE_NUMBER_ID=123456789012345
VERSION=v22.0
VERIFY_TOKEN=tu_token_verificacion_secreto

# ═══════════════════════════════════════════════════════════════════════
# Turso Database (Cloud SQLite) — omitir para usar SQLite local
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
PORT=5000
FLASK_ENV=development
DELAY_SECONDS=1.5
USE_AI_AGENT=True
```

> **Nota:** Si `TURSO_DATABASE_URL` y `TURSO_AUTH_TOKEN` no están definidos, el sistema usa SQLite local automáticamente (`data/whatsapp_tracking.db`). Si `USE_AI_AGENT=False`, se activa el modo legacy (regex).

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

El servidor estará disponible en `http://localhost:5000`

### Iniciar con Gunicorn (Producción)

```bash
gunicorn --bind 0.0.0.0:$PORT "app:create_app()"
```

### Verificar Estado

```bash
curl http://localhost:5000/health
```

---

## 📚 API REST — Endpoints

### Sistema

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/` | Info general de la API |
| GET | `/health` | Health check (credenciales + BD) |
| GET | `/privacy` | Política de privacidad (HTML) |
| DELETE | `/api/database/reset` | **PELIGRO** — Borra toda la BD |

### Webhook WhatsApp

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/webhook` | Verificación handshake con Meta |
| POST | `/webhook` | Recepción de mensajes/eventos WhatsApp |

### Mensajes

| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/api/messages/send-simple` | Envía texto o plantilla individual |
| POST | `/api/messages/send-template` | Alias de send-simple (legacy) |
| POST | `/api/messages/send-batch` | Envío masivo a todos los pendientes |

### Estudiantes

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/estudiantes/all` | Lista paginada (`limit`, `offset`) |
| GET | `/api/estudiantes/bootcamp/:id` | Filtrar por bootcamp |
| GET | `/api/estudiantes/phone/:phone` | Buscar por teléfono |
| PUT | `/api/estudiantes/update-field` | Actualizar campo específico |
| DELETE | `/api/estudiantes/delete/:phone` | Eliminar estudiante |

### Estadísticas

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/estadisticas` | Stats generales (alias) |
| GET | `/api/contacts/stats` | Stats generales |
| GET | `/api/contacts/pending` | Lista de pendientes de envío |

### Bootcamps

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/bootcamps` | Lista todos los bootcamps |
| DELETE | `/api/bootcamps/delete/:id` | Eliminar un bootcamp |
| DELETE | `/api/bootcamps/clear-all` | **PELIGRO** — Eliminar todos |

### Campañas

| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/api/campaigns` | Crear campaña (nombre, tipo, plantilla) |
| GET | `/api/campaigns` | Listar todas las campañas |
| GET | `/api/campaigns/:id` | Obtener campaña con estadísticas |
| GET | `/api/campaigns/templates` | Plantillas por defecto por tipo |
| POST | `/api/campaigns/:id/members` | Agregar miembros (por IDs, bootcamp o all_opt_in) |
| POST | `/api/campaigns/:id/send` | Enviar campaña a pendientes |
| GET | `/api/campaigns/:id/stats` | Estadísticas detalladas |
| DELETE | `/api/campaigns/:id` | Eliminar campaña + miembros |

### Google Drive

| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/api/google/upload` | Procesar archivo de Drive → BD |
| POST | `/api/sync/drive-manual` | Forzar sincronización manual |

> Documentación detallada de cada endpoint en [docs/API_DOCUMENTATION.md](./docs/API_DOCUMENTATION.md)

---

## 🧪 Tests

El proyecto cuenta con **172 tests** organizados en 7 archivos:

| Archivo | Cobertura |
|---|---|
| `test_agent_optimizations.py` | Agente IA: dedup, router, quick_response, fast-path |
| `test_controllers.py` | Endpoints HTTP de todos los controladores |
| `test_data_normalizer.py` | Normalización de teléfonos y DataFrames |
| `test_db_handler.py` | CRUD completo en todas las tablas |
| `test_insertions.py` | Inserciones y upserts de estudiantes/bootcamps |
| `test_logic.py` | Lógica de respuestas (modo legacy) |
| `test_turso_integration.py` | Integración con Turso (cloud) |

### Ejecutar Tests

```bash
# Todos los tests
python -m pytest

# Con detalle
python -m pytest -v --tb=short

# Por archivo
python -m pytest tests/test_db_handler.py

# Por nombre
python -m pytest -k "test_router"
```

---

## 📁 Estructura del Proyecto

```
Agent_T_T/
│
├── run.py                          # Punto de entrada (desarrollo local)
├── requirements.txt                # 15 dependencias
├── langgraph.json                  # Config LangGraph → app/agent/graph.py:get_agent
├── pytest.ini                      # Configuración de pytest
├── .env                            # Variables de entorno (no versionado)
│
├── app/                            # PAQUETE PRINCIPAL
│   ├── __init__.py                 # Factory Flask (create_app) + singletons
│   │
│   ├── agent/                      # AGENTE IA (LangGraph + Gemini)
│   │   ├── state.py                # AgentState (TypedDict)
│   │   ├── graph.py                # Grafo: router + nodos + edges condicionales
│   │   └── nodes/                  # Nodos especializados
│   │       ├── load_context.py     # Carga datos estudiante + campaña activa
│   │       ├── status.py           # Estado de matrícula (determinístico)
│   │       ├── platform.py         # Acceso a plataforma educativa
│   │       ├── confirm.py          # Confirmación Sí/No (matrícula)
│   │       ├── confirm_event.py    # Confirmación Asisto/No Asisto (eventos)
│   │       ├── quick_response.py   # 11 respuestas pre-definidas (0 tokens)
│   │       └── fallback.py         # FAQ con Gemini
│   │
│   ├── controllers/                # CAPA HTTP — Blueprints Flask
│   │   ├── system_controller.py    # /, /health, /privacy, /database/reset
│   │   ├── webhook_controller.py   # GET/POST /webhook (WhatsApp Cloud API)
│   │   ├── message_controller.py   # send-simple, send-batch
│   │   ├── student_controller.py   # CRUD estudiantes + estadísticas
│   │   ├── bootcamp_controller.py  # CRUD bootcamps
│   │   ├── campaign_controller.py  # CRUD + envío de campañas
│   │   └── drive_controller.py     # Upload Drive + sync manual
│   │
│   ├── services/                   # CAPA DE NEGOCIO
│   │   ├── whatsapp_service.py     # Cliente Meta Graph API v22.0
│   │   ├── db_handler.py           # CRUD Turso/SQLite (~1250 líneas)
│   │   ├── google_drive_service.py # Descarga/parse/actualización Drive
│   │   └── sync_service.py         # APScheduler cada 5 min
│   │
│   ├── core/
│   │   └── logic.py                # ResponseLogic (modo legacy sin IA)
│   │
│   └── utils/                      # UTILIDADES
│       ├── data_normalizer.py      # Normalización de teléfonos E.164
│       ├── gemini_logger.py        # Log de tokens por llamada Gemini
│       └── message_dedup.py        # Cache LRU deduplicación en RAM
│
├── data/                           # BD SQLite local (desarrollo)
├── templates/
│   └── privacy.html                # Política de privacidad (Meta)
├── docs/                           # Documentación técnica
│   ├── API_DOCUMENTATION.md        # Referencia completa de endpoints
│   ├── BACKEND_DOCUMENTATION.md    # Arquitectura técnica
│   ├── DATABASE_SCHEMA.md          # DDL, campos, índices
│   └── SERVICES_ARCHITECTURE.md    # Diagramas de servicios
│
└── tests/                          # 172 tests
    ├── test_agent_optimizations.py
    ├── test_controllers.py
    ├── test_data_normalizer.py
    ├── test_db_handler.py
    ├── test_insertions.py
    ├── test_logic.py
    └── test_turso_integration.py
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

Variables de entorno a configurar en el dashboard de Render: `ACCESS_TOKEN`, `PHONE_NUMBER_ID`, `VERSION`, `VERIFY_TOKEN`, `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, `GOOGLE_API_KEY`, `USE_AI_AGENT`.

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

---

## 🔒 Seguridad

- Credenciales sensibles exclusivamente en variables de entorno (`.env` no versionado)
- CORS configurado para dominios específicos en producción
- Webhook verificado con `VERIFY_TOKEN` secreto contra Meta
- Conexiones HTTPS a todas las APIs externas (Meta, Turso, Google)
- Base de datos Turso con autenticación por Bearer token
- Deduplicación atómica para evitar procesamiento repetido de mensajes
- Filtro de antigüedad: mensajes de más de 5 minutos se descartan

---

## 📊 Monitoreo

### Logs Estructurados

| Tag | Descripción |
|---|---|
| `[ROUTER]` | Clasificación de intención del agente |
| `[QUICK]` | Respuestas determinísticas (0 tokens) |
| `[EVENT]` | Confirmación de asistencia a eventos |
| `[WH]` | Eventos del webhook (dedup, filtros) |
| `[BG]` | Procesamiento en background thread |
| `[DB]` | Operaciones de base de datos |
| `[SEND]` | Envío de mensajes WhatsApp |
| `[DRIVE]` | Operaciones con Google Drive |
| `[SYNC]` | Sincronización automática |
| `[GEMINI]` | Uso de tokens por llamada a Gemini |

### Ejemplo de Logs

```
[ROUTER] Procesando mensaje: 'hola'
[ROUTER] Fast-Path: SALUDO (sin IA)
[QUICK] Respuesta determinística para intent=SALUDO (0 tokens IA)
[BG] ✅ Respuesta enviada a 573001234567
```

---

## 🤝 Contribución

1. Fork el repositorio
2. Crear rama de feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -m 'feat: agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

### Convención de Commits

- `feat:` Nueva funcionalidad
- `fix:` Corrección de bug
- `docs:` Documentación
- `refactor:` Refactorización
- `test:` Tests
- `chore:` Mantenimiento

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
