# 📱 Especificaciones Frontend - Vista de Mensajes

## 🎯 Objetivo
Crear una vista para visualizar y filtrar todos los mensajes enviados a estudiantes, permitiendo filtrar principalmente por `bootcamp_id`, además de filtros secundarios por teléfono y fecha.

---

## 🏗️ Arquitectura de Componentes

### Componente Principal: `MensajesView`
```
MensajesView/
├── FiltersPanel (Filtros)
├── StatsCards (Estadísticas - opcional)
├── MensajesTable (Tabla de datos)
└── Pagination (Paginación)
```

---

## 📊 Diseño de UI/UX

### 1. Panel de Filtros
```
┌─────────────────────────────────────────────────────────┐
│  🔍 Filtros                                              │
├─────────────────────────────────────────────────────────┤
│  Bootcamp: [Dropdown ▼]  Teléfono: [_______]           │
│  Desde: [📅] Hasta: [📅]  [Buscar] [Limpiar]            │
└─────────────────────────────────────────────────────────┘
```

**Campos:**
- **Bootcamp** (Dropdown): Opción principal, carga desde `/api/bootcamps`
- **Teléfono** (Input): Búsqueda exacta o parcial
- **Rango de fechas** (Date pickers): Desde - Hasta
- **Botones**: Buscar (aplicar filtros) y Limpiar (resetear)

### 2. Cards de Estadísticas (Opcional)
```
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ 📨 150   │ │ ✅ 120   │ │ ❌ 15    │ │ ⏳ 15    │
│ Enviados │ │ Sí       │ │ No       │ │ Pendiente│
└──────────┘ └──────────┘ └──────────┘ └──────────┘
```

### 3. Tabla de Mensajes
```
┌──────────────┬──────────┬─────────────┬───────────┬────────┬─────────┬──────────┐
│ Teléfono     │ Nombre   │ Bootcamp    │ Modalidad │ Estado │ Fecha   │ Respuesta│
├──────────────┼──────────┼─────────────┼───────────┼────────┼─────────┼──────────┤
│ +5731234567  │ Juan P.  │ IA 2024     │ Virtual   │ 🟢 Sent│ 28/10   │ ✅ Sí    │
│ +5737654321  │ María G. │ Data Science│ Presencial│ 🟢 Sent│ 28/10   │ ⏳ -     │
└──────────────┴──────────┴─────────────┴───────────┴────────┴─────────┴──────────┘
```

**Columnas:**
- Teléfono (con formato)
- Nombre
- Bootcamp (nombre + id en tooltip)
- Modalidad
- Estado (badge con color)
- Fecha de envío (formato corto)
- Respuesta (con íconos visuales)

**Acciones (opcional):**
- 👁️ Ver detalle completo
- ✏️ Editar campos
- 🗑️ Eliminar registro

---

## 🔌 Integración con API

### Endpoints a Consumir

#### 1. Cargar Dropdown de Bootcamps
```javascript
GET /api/bootcamps
Response:
{
  "success": true,
  "count": 4,
  "bootcamps": [
    { "bootcamp_id": "IA_2024_01", "bootcamp_nombre": "Inteligencia Artificial" },
    { "bootcamp_id": "DS_2024_01", "bootcamp_nombre": "Data Science" }
  ]
}
```

#### 2. Filtrar por Bootcamp (Principal)
```javascript
GET /api/estudiantes/bootcamp/{bootcamp_id}
Response:
{
  "success": true,
  "bootcamp_id": "IA_2024_01",
  "count": 25,
  "estudiantes": [...]
}
```

#### 3. Buscar por Teléfono
```javascript
GET /api/estudiantes/phone/{phone}
Response:
{
  "success": true,
  "phone": "+573001234567",
  "count": 1,
  "estudiantes": [...]
}
```

#### 4. Filtrar por Rango de Fechas
```javascript
GET /api/estudiantes/date-range?fecha_inicio=2024-01-01&fecha_fin=2024-01-31
Response:
{
  "success": true,
  "fecha_inicio": "2024-01-01",
  "fecha_fin": "2024-01-31",
  "count": 75,
  "estudiantes": [...]
}
```

#### 5. Obtener Todos (con paginación)
```javascript
GET /api/estudiantes/all?limit=50&offset=0
Response:
{
  "success": true,
  "total": 150,
  "limit": 50,
  "offset": 0,
  "count": 50,
  "estudiantes": [...]
}
```

#### 6. Estadísticas (Opcional)
```javascript
GET /api/estadisticas
Response:
{
  "success": true,
  "estadisticas": {
    "total_estudiantes": 150,
    "mensajes_enviados": 150,
    "confirmaron_si": 120,
    "confirmaron_no": 15,
    "pendientes_respuesta": 15,
    "tasa_respuesta": 90.0
  }
}
```

---

## 🎨 Diseño Visual

### Paleta de Colores Sugerida
- **Estados:**
  - 🟢 Verde: `sent` (enviado exitoso)
  - 🔴 Rojo: `error` (error de envío)
  - ⚪ Gris: `pending` (pendiente)

- **Respuestas:**
  - ✅ Verde: "Sí" (confirmado)
  - ❌ Rojo: "No" (rechazado)
  - ⏳ Gris: Sin respuesta

### Badges Sugeridos
```html
<!-- Estado -->
<span class="badge bg-success">Enviado</span>
<span class="badge bg-danger">Error</span>
<span class="badge bg-secondary">Pendiente</span>

<!-- Respuesta -->
<span class="badge bg-success">✓ Sí</span>
<span class="badge bg-danger">✗ No</span>
<span class="badge bg-secondary">⏳ Sin respuesta</span>
```

