# 🔧 Endpoints CRUD - Base de Datos SQLite

## Resumen de Mejoras

### ✅ Problemas Resueltos

1. **Duplicados eliminados**: Ahora `telefono_e164` es UNIQUE, no permite duplicados
2. **bootcamp_id y bootcamp_nombre se guardan correctamente**: Campos mapeados correctamente desde CSV
3. **CRUD completo implementado**: Editar campos individuales, múltiples, eliminar, vaciar
4. **Validación automática**: No se crean registros duplicados

---

## 📝 Endpoints de Edición

### 1. Actualizar UN Campo
**PUT** `/api/estudiantes/update-field`

Actualiza un solo campo de un estudiante.

**Request Body**:
```json
{
  "telefono": "+573001234567",
  "field": "nombre",
  "value": "Juan Pérez Actualizado"
}
```

**Campos permitidos**:
- `nombre`, `bootcamp_id`, `bootcamp_nombre`, `modalidad`
- `ingles_inicio`, `ingles_fin`, `inicio_formacion`, `horario`
- `lugar`, `opt_in`, `estado_envio`, `fecha_envio`, `message_id`
- `respuesta`, `fecha_respuesta`

**Ejemplo con curl**:
```bash
curl -X PUT http://localhost:5000/api/estudiantes/update-field \
  -H "Content-Type: application/json" \
  -d '{
    "telefono": "+573001234567",
    "field": "modalidad",
    "value": "Virtual"
  }'
```

**Respuesta Exitosa**:
```json
{
  "success": true,
  "message": "Campo 'modalidad' actualizado exitosamente"
}
```

---

### 2. Actualizar MÚLTIPLES Campos
**PUT** `/api/estudiantes/update-fields`

Actualiza varios campos de un estudiante en una sola operación.

**Request Body**:
```json
{
  "telefono": "+573001234567",
  "fields": {
    "nombre": "Juan Pérez",
    "modalidad": "Virtual",
    "horario": "Lunes a viernes 6pm-10pm",
    "bootcamp_nombre": "Data Science Avanzado"
  }
}
```

**Ejemplo con curl**:
```bash
curl -X PUT http://localhost:5000/api/estudiantes/update-fields \
  -H "Content-Type: application/json" \
  -d '{
    "telefono": "+573001234567",
    "fields": {
      "modalidad": "Híbrido",
      "horario": "Sábados 8am-12pm"
    }
  }'
```

**Respuesta Exitosa**:
```json
{
  "success": true,
  "message": "2 campo(s) actualizado(s) exitosamente"
}
```

---

## 🗑️ Endpoints de Eliminación

### 3. Eliminar Un Estudiante
**DELETE** `/api/estudiantes/delete/<phone>`

Elimina un estudiante específico por su teléfono.

**Ejemplo**:
```bash
curl -X DELETE http://localhost:5000/api/estudiantes/delete/573001234567
```

**Respuesta Exitosa**:
```json
{
  "success": true,
  "message": "Estudiante eliminado (1 registro(s))"
}
```

---

### 4. Eliminar Un Bootcamp
**DELETE** `/api/bootcamps/delete/<bootcamp_id>`

Elimina un bootcamp del catálogo.

**Ejemplo**:
```bash
curl -X DELETE http://localhost:5000/api/bootcamps/delete/IA_2024_01
```

**Respuesta Exitosa**:
```json
{
  "success": true,
  "message": "Bootcamp IA_2024_01 eliminado"
}
```

---

### 5. Vaciar Tabla de Estudiantes
**DELETE** `/api/estudiantes/clear-all`

⚠️ **PELIGRO**: Elimina TODOS los estudiantes. No se puede deshacer.

**Ejemplo**:
```bash
curl -X DELETE http://localhost:5000/api/estudiantes/clear-all
```

**Respuesta Exitosa**:
```json
{
  "success": true,
  "message": "150 estudiante(s) eliminado(s)"
}
```

---

### 6. Vaciar Tabla de Bootcamps
**DELETE** `/api/bootcamps/clear-all`

⚠️ **PELIGRO**: Elimina TODOS los bootcamps. No se puede deshacer.

**Ejemplo**:
```bash
curl -X DELETE http://localhost:5000/api/bootcamps/clear-all
```

**Respuesta Exitosa**:
```json
{
  "success": true,
  "message": "4 bootcamp(s) eliminado(s)"
}
```

---

### 7. Resetear Base de Datos Completa
**DELETE** `/api/database/reset`

⚠️ **PELIGRO EXTREMO**: Elimina TODO (estudiantes + bootcamps). No se puede deshacer.

**Ejemplo**:
```bash
curl -X DELETE http://localhost:5000/api/database/reset
```

**Respuesta Exitosa**:
```json
{
  "success": true,
  "message": "Base de datos vaciada: 150 estudiante(s) eliminado(s), 4 bootcamp(s) eliminado(s)"
}
```

---

## 🔄 Recrear Base de Datos desde CSV

Si necesitas recrear la base de datos limpia desde el CSV actual:

```bash
python recreate_db.py
```

Este script:
1. ✅ Elimina la base de datos existente
2. ✅ Crea una nueva base de datos limpia
3. ✅ Carga bootcamps desde CSV
4. ✅ Carga estudiantes sin duplicados
5. ✅ Muestra estadísticas de verificación

