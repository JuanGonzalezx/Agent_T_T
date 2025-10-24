# 🚀 Guía de Inicio Rápido

## Configuración inicial (solo una vez)

### 1️⃣ Instalar dependencias
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2️⃣ Configurar credenciales
```powershell
# Copiar archivo de ejemplo
Copy-Item .env.example .env

# Editar .env con tus credenciales de Meta
notepad .env
```

**Obtener credenciales en**: https://developers.facebook.com/apps

- `WHATSAPP_TOKEN`: Token de acceso (empieza con EAA...)
- `PHONE_NUMBER_ID`: ID numérico del teléfono
- `VERIFY_TOKEN`: Cualquier texto secreto (ej: mi_token_123)

### 3️⃣ Verificar configuración
```powershell
python verify_setup.py
```

Si todo está ✅, continúa al paso 4.

---

## Uso diario (cada vez que envíes mensajes)

### 🔄 Flujo de 3 terminales

#### Terminal 1: Webhook (déjalo corriendo)
```powershell
.\.venv\Scripts\Activate.ps1
python webhook.py
```
**No cierres esta terminal** mientras recibas respuestas.

#### Terminal 2: Túnel ngrok (déjalo corriendo)
```powershell
ngrok http 5000
```
Copia la URL `https://xxxxx.ngrok.io` que aparece.

**Primera vez**: Configurar webhook en Meta:
1. Ve a https://developers.facebook.com/apps
2. Tu app → WhatsApp → Configuración → Webhooks
3. URL: `https://xxxxx.ngrok.io/webhook`
4. Verify Token: el mismo de tu `.env`
5. Suscríbete a "messages"

#### Terminal 3: Enviar mensajes
```powershell
.\.venv\Scripts\Activate.ps1
python send_messages.py
```
Este script termina automáticamente al finalizar.

---

## 📊 Resultado

El archivo `bd_envio.csv` se actualiza automáticamente:

**Después de enviar:**
- `estado_envio`: `sent`
- `fecha_envio`: timestamp
- `message_sid`: ID del mensaje

**Después de que el usuario responde:**
- `respuesta`: `Sí confirmo ✅` o `No puedo ❌`
- `fecha_respuesta`: timestamp
- `respuesta_id`: `btn_si` o `btn_no`

---

## 🆘 Problemas comunes

### "No se ha podido resolver la importación"
```powershell
pip install -r requirements.txt
```

### "WHATSAPP_TOKEN no configurado"
Crea el archivo `.env` y completa las credenciales.

### Webhook no recibe respuestas
- ✅ `webhook.py` corriendo
- ✅ `ngrok` corriendo
- ✅ URL configurada en Meta (termina en `/webhook`)
- ✅ Suscrito a "messages" en Meta

### Mensajes no se envían
- ✅ Token válido (no expirado)
- ✅ `PHONE_NUMBER_ID` correcto
- ✅ Números en formato +57xxx
- ✅ `opt_in=TRUE` en el CSV

---

## 📚 Más información

Lee el **README.md** completo para:
- Configuración detallada de WhatsApp Business API
- Explicación de cada paso
- Preguntas frecuentes
- Solución de problemas avanzada

---

## 📁 Archivos importantes

| Archivo | Descripción |
|---------|-------------|
| `send_messages.py` | Script de envío (ejecutar una vez) |
| `webhook.py` | Servidor receptor (mantener corriendo) |
| `verify_setup.py` | Verificador de configuración |
| `bd_envio.csv` | Base de datos de contactos |
| `.env` | Credenciales (NUNCA subir a Git) |
| `README.md` | Documentación completa |

---

¡Listo para enviar! 🎉
