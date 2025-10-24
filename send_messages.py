"""
Script para enviar mensajes de WhatsApp con botones interactivos (Sí/No)
usando WhatsApp Cloud API (Meta/Facebook).

Lee bd_envio.csv, envía mensajes a contactos con opt_in=TRUE y actualiza
el CSV con el estado de envío.
"""
import os
import time
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Configuración
CSV_PATH = os.getenv('CSV_PATH', 'bd_envio.csv')
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
PHONE_NUMBER_ID = os.getenv('PHONE_NUMBER_ID')
API_VERSION = os.getenv('API_VERSION', 'v18.0')
DELAY_SECONDS = float(os.getenv('DELAY_SECONDS', '1.0'))

# Validar configuración
if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
    raise SystemExit(
        '❌ Error: Debes configurar WHATSAPP_TOKEN y PHONE_NUMBER_ID en el archivo .env\n'
        'Lee el README.md para instrucciones de configuración.'
    )

# URL de la API de WhatsApp
API_URL = f'https://graph.facebook.com/{API_VERSION}/{PHONE_NUMBER_ID}/messages'
HEADERS = {
    'Authorization': f'Bearer {WHATSAPP_TOKEN}',
    'Content-Type': 'application/json'
}


def normalizar_telefono(telefono):
    """Normaliza el número de teléfono removiendo espacios y caracteres especiales."""
    if pd.isna(telefono) or not telefono:
        return ''
    return str(telefono).strip()


def construir_mensaje_interactivo(fila):
    """
    Construye el payload del mensaje interactivo con botones Sí/No.
    
    Estructura del mensaje:
    - Saludo personalizado con el nombre
    - Información del bootcamp
    - Fecha, horario y lugar
    - Dos botones: "Sí confirmo" y "No puedo"
    """
    nombre = fila.get('nombre', 'Estudiante')
    bootcamp = fila.get('bootcamp', '')
    inicio = fila.get('inicio_formacion', '')
    horario = fila.get('horario', '')
    lugar = fila.get('lugar', '')
    
    # Texto del mensaje
    mensaje_cuerpo = (
        f"¡Hola {nombre}! 👋\n\n"
        f"Te recordamos tu formación de *{bootcamp}*.\n\n"
        f"📅 *Inicio:* {inicio}\n"
        f"🕐 *Horario:* {horario}\n"
        f"📍 *Lugar:* {lugar}\n\n"
        f"¿Confirmas tu asistencia? Por favor selecciona una opción:"
    )
    
    # Payload según la API de WhatsApp Cloud API
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": normalizar_telefono(fila['telefono_e164']),
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": mensaje_cuerpo
            },
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": "btn_si",
                            "title": "Sí confirmo ✅"
                        }
                    },
                    {
                        "type": "reply",
                        "reply": {
                            "id": "btn_no",
                            "title": "No puedo ❌"
                        }
                    }
                ]
            }
        }
    }
    
    return payload


def enviar_mensaje(payload):
    """Envía el mensaje a la API de WhatsApp."""
    try:
        response = requests.post(API_URL, headers=HEADERS, json=payload, timeout=30)
        return response
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error de conexión: {e}")
        return None


def main():
    print("=" * 60)
    print("📱 ENVÍO DE MENSAJES DE WHATSAPP CON BOTONES INTERACTIVOS")
    print("=" * 60)
    print()
    
    # Leer CSV
    try:
        df = pd.read_csv(CSV_PATH, dtype=str)
        print(f"✅ CSV cargado: {CSV_PATH}")
        print(f"📊 Total de registros: {len(df)}")
    except FileNotFoundError:
        raise SystemExit(f"❌ Error: No se encontró el archivo {CSV_PATH}")
    
    # Crear columnas de seguimiento si no existen
    for col in ['estado_envio', 'fecha_envio', 'message_sid']:
        if col not in df.columns:
            df[col] = ''
    
    # Crear backup antes de modificar
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"bd_envio_backup_{timestamp}.csv"
    df.to_csv(backup_path, index=False)
    print(f"💾 Backup creado: {backup_path}")
    print()
    
    # Filtrar registros a enviar
    registros_a_enviar = []
    for idx, fila in df.iterrows():
        opt_in = str(fila.get('opt_in', '')).strip().upper()
        estado = str(fila.get('estado_envio', '')).strip().lower()
        
        # Solo enviar si opt_in es TRUE y no se ha enviado previamente
        if opt_in == 'TRUE' and estado != 'sent':
            registros_a_enviar.append((idx, fila))
    
    if not registros_a_enviar:
        print("ℹ️  No hay registros nuevos para enviar.")
        print("   (Todos los registros con opt_in=TRUE ya fueron enviados)")
        return
    
    print(f"📤 Registros a enviar: {len(registros_a_enviar)}")
    print("-" * 60)
    print()
    
    # Enviar mensajes
    enviados = 0
    errores = 0
    
    for idx, fila in registros_a_enviar:
        telefono = fila['telefono_e164']
        nombre = fila.get('nombre', 'Usuario')
        
        print(f"📞 Enviando a {nombre} ({telefono})...", end=' ')
        
        payload = construir_mensaje_interactivo(fila)
        response = enviar_mensaje(payload)
        
        if response and response.status_code in (200, 201):
            try:
                data = response.json()
                if 'messages' in data and len(data['messages']) > 0:
                    message_id = data['messages'][0].get('id', '')
                    df.at[idx, 'estado_envio'] = 'sent'
                    df.at[idx, 'fecha_envio'] = datetime.now().isoformat()
                    df.at[idx, 'message_sid'] = message_id
                    print(f"✅ Enviado (ID: {message_id})")
                    enviados += 1
                else:
                    df.at[idx, 'estado_envio'] = 'error'
                    df.at[idx, 'fecha_envio'] = datetime.now().isoformat()
                    print(f"❌ Error en respuesta: {data}")
                    errores += 1
            except Exception as e:
                df.at[idx, 'estado_envio'] = 'error_parse'
                print(f"❌ Error al procesar respuesta: {e}")
                errores += 1
        else:
            estado_code = response.status_code if response else 'timeout'
            df.at[idx, 'estado_envio'] = f'error_{estado_code}'
            df.at[idx, 'fecha_envio'] = datetime.now().isoformat()
            
            if response:
                try:
                    error_msg = response.json()
                    print(f"❌ Error {response.status_code}: {error_msg}")
                except:
                    print(f"❌ Error {response.status_code}")
            else:
                print("❌ Timeout o error de conexión")
            
            errores += 1
        
        # Pausa entre mensajes para evitar rate limits
        if idx < len(registros_a_enviar) - 1:
            time.sleep(DELAY_SECONDS)
    
    # Guardar cambios en el CSV
    df.to_csv(CSV_PATH, index=False)
    
    print()
    print("-" * 60)
    print("📊 RESUMEN DEL ENVÍO")
    print("-" * 60)
    print(f"✅ Enviados exitosamente: {enviados}")
    print(f"❌ Errores: {errores}")
    print(f"💾 CSV actualizado: {CSV_PATH}")
    print()
    print("🔔 El webhook debe estar activo para recibir las respuestas.")
    print("=" * 60)


if __name__ == '__main__':
    main()
