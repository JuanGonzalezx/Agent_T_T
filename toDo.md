# 📋 TODO List - Agent_T_T

---

## 🔄 Tareas Pendientes

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

### 📱 WhatsApp & Meta
- [x] **Revisar plantillas** en Meta Developer
  - Verificar plantillas activas
  - Actualizar mensajes si es necesario

---
  
**Última actualización:** 28 de octubre, 2025
