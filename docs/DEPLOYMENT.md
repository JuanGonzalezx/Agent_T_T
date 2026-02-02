# Guía de Despliegue

## WhatsApp Messaging API - Talento Tech

Esta guía cubre el despliegue del backend en diferentes plataformas.

---

## Tabla de Contenidos

1. [Render (Recomendado)](#1-render-recomendado)
2. [Railway](#2-railway)
3. [Docker](#3-docker)
4. [VPS Manual](#4-vps-manual)
5. [Configuración del Webhook](#5-configuración-del-webhook)
6. [Verificación Post-Despliegue](#6-verificación-post-despliegue)

---

## 1. Render (Recomendado)

### Paso 1: Crear cuenta y conectar repositorio

1. Ir a [render.com](https://render.com) y crear cuenta
2. Click en "New +" → "Web Service"
3. Conectar cuenta de GitHub
4. Seleccionar repositorio `Agent_T_T`

### Paso 2: Configurar servicio

| Campo | Valor |
|-------|-------|
| Name | `agent-t-t` |
| Region | Oregon (US West) |
| Branch | `main` |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app` |
| Instance Type | Free / Starter |

### Paso 3: Variables de entorno

En la sección "Environment Variables", agregar:

```
ACCESS_TOKEN=EAAxxxxxxxx
PHONE_NUMBER_ID=123456789
VERSION=v22.0
WEBHOOK_VERIFY_TOKEN=mi_token_secreto
TURSO_DATABASE_URL=libsql://mi-db.turso.io
TURSO_AUTH_TOKEN=eyJhbGciOiJxxxxxxx
DELAY_SECONDS=1.5
```

### Paso 4: Deploy

1. Click en "Create Web Service"
2. Esperar a que termine el build (2-5 minutos)
3. La URL será: `https://agent-t-t.onrender.com`

### Auto-Deploy

Render hace deploy automático en cada push a `main`.

---

## 2. Railway

### Paso 1: Crear proyecto

1. Ir a [railway.app](https://railway.app)
2. "New Project" → "Deploy from GitHub repo"
3. Seleccionar repositorio

### Paso 2: Configurar

Railway detecta automáticamente que es Python. Agregar:

**Procfile** (si no existe):
```
web: gunicorn app:app
```

### Paso 3: Variables de entorno

En Settings → Variables, agregar las mismas variables que Render.

### Paso 4: Dominio

1. Settings → Domains
2. "Generate Domain" o usar dominio personalizado

---

## 3. Docker

### Dockerfile

```dockerfile
# Imagen base de Python
FROM python:3.10-slim

# Directorio de trabajo
WORKDIR /app

# Copiar requirements primero (aprovecha cache de Docker)
COPY requirements.txt .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .

# Puerto expuesto
EXPOSE 5000

# Variables de entorno por defecto
ENV FLASK_ENV=production
ENV PORT=5000

# Comando de inicio
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "5000:5000"
    environment:
      - ACCESS_TOKEN=${ACCESS_TOKEN}
      - PHONE_NUMBER_ID=${PHONE_NUMBER_ID}
      - VERSION=v22.0
      - WEBHOOK_VERIFY_TOKEN=${WEBHOOK_VERIFY_TOKEN}
      - TURSO_DATABASE_URL=${TURSO_DATABASE_URL}
      - TURSO_AUTH_TOKEN=${TURSO_AUTH_TOKEN}
      - DELAY_SECONDS=1.5
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Comandos Docker

```bash
# Construir imagen
docker build -t whatsapp-api .

# Ejecutar contenedor
docker run -d \
  --name whatsapp-api \
  -p 5000:5000 \
  --env-file .env \
  whatsapp-api

# Con docker-compose
docker-compose up -d

# Ver logs
docker logs -f whatsapp-api
```

---

## 4. VPS Manual

### Requisitos

- Ubuntu 20.04+ / Debian 11+
- Python 3.10+
- Nginx
- Supervisor (o systemd)

### Paso 1: Preparar servidor

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar dependencias
sudo apt install -y python3 python3-pip python3-venv nginx supervisor git

# Crear usuario para la app
sudo useradd -m -s /bin/bash whatsapp-api
```

### Paso 2: Clonar y configurar

```bash
# Cambiar a usuario de la app
sudo su - whatsapp-api

# Clonar repositorio
git clone https://github.com/JuanGonzalezx/Agent_T_T.git
cd Agent_T_T

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
pip install gunicorn

# Crear archivo de variables de entorno
nano .env
# (agregar todas las variables)
```

### Paso 3: Configurar Supervisor

```bash
sudo nano /etc/supervisor/conf.d/whatsapp-api.conf
```

```ini
[program:whatsapp-api]
directory=/home/whatsapp-api/Agent_T_T
command=/home/whatsapp-api/Agent_T_T/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:5000 app:app
user=whatsapp-api
autostart=true
autorestart=true
stderr_logfile=/var/log/whatsapp-api/error.log
stdout_logfile=/var/log/whatsapp-api/access.log
environment=
    ACCESS_TOKEN="tu_token",
    PHONE_NUMBER_ID="tu_id",
    WEBHOOK_VERIFY_TOKEN="tu_verify_token",
    TURSO_DATABASE_URL="tu_url",
    TURSO_AUTH_TOKEN="tu_auth"
```

```bash
# Crear directorio de logs
sudo mkdir -p /var/log/whatsapp-api
sudo chown whatsapp-api:whatsapp-api /var/log/whatsapp-api

# Recargar supervisor
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start whatsapp-api
```

### Paso 4: Configurar Nginx

```bash
sudo nano /etc/nginx/sites-available/whatsapp-api
```

```nginx
server {
    listen 80;
    server_name tu-dominio.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
    }
}
```

```bash
# Habilitar sitio
sudo ln -s /etc/nginx/sites-available/whatsapp-api /etc/nginx/sites-enabled/

# Verificar configuración
sudo nginx -t

# Reiniciar Nginx
sudo systemctl restart nginx
```

### Paso 5: SSL con Certbot

```bash
# Instalar Certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtener certificado
sudo certbot --nginx -d tu-dominio.com

# Renovación automática
sudo certbot renew --dry-run
```

---

## 5. Configuración del Webhook

### En Meta for Developers

1. Ir a [developers.facebook.com](https://developers.facebook.com)
2. Seleccionar tu aplicación
3. Menú izquierdo: WhatsApp → Configuration
4. En "Webhook":
   - Callback URL: `https://tu-dominio.com/webhook`
   - Verify Token: El mismo valor de `WEBHOOK_VERIFY_TOKEN`
5. Click "Verify and Save"
6. En "Webhook fields", suscribirse a:
   - `messages`
   - `message_deliveries` (opcional)
   - `message_reads` (opcional)

### Verificar Webhook

```bash
# Verificación manual
curl "https://tu-dominio.com/webhook?hub.mode=subscribe&hub.verify_token=tu_token&hub.challenge=test123"

# Debe responder: test123
```

---

## 6. Verificación Post-Despliegue

### Checklist

- [ ] Health check responde correctamente
- [ ] Credenciales de WhatsApp válidas
- [ ] Conexión a Turso exitosa
- [ ] Webhook verificado en Meta
- [ ] Envío de mensaje de prueba exitoso
- [ ] Recepción de respuesta funciona

### Comandos de Verificación

```bash
# Health check
curl https://tu-dominio.com/health

# Información de la API
curl https://tu-dominio.com/

# Estadísticas
curl https://tu-dominio.com/api/estadisticas

# Enviar mensaje de prueba
curl -X POST https://tu-dominio.com/api/messages/send-simple \
  -H "Content-Type: application/json" \
  -d '{"phone": "+573001234567", "template_name": "hello_world", "language_code": "es"}'
```

### Monitoreo de Logs

```bash
# Render
# Ver logs en el dashboard de Render

# Docker
docker logs -f whatsapp-api

# Supervisor
tail -f /var/log/whatsapp-api/access.log
tail -f /var/log/whatsapp-api/error.log

# Journalctl (systemd)
journalctl -u whatsapp-api -f
```

---

## Troubleshooting

### Error: "Credenciales no válidas"

- Verificar que `ACCESS_TOKEN` no haya expirado
- Regenerar token en Meta for Developers si es necesario

### Error: "Webhook verification failed"

- Verificar que `WEBHOOK_VERIFY_TOKEN` coincida exactamente
- Asegurar que la URL del webhook sea accesible públicamente
- Revisar que el certificado SSL sea válido

### Error: "Connection to Turso failed"

- Verificar `TURSO_DATABASE_URL` (debe empezar con `libsql://`)
- Verificar que `TURSO_AUTH_TOKEN` sea válido
- Comprobar que la base de datos exista en Turso

### Aplicación lenta en Render Free Tier

- El tier gratuito "duerme" después de 15 minutos de inactividad
- El primer request toma ~30 segundos mientras "despierta"
- Considerar upgrade a tier de pago para producción

---

## Actualizar Despliegue

### Render / Railway

Push a `main` dispara deploy automático.

### Docker

```bash
docker-compose pull
docker-compose up -d
```

### VPS

```bash
cd /home/whatsapp-api/Agent_T_T
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo supervisorctl restart whatsapp-api
```
