import os
import time
import json
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# --------------------------------------------------------------
# Cargar variables de entorno
# --------------------------------------------------------------

load_dotenv()

# Configuración desde variables de entorno o valores por defecto
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERSION = os.getenv("VERSION", "v22.0")

CSV_PATH = "bd_envio.csv"
MENSAJE = "Juan diego gay "
DELAY_SEGUNDOS = 1.5


# --------------------------------------------------------------
# Función para construir payload de mensaje de texto
# --------------------------------------------------------------

def get_text_message_input(recipient, text):
    """Construye el payload JSON para enviar un mensaje de texto."""
    return json.dumps({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "text",
        "text": {"preview_url": False, "body": text}
    })


# --------------------------------------------------------------
# Función para enviar mensaje de WhatsApp
# --------------------------------------------------------------

def send_message(data):
    """
    Envía un mensaje de WhatsApp usando la API de Cloud.
    
    Args:
        data: JSON string con el payload del mensaje
    
    Returns:
        tuple: (success, message_id o error)
    """
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {ACCESS_TOKEN}",
    }

    url = f"https://graph.facebook.com/{VERSION}/{PHONE_NUMBER_ID}/messages"

    try:
        response = requests.post(url, data=data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            response_data = response.json()
            if 'messages' in response_data and len(response_data['messages']) > 0:
                message_id = response_data['messages'][0].get('id', '')
                return True, message_id
            else:
                return False, f"Respuesta inesperada: {response_data}"
        else:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get('error', {}).get('message', response.text)
            return False, f"Error {response.status_code}: {error_msg}"
    
    except requests.exceptions.Timeout:
        return False, "Timeout - La API no respondió a tiempo"
    except requests.exceptions.ConnectionError:
        return False, "Error de conexión - Verifica tu internet"
    except Exception as e:
        return False, f"Error inesperado: {str(e)}"


def enviar_mensaje_texto(telefono, mensaje):
    """
    Envía un mensaje de texto a un número de WhatsApp.
    
    Args:
        telefono: Número en formato E.164 (ej: +573001234567)
        mensaje: Texto del mensaje a enviar
    
    Returns:
        tuple: (success, message_id o error)
    """
    # Normalizar teléfono (remover + y espacios)
    telefono = str(telefono).strip().replace('+', '').replace(' ', '').replace('-', '')
    
    # Construir payload usando la función del ejemplo
    data = get_text_message_input(recipient=telefono, text=mensaje)
    
    # Enviar usando la función del ejemplo
    return send_message(data)



def main():
    print("\n" + "="*70)
    print("  📱 ENVÍO DE MENSAJES DE WHATSAPP")
    print("="*70)
    print(f"\n📄 Mensaje a enviar: \"{MENSAJE}\"")
    print(f"📂 CSV: {CSV_PATH}\n")
    
    # Validar configuración
    if not ACCESS_TOKEN or ACCESS_TOKEN == "tu_token_aqui":
        print("❌ ERROR: Debes configurar ACCESS_TOKEN")
        print("   Crea un archivo .env con tus credenciales o edita el script.\n")
        print("   Lee la guía COMO_OBTENER_TOKENS.md para saber cómo obtenerlos.\n")
        return
    
    # Leer CSV
    try:
        df = pd.read_csv(CSV_PATH, dtype=str)
        print(f"✅ CSV cargado: {len(df)} registros encontrados")
        
        # Debug: mostrar valores de las columnas clave
        print("\n🔍 Debug - Primeras filas:")
        for idx, fila in df.iterrows():
            if idx >= 3:
                break
            opt_in = fila.get('opt_in', 'N/A')
            estado = fila.get('estado_envio_simple', 'N/A')
            print(f"  Fila {idx}: opt_in='{opt_in}' | estado_envio_simple='{estado}'")
        print()
        
    except FileNotFoundError:
        print(f"❌ ERROR: No se encontró el archivo {CSV_PATH}")
        return
    except Exception as e:
        print(f"❌ ERROR al leer CSV: {e}")
        return
    
    # Verificar columnas necesarias
    if 'telefono_e164' not in df.columns:
        print("❌ ERROR: El CSV debe tener una columna 'telefono_e164'")
        return
    
    # Crear columnas de seguimiento si no existen
    for col in ['estado_envio_simple', 'fecha_envio_simple', 'message_id_simple']:
        if col not in df.columns:
            df[col] = ''
    
    # Crear backup
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"bd_envio_backup_simple_{timestamp}.csv"
    df.to_csv(backup_path, index=False)
    print(f"💾 Backup creado: {backup_path}")
    
    # Filtrar registros a enviar
    registros_a_enviar = []
    for idx, fila in df.iterrows():
        # Solo enviar si tiene opt_in=TRUE (si existe la columna)
        if 'opt_in' in df.columns:
            opt_in = str(fila.get('opt_in', '')).strip().upper()
            if opt_in not in ('TRUE', '1', 'YES', 'SI', 'SÍ'):
                continue
        
        # No reenviar si ya se envió antes (verificar que realmente tenga el valor 'sent')
        estado = str(fila.get('estado_envio_simple', '')).strip().lower()
        if estado == 'sent':
            continue
        
        registros_a_enviar.append((idx, fila))
    
    if not registros_a_enviar:
        print("\nℹ️  No hay registros nuevos para enviar.")
        if 'opt_in' in df.columns:
            print("   Verifica que haya registros con opt_in=TRUE")
        print("   y que no hayan sido enviados anteriormente.\n")
        return
    
    print(f"\n📤 Registros a enviar: {len(registros_a_enviar)}")
    print("-" * 70)
    
    # Confirmar antes de enviar
    respuesta = input("\n¿Deseas continuar con el envío? (si/no): ").strip().lower()
    if respuesta not in ('si', 'sí', 's', 'yes', 'y'):
        print("\n❌ Envío cancelado por el usuario.\n")
        return
    
    print("\n🚀 Iniciando envío...\n")
    
    # Enviar mensajes
    enviados = 0
    errores = 0
    
    for idx, fila in registros_a_enviar:
        telefono = fila['telefono_e164']
        nombre = fila.get('nombre', 'Usuario')
        
        print(f"📞 {nombre} ({telefono})... ", end='', flush=True)
        
        success, result = enviar_mensaje_texto(telefono, MENSAJE)
        
        if success:
            df.at[idx, 'estado_envio_simple'] = 'sent'
            df.at[idx, 'fecha_envio_simple'] = datetime.now().isoformat()
            df.at[idx, 'message_id_simple'] = result
            print(f"✅ Enviado (ID: {result[:20]}...)")
            enviados += 1
        else:
            df.at[idx, 'estado_envio_simple'] = 'error'
            df.at[idx, 'fecha_envio_simple'] = datetime.now().isoformat()
            print(f"❌ Error: {result}")
            errores += 1
        
        # Pausa entre mensajes
        if idx < len(registros_a_enviar) - 1:
            time.sleep(DELAY_SEGUNDOS)
    
    # Guardar cambios
    df.to_csv(CSV_PATH, index=False)
    
    # Resumen
    print("\n" + "-" * 70)
    print("📊 RESUMEN DEL ENVÍO")
    print("-" * 70)
    print(f"✅ Enviados exitosamente: {enviados}")
    print(f"❌ Errores: {errores}")
    print(f"💾 CSV actualizado: {CSV_PATH}")
    print("="*70 + "\n")


if __name__ == '__main__':
    main()
