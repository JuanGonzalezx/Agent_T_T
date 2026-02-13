# 📘 Documentación del Proyecto Agent_T_T

## 🎯 Propósito del Proyecto
**Agent_T_T** es una API REST diseñada para automatizar y gestionar el envío de mensajes masivos a través de la **WhatsApp Business API**. Su objetivo principal es facilitar la comunicación con estudiantes de bootcamps, permitiendo el seguimiento de envíos, la recepción de respuestas y la sincronización de datos entre almacenamiento local, bases de datos en la nube y hojas de cálculo de Google Drive.

El sistema resuelve problemas de escalabilidad y concurrencia al migrar de una gestión puramente basada en archivos CSV a una arquitectura híbrida con base de datos SQL, manteniendo la compatibilidad con flujos de trabajo existentes en Google Sheets.

---

## 🚀 Funcionalidades Principales

### 1. Gestión de Mensajería WhatsApp
- **Envío Masivo:** Capacidad para enviar mensajes de plantilla a listas de estudiantes.
- **Webhooks:** Recepción de actualizaciones de estado (enviado, entregado, leído) y respuestas de usuarios en tiempo real.
- **Normalización:** Limpieza y validación automática de números telefónicos para asegurar el formato internacional correcto.

### 2. Gestión de Datos Híbrida
- **Dual-Write System:** Los datos se persisten simultáneamente en:
  - **SQLite/Turso:** Para consultas rápidas, integridad referencial y manejo de concurrencia.
  - **CSV/Google Sheets:** Para visualización y edición manual por parte de operadores.
- **Sincronización Automática:** Mecanismo de sincronización en segundo plano para mantener actualizados los archivos en Google Drive.

### 3. Base de Datos y CRUD
- **Soporte Multi-Entorno:**
  - **Local:** SQLite con modo WAL (Write-Ahead Logging) para alto rendimiento local.
  - **Producción:** Integración con **Turso (libSQL)** para base de datos distribuida en la nube.
- **Endpoints de Consulta:**
  - Filtrado por Bootcamp.
  - Búsqueda por número de teléfono.
  - Filtrado por rangos de fecha.
  - Estadísticas de envío y respuesta.
- **Operaciones CRUD:** API completa para crear, leer, actualizar y eliminar registros de estudiantes y bootcamps.

### 4. Integración con Google Drive
- **Carga de Datos:** Importación directa desde archivos CSV o Google Sheets alojados en Drive.
- **Actualización Remota:** Capacidad para escribir los resultados (estados de envío, respuestas) de vuelta en el archivo original en la nube.

---

## 🏗️ Arquitectura Inicial

El proyecto sigue una arquitectura modular basada en servicios, separando la lógica de negocio, la capa de datos y los controladores de la API.

### Estructura del Proyecto
```
Agent_T_T/
├── app.py                  # Punto de entrada, configuración de Flask y definición de rutas
├── services/               # Lógica de negocio y adaptadores externos
│   ├── whatsapp_service.py     # Comunicación con WhatsApp Graph API
│   ├── google_drive_service.py # Integración con Google Drive API
│   └── db_handler.py           # Abstracción de base de datos (SQLite/Turso)
├── utils/                  # Utilidades transversales
│   ├── csv_handler.py          # Manejo de archivos CSV locales
│   └── data_normalizer.py      # Limpieza y validación de datos
├── bd_envio.csv            # Archivo de datos local (caché/backup)
└── requirements.txt        # Dependencias del proyecto
```

### Flujo de Datos
1. **Ingesta:** Los datos llegan vía API desde Google Drive o carga directa.
2. **Procesamiento:** Se normalizan los teléfonos y se validan los campos.
3. **Persistencia:** Se guardan/actualizan registros en la base de datos (SQLite/Turso).
4. **Acción:** Se envían mensajes a través de `WhatsAppService`.
5. **Feedback:** Los webhooks actualizan el estado en la BD y, eventualmente, se sincronizan de vuelta a Drive.

---

## 🛠️ Herramientas y Tecnologías

### Backend
- **Lenguaje:** Python 3.x
- **Framework Web:** Flask (con `flask-cors` para manejo de orígenes cruzados).
- **Procesamiento de Datos:** Pandas (manipulación eficiente de CSV/DataFrames).

### Base de Datos
- **SQLite:** Motor de base de datos relacional ligero (uso local/dev).
- **Turso (libSQL):** Base de datos SQLite distribuida para producción (edge computing).

### APIs Externas
- **WhatsApp Business API (Meta):** Versión v22.0 (Graph API).
- **Google Drive API:** Para lectura y escritura de archivos en la nube.

### Infraestructura (Implícita/Soportada)
- **Render:** Plataforma de despliegue (detectado por configuración de disco persistente).
- **Variables de Entorno:** Gestión de configuración sensible (`.env`).

---

## 📚 Documentación Adicional
- **API Reference:** Ver `SQLITE_API_DOCS.md` para detalles de los endpoints.
- **Frontend Specs:** Ver `FRONTEND_SPECS.md` para especificaciones de la interfaz de usuario.