---

## 🛠️ Librerías Recomendadas

### Opción 1: React + Material-UI
```bash
npm install @mui/material @emotion/react @emotion/styled
npm install @mui/x-data-grid  # Para la tabla
npm install @mui/x-date-pickers  # Para date pickers
```

**Componentes clave:**
- `DataGrid` para tabla con filtros y paginación integrados
- `Select` para dropdown de bootcamps
- `TextField` para búsqueda por teléfono
- `DatePicker` para rango de fechas

### Opción 2: React + Ant Design
```bash
npm install antd
```

**Componentes clave:**
- `Table` con `filters` y `pagination`
- `Select` para bootcamps
- `Input.Search` para teléfono
- `DatePicker.RangePicker` para fechas

### Opción 3: Vue + Element Plus
```bash
npm install element-plus
```

**Componentes clave:**
- `el-table` con filtros
- `el-select` para bootcamps
- `el-input` para teléfono
- `el-date-picker` tipo `daterange`

---

## 📝 Ejemplo de Código (React + MUI)

```jsx
import React, { useState, useEffect } from 'react';
import {
  Box, Select, MenuItem, TextField, Button, 
  Card, CardContent, Typography
} from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import { DatePicker } from '@mui/x-date-pickers';

const MensajesView = () => {
  const [bootcamps, setBootcamps] = useState([]);
  const [selectedBootcamp, setSelectedBootcamp] = useState('');
  const [estudiantes, setEstudiantes] = useState([]);
  const [loading, setLoading] = useState(false);

  // Cargar bootcamps al montar
  useEffect(() => {
    fetch('https://agent-t-t.onrender.com/api/bootcamps')
      .then(res => res.json())
      .then(data => setBootcamps(data.bootcamps));
  }, []);

  // Filtrar por bootcamp
  const handleBootcampChange = (bootcampId) => {
    setLoading(true);
    fetch(`https://agent-t-t.onrender.com/api/estudiantes/bootcamp/${bootcampId}`)
      .then(res => res.json())
      .then(data => {
        setEstudiantes(data.estudiantes);
        setLoading(false);
      });
  };

  const columns = [
    { field: 'telefono_e164', headerName: 'Teléfono', width: 150 },
    { field: 'nombre', headerName: 'Nombre', width: 150 },
    { field: 'bootcamp_nombre', headerName: 'Bootcamp', width: 200 },
    { field: 'modalidad', headerName: 'Modalidad', width: 120 },
    { field: 'estado_envio', headerName: 'Estado', width: 100 },
    { field: 'respuesta', headerName: 'Respuesta', width: 100 },
  ];

  return (
    <Box sx={{ p: 3 }}>
      {/* Filtros */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6">🔍 Filtros</Typography>
          <Box sx={{ display: 'flex', gap: 2, mt: 2 }}>
            <Select
              value={selectedBootcamp}
              onChange={(e) => handleBootcampChange(e.target.value)}
              sx={{ minWidth: 200 }}
            >
              <MenuItem value="">Todos los bootcamps</MenuItem>
              {bootcamps.map(bc => (
                <MenuItem key={bc.bootcamp_id} value={bc.bootcamp_id}>
                  {bc.bootcamp_nombre}
                </MenuItem>
              ))}
            </Select>
            
            <TextField
              placeholder="Buscar por teléfono"
              sx={{ minWidth: 200 }}
            />
            
            <Button variant="contained">Buscar</Button>
            <Button variant="outlined">Limpiar</Button>
          </Box>
        </CardContent>
      </Card>

      {/* Tabla */}
      <DataGrid
        rows={estudiantes}
        columns={columns}
        pageSize={25}
        loading={loading}
        autoHeight
      />
    </Box>
  );
};

export default MensajesView;
```

---

## ✅ Checklist de Implementación

### Fase 1: Estructura Base
- [ ] Crear componente `MensajesView`
- [ ] Implementar layout básico (filtros + tabla)
- [ ] Configurar routing (si aplica)

### Fase 2: Integración API
- [ ] Conectar con `/api/bootcamps` para dropdown
- [ ] Implementar filtro por bootcamp (principal)
- [ ] Implementar filtro por teléfono
- [ ] Implementar filtro por fechas
- [ ] Cargar datos con paginación

### Fase 3: UI/UX
- [ ] Agregar badges de color para estados
- [ ] Implementar loading states
- [ ] Agregar mensajes de "sin resultados"
- [ ] Hacer tabla responsive

### Fase 4: Funcionalidades Extra (Opcional)
- [ ] Cards de estadísticas
- [ ] Modal de detalle completo
- [ ] Botones de edición (CRUD)
- [ ] Export a Excel/CSV
- [ ] Búsqueda en tiempo real

---

## 🚀 Flujo de Usuario

1. **Usuario entra a la vista** → Se cargan todos los mensajes (paginados)
2. **Selecciona un bootcamp del dropdown** → Filtra automáticamente
3. **Ingresa un teléfono** → Búsqueda específica
4. **Selecciona rango de fechas** → Filtra por período
5. **Hace clic en "Limpiar"** → Vuelve a vista completa
6. **(Opcional) Hace clic en "Ver"** → Modal con detalle completo
7. **(Opcional) Hace clic en "Editar"** → Formulario de actualización

---

## 📚 Recursos Adicionales

- **API Docs**: `SQLITE_API_DOCS.md`
- **Base URL**: `https://agent-t-t.onrender.com`
- **Estructura de datos**: Ver respuestas de API en documentación

---

**Última actualización:** 29 de octubre, 2025