**Salida esperada**:
```
🔄 Recreando base de datos SQLite...
======================================================================
✅ Base de datos antigua eliminada: whatsapp_tracking.db

📦 Creando nueva base de datos...
✅ Base de datos creada con tablas: estudiantes, bootcamps

🏫 Registrando bootcamps...
   ✓ 123 - Inteligencia Artificial

👥 Registrando estudiantes...
   ✓ +573154963483 - patricio
   ✓ +573113116974 - patricio
   ✓ +573146827796 - patricio
   ✓ +573205770097 - talentoTechsss

✅ 4 estudiante(s) registrado(s)
```

---

## 🔒 Validaciones Implementadas

### Prevención de Duplicados

La tabla `estudiantes` tiene un constraint **UNIQUE** en `telefono_e164`:

```sql
CREATE TABLE estudiantes (
    ...
    telefono_e164 TEXT NOT NULL UNIQUE,
    ...
)
```

Si intentas insertar un teléfono duplicado:
- ✅ Se **actualiza** el registro existente (UPSERT)
- ✅ **NO** se crea un duplicado

### Lógica de Actualización Inteligente

Cuando haces UPSERT, solo se actualizan los campos que **no están vacíos**:

```sql
ON CONFLICT(telefono_e164) DO UPDATE SET
    estado_envio = CASE 
        WHEN excluded.estado_envio != '' THEN excluded.estado_envio 
        ELSE estudiantes.estado_envio 
    END
```

Esto evita sobrescribir datos existentes con valores vacíos.

---

## 🧪 Ejemplos de Uso Completos

### Ejemplo 1: Actualizar modalidad de un estudiante
```bash
curl -X PUT http://localhost:5000/api/estudiantes/update-field \
  -H "Content-Type: application/json" \
  -d '{
    "telefono": "573001234567",
    "field": "modalidad",
    "value": "Híbrido"
  }'
```

### Ejemplo 2: Actualizar varios campos a la vez
```bash
curl -X PUT http://localhost:5000/api/estudiantes/update-fields \
  -H "Content-Type: application/json" \
  -d '{
    "telefono": "573001234567",
    "fields": {
      "bootcamp_id": "DS_2025_01",
      "bootcamp_nombre": "Data Science 2025",
      "modalidad": "Presencial",
      "horario": "Lunes a Viernes 2pm-6pm"
    }
  }'
```

### Ejemplo 3: Eliminar estudiante específico
```bash
curl -X DELETE http://localhost:5000/api/estudiantes/delete/573001234567
```

### Ejemplo 4: Vaciar toda la base de datos y recargar desde CSV
```bash
# 1. Resetear base de datos
curl -X DELETE http://localhost:5000/api/database/reset

# 2. Recargar desde CSV
python recreate_db.py
```

---

## 📊 Verificación de Datos

### Ver todos los bootcamps
```bash
curl http://localhost:5000/api/bootcamps
```

### Ver todos los estudiantes (primeros 10)
```bash
curl "http://localhost:5000/api/estudiantes/all?limit=10&offset=0"
```

### Ver estudiantes de un bootcamp
```bash
curl http://localhost:5000/api/estudiantes/bootcamp/123
```

### Ver estadísticas generales
```bash
curl http://localhost:5000/api/estadisticas
```

---

## 🛡️ Manejo de Errores

### Error: Campo no válido
```json
{
  "success": false,
  "error": "Campo no válido: telefono_invalido"
}
```

### Error: Estudiante no encontrado
```json
{
  "success": false,
  "error": "No se encontró estudiante con teléfono +573001234567"
}
```

### Error: Campos requeridos faltantes
```json
{
  "success": false,
  "error": "Campos requeridos: telefono, field, value"
}
```

---

## 📝 Notas Importantes

1. **Teléfonos sin +**: Los endpoints aceptan teléfonos con o sin el prefijo `+`
   - `+573001234567` ✅
   - `573001234567` ✅

2. **UNIQUE por teléfono**: Ya no se permite el mismo teléfono múltiples veces
   - Antes: (telefono, bootcamp_id) UNIQUE ❌
   - Ahora: telefono UNIQUE ✅

3. **Actualización inteligente**: Los campos vacíos no sobrescriben datos existentes

4. **Sincronización CSV ↔ SQLite**: Los cambios en SQLite NO se reflejan automáticamente en el CSV. Para sincronizar:
   - Opción 1: Usa los endpoints existentes que actualizan ambos
   - Opción 2: Exporta desde SQLite y sobrescribe el CSV

---

## 🚀 Flujo de Trabajo Recomendado

1. **Carga inicial**: Usa `/api/google/upload` para cargar CSV → SQLite
2. **Consultas**: Usa los endpoints GET de SQLite (más rápidos)
3. **Ediciones**: Usa los endpoints PUT/DELETE de SQLite
4. **Sincronización**: El webhook y send-batch actualizan ambos (CSV + SQLite)
5. **Reset**: Si algo sale mal, usa `python recreate_db.py`

---

## ✅ Checklist de Verificación

- [x] Duplicados eliminados (UNIQUE en telefono_e164)
- [x] bootcamp_id se guarda correctamente
- [x] bootcamp_nombre se guarda correctamente
- [x] Endpoint para actualizar 1 campo
- [x] Endpoint para actualizar múltiples campos
- [x] Endpoint para eliminar estudiante
- [x] Endpoint para eliminar bootcamp
- [x] Endpoint para vaciar tabla estudiantes
- [x] Endpoint para vaciar tabla bootcamps
- [x] Endpoint para resetear toda la DB
- [x] Script para recrear DB desde CSV
- [x] Validación de campos permitidos
- [x] Manejo de errores robusto
