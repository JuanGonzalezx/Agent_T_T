# WhatsApp Messaging API - Talento Tech

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Flask-3.0-green?logo=flask" alt="Flask">
  <img src="https://img.shields.io/badge/Database-Turso-purple" alt="Turso">
  <img src="https://img.shields.io/badge/WhatsApp-Business%20API-25D366?logo=whatsapp" alt="WhatsApp">
  <img src="https://img.shields.io/badge/Deploy-Render-46E3B7" alt="Render">
</p>

Sistema backend para gestión y envío masivo de mensajes WhatsApp mediante la API de WhatsApp Business (Meta), diseñado para el programa **Talento Tech** del Ministerio de las TIC de Colombia.

---

## 📋 Tabla de Contenidos

- [Características](#-características)
- [Arquitectura](#-arquitectura)
- [Requisitos Previos](#-requisitos-previos)
- [Instalación](#-instalación)
- [Configuración](#-configuración)
- [Uso](#-uso)
- [API Reference](#-api-reference)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Despliegue](#-despliegue)
- [Contribución](#-contribución)

---

## ✨ Características

- **Envío Masivo de Mensajes**: Procesamiento batch de mensajes usando plantillas de WhatsApp
- **Webhook en Tiempo Real**: Recepción y procesamiento de respuestas de usuarios
- **Integración Google Drive**: Importación de contactos desde Sheets/CSV/XLSX
- **Base de Datos Cloud**: Turso (libSQL) como fuente única de verdad
- **Panel de Control**: Frontend en Vercel para gestión visual
- **Sincronización Automática**: Actualización periódica a Google Drive
- **API RESTful**: Endpoints documentados para integración con otros sistemas

---

## 🏗 Arquitectura

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           ARQUITECTURA DEL SISTEMA                       │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Google    │────▶│   Flask API     │◀───▶│     Turso       │
│   Drive     │◀────│   (Render)      │     │   (Cloud DB)    │
└─────────────┘     └────────┬────────┘     └─────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
     ┌─────────────┐  ┌───────────┐  ┌─────────────┐
     │  WhatsApp   │  │  Frontend │  │   Webhook   │
     │  Business   │  │  (Vercel) │  │   (Meta)    │
     │    API      │  │           │  │             │
     └─────────────┘  └───────────┘  └─────────────┘
```

### Flujo de Datos

1. **Importación**: Google Drive → API → Turso
2. **Envío**: Turso → API → WhatsApp Business API → Usuario
3. **Respuesta**: Usuario → WhatsApp → Webhook → API → Turso
4. **Visualización**: Turso → API → Frontend (Vercel)
5. **Sincronización**: Turso → API → Google Drive (cada 5 minutos)

---

## 📦 Requisitos Previos

- **Python** 3.10 o superior
- **Cuenta Meta Business** con WhatsApp Business API configurada
- **Cuenta Turso** (base de datos cloud)
- **Cuenta Google Cloud** (para integración con Drive)
- **Cuenta Render** (para despliegue - opcional)

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
python -m venv .venv
.venv\Scripts\activate

# Linux/Mac
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar Variables de Entorno

```bash
# Copiar plantilla
cp .env.example .env

# Editar con tus credenciales
code .env  # o tu editor preferido
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
WEBHOOK_VERIFY_TOKEN=tu_token_verificacion_secreto

# ═══════════════════════════════════════════════════════════════════════
# Turso Database (Cloud SQLite)
# ═══════════════════════════════════════════════════════════════════════
TURSO_DATABASE_URL=libsql://tu-database.turso.io
TURSO_AUTH_TOKEN=eyJhbGciOiJxxxxxxxxxxxxxxxx

# ═══════════════════════════════════════════════════════════════════════
# Configuración de la Aplicación
# ═══════════════════════════════════════════════════════════════════════
PORT=5000
FLASK_ENV=development
DELAY_SECONDS=1.5
DATA_DIR=.
```

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

---

## 💻 Uso

### Iniciar el Servidor (Desarrollo)

```bash
python app.py
```

El servidor estará disponible en `http://localhost:5000`

### Iniciar con Gunicorn (Producción)

```bash
gunicorn --bind 0.0.0.0:$PORT app:app
```

### Verificar Estado

```bash
curl http://localhost:5000/health
```

---

## 📚 API Reference

### Índice de Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/` | Información de la API |
| GET | `/health` | Estado del servidor |
| GET | `/privacy` | Política de privacidad |
| POST | `/api/messages/send-simple` | Enviar mensaje simple |
| POST | `/api/messages/send-template` | Enviar mensaje con plantilla |
| POST | `/api/messages/send-batch` | Envío masivo |
| GET | `/api/contacts/stats` | Estadísticas de contactos |
| GET | `/api/contacts/pending` | Contactos pendientes |
| POST | `/api/google/upload` | Importar desde Google Drive |
| GET/POST | `/webhook` | Webhook de WhatsApp |
| GET | `/api/estudiantes/all` | Listar estudiantes |
| GET | `/api/estudiantes/bootcamp/:id` | Estudiantes por bootcamp |
| GET | `/api/estudiantes/phone/:phone` | Buscar por teléfono |
| GET | `/api/bootcamps` | Listar bootcamps |
| GET | `/api/estadisticas` | Estadísticas generales |
| PUT | `/api/estudiantes/update-field` | Actualizar campo |
| DELETE | `/api/estudiantes/delete/:phone` | Eliminar estudiante |

### Documentación Detallada

Ver [API_DOCUMENTATION.md](./docs/API_DOCUMENTATION.md) para documentación completa de cada endpoint.

---

## 📁 Estructura del Proyecto

```
Agent_T_T/
├── app.py                      # Aplicación principal Flask
├── requirements.txt            # Dependencias Python
├── .env                        # Variables de entorno (no versionado)
├── .gitignore                 # Archivos ignorados por Git
│
├── services/                   # Capa de servicios
│   ├── __init__.py
│   ├── whatsapp_service.py    # Cliente WhatsApp Business API
│   ├── google_drive_service.py # Integración Google Drive
│   └── db_handler.py          # Gestor de base de datos Turso/SQLite
│
├── utils/                      # Utilidades
│   ├── __init__.py
│   ├── csv_handler.py         # (Legacy) Manejo de CSV
│   └── data_normalizer.py     # Normalización de datos
│
├── templates/                  # Plantillas HTML
│   └── privacy.html           # Política de privacidad
│
└── docs/                       # Documentación
    ├── API_DOCUMENTATION.md
    └── DEPLOYMENT.md
```

---

## 🌐 Despliegue

### Render (Recomendado)

1. Conectar repositorio de GitHub
2. Configurar variables de entorno en el dashboard
3. Configurar build command: `pip install -r requirements.txt`
4. Configurar start command: `gunicorn app:app`
5. Deploy automático en cada push a `main`

### Docker (Alternativo)

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
```

---

## 🔒 Seguridad

- Las credenciales sensibles se manejan mediante variables de entorno
- CORS configurado para dominios específicos en producción
- Webhook verificado con token secreto
- Conexiones a APIs externas mediante HTTPS
- Base de datos con autenticación por token

---

## 📊 Monitoreo

### Logs Estructurados

El sistema utiliza tags para facilitar el filtrado de logs:

| Tag | Descripción |
|-----|-------------|
| `[SEND]` | Operaciones de envío de mensajes |
| `[WEBHOOK]` | Eventos del webhook |
| `[DB]` | Operaciones de base de datos |
| `[DRIVE]` | Operaciones con Google Drive |
| `[SYNC]` | Sincronización automática |

### Ejemplo de Logs

```
[SEND] Batch iniciado - 150 pendientes
[SEND] +573001234567 - OK (wamid.xxx)
[WEBHOOK] Respuesta recibida - 573001234567: "Si"
[DB] Respuesta guardada - 573001234567
[SYNC] Drive actualizado - OK
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

- **Proyecto**: Talento Tech - MinTIC Colombia
- **Repositorio**: [github.com/JuanGonzalezx/Agent_T_T](https://github.com/JuanGonzalezx/Agent_T_T)
- **API en Producción**: [agent-t-t.onrender.com](https://agent-t-t.onrender.com)
- **Frontend**: [panel-agent-tt.vercel.app](https://panel-agent-tt.vercel.app)
