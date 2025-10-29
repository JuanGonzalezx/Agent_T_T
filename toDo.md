# 📋 TODO List - Agent_T_T

---

## 🔄 Tareas Pendientes

### 🎨 Frontend - Vista de Visualización de Mensajes
- [ ] **Crear página/componente de visualización de mensajes enviados**
  - [ ] Diseñar layout de la tabla con columnas principales:
    - Teléfono, Nombre, Bootcamp, Modalidad, Estado, Fecha Envío, Respuesta
  - [ ] Implementar tabla responsive (DataTable, AG-Grid, o similar)
  - [ ] Agregar indicadores visuales (badges de color para estados)

- [ ] **Implementar sistema de filtros**
  - [ ] **Filtro principal: Dropdown de Bootcamps**
    - Consumir `GET /api/bootcamps` para poblar opciones
    - Aplicar filtro con `GET /api/estudiantes/bootcamp/{id}`
  - [ ] **Filtro secundario: Búsqueda por teléfono**
    - Input de búsqueda con validación
    - Consumir `GET /api/estudiantes/phone/{phone}`
  - [ ] **Filtro de fechas**
    - Date picker para rango (fecha inicio - fecha fin)
    - Consumir `GET /api/estudiantes/date-range?fecha_inicio=X&fecha_fin=Y`
  - [ ] Botón "Limpiar filtros" para resetear vista

- [ ] **Implementar paginación**
  - [ ] Controles de paginación (anterior/siguiente)
  - [ ] Selector de items por página (10, 25, 50, 100)
  - [ ] Indicador de "Mostrando X-Y de Z registros"

- [ ] **Panel de estadísticas (opcional)**
  - [ ] Consumir `GET /api/estadisticas`
  - [ ] Mostrar cards con métricas:
    - Total enviados, Confirmados Sí/No, Pendientes, Tasa de respuesta
  - [ ] Gráfico simple (opcional)

- [ ] **Acciones sobre registros (opcional)**
  - [ ] Botón "Ver detalle" para modal con info completa
  - [ ] Botón "Editar" (actualizar campos via CRUD)
  - [ ] Botón "Eliminar" con confirmación

### 🔧 Backend & Servicios
- [ ] **Crear botón y configurar envío masivo** en el backend
  - Implementar endpoint para envío masivo
  - Validar datos antes del envío
  - Manejo de errores y respuestas

### 🎨 Frontend
- [ ] **Revisar detalles de frontend**
  - Mejorar UI/UX
  - Validar funcionalidad de botones
  - Responsive design

### 📱 WhatsApp & Meta
- [ ] **Actualizar o añadir nuevo número** de Talento Tech
  - Configurar nuevo número en Meta
  - Actualizar credenciales en el sistema

### 📖 Documentación
- [ ] **Agregar manual de usuario**
  - Crear guía de uso del sistema
  - Incluir capturas de pantalla
  - Documentar casos de uso comunes

---

## ✅ Tareas Completadas

- [x] **Revisar funciones repetidas** en `csv_handler` y `data_normalizer`
  - ✅ Identificado código duplicado en `add_tracking_columns()`
  - ✅ Refactorizado para usar función centralizada de `data_normalizer`
  - ✅ Eliminada variable `_tracking_columns` innecesaria

- [x] **Revisar y normalizar campos** del `bd_envio.csv`
  - ✅ Eliminadas columnas obsoletas: `estado_envio`, `fecha_envio`, `message_sid`
  - ✅ Renombradas columnas: `_simple` removido (estado_envio, fecha_envio, message_id)
  - ✅ Eliminada columna `respuesta_id` (no utilizada)
  - ✅ Añadida columna `bootcamp_id` después de `nombre`
  - ✅ Renombrada columna `bootcamp` a `bootcamp_nombre`
  - ✅ Actualizado código en `csv_handler.py`, `data_normalizer.py` y `app.py`

- [x] **Configurar webhook** para actualizar dinámicamente el archivo
  - Implementar webhook de Google Drive
  - Actualizar `fileId` de forma automática
  - Validar sincronización

- [x] **Implementar base de datos SQLite**
  - ✅ Creadas tablas: `estudiantes` y `bootcamps`
  - ✅ Constraint UNIQUE en `telefono_e164`
  - ✅ 4 índices optimizados para búsquedas
  - ✅ Dual-write CSV + SQLite en todos los endpoints
  - ✅ WAL mode + reintentos para concurrencia
  - ✅ 13 endpoints CRUD completos (consulta, editar, eliminar)
  - ✅ Documentación completa en `SQLITE_API_DOCS.md`

### 📱 WhatsApp & Meta
- [x] **Revisar plantillas** en Meta Developer
  - Verificar plantillas activas
  - Actualizar mensajes si es necesario

---
  
**Última actualización:** 28 de octubre, 2025
