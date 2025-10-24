"""
Webhook Flask para recibir respuestas de WhatsApp Cloud API.

Este servidor:
1. Verifica el webhook con Meta/Facebook (GET)
2. Recibe notificaciones cuando usuarios responden (POST)
3. Actualiza bd_envio.csv con la respuesta y fecha

Debe estar corriendo constantemente para recibir respuestas.
"""
import os
import json
from datetime import datetime
from flask import Flask, request, jsonify
import pandas as pd
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración
CSV_PATH = os.getenv('CSV_PATH', 'bd_envio.csv')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', 'mi_token_secreto_12345')
PORT = int(os.getenv('PORT', 5000))

app = Flask(__name__)


def normalizar_telefono_busqueda(telefono):
    """Normaliza teléfono para búsqueda (remueve + y espacios)."""
    if not telefono:
        return ''
    return str(telefono).replace('+', '').replace(' ', '').replace('-', '').strip()


def buscar_telefono_en_csv(wa_id):
    """
    Busca el teléfono en el CSV.
    wa_id viene sin el '+' desde WhatsApp (ej: 573154963483)
    """
    try:
        df = pd.read_csv(CSV_PATH, dtype=str)
        
        # Normalizar columna de teléfonos
        df['telefono_normalizado'] = df['telefono_e164'].apply(normalizar_telefono_busqueda)
        
        # Buscar coincidencia
        wa_id_normalizado = normalizar_telefono_busqueda(wa_id)
        mascara = df['telefono_normalizado'] == wa_id_normalizado
        
        if mascara.any():
            return df, mascara
        else:
            return df, None
    except Exception as e:
        print(f"❌ Error al leer CSV: {e}")
        return None, None


def actualizar_respuesta_en_csv(wa_id, respuesta_texto, respuesta_id):
    """Actualiza el CSV con la respuesta del usuario."""
    df, mascara = buscar_telefono_en_csv(wa_id)
    
    if df is None:
        print(f"⚠️  No se pudo leer el CSV")
        return False
    
    if mascara is None:
        print(f"⚠️  Teléfono {wa_id} no encontrado en CSV")
        return False
    
    # Crear columnas si no existen
    if 'respuesta' not in df.columns:
        df['respuesta'] = ''
    if 'fecha_respuesta' not in df.columns:
        df['fecha_respuesta'] = ''
    if 'respuesta_id' not in df.columns:
        df['respuesta_id'] = ''
    
    # Actualizar la fila que coincide
    df.loc[mascara, 'respuesta'] = respuesta_texto
    df.loc[mascara, 'fecha_respuesta'] = datetime.now().isoformat()
    df.loc[mascara, 'respuesta_id'] = respuesta_id
    
    # Guardar CSV
    try:
        # Eliminar columna temporal de normalización
        if 'telefono_normalizado' in df.columns:
            df = df.drop(columns=['telefono_normalizado'])
        
        df.to_csv(CSV_PATH, index=False)
        print(f"✅ CSV actualizado con respuesta de {wa_id}: {respuesta_texto}")
        return True
    except Exception as e:
        print(f"❌ Error al guardar CSV: {e}")
        return False


@app.route('/')
def home():
    """Página de inicio para verificar que el webhook está activo."""
    return """
    <h1>🤖 Webhook WhatsApp activo</h1>
    <p>Este servidor está escuchando respuestas de WhatsApp.</p>
    <p>Endpoint: <code>/webhook</code></p>
    """, 200


@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """
    Verificación del webhook (GET).
    Meta/Facebook llama a este endpoint para verificar el webhook.
    """
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    print(f"🔐 Verificación de webhook solicitada...")
    print(f"   Mode: {mode}")
    print(f"   Token recibido: {token}")
    
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        print("✅ Webhook verificado correctamente")
        return challenge, 200
    else:
        print("❌ Verificación fallida: token incorrecto")
        return 'Forbidden', 403


@app.route('/webhook', methods=['POST'])
def webhook_post():
    """
    Recibe notificaciones de WhatsApp (POST).
    Procesa mensajes de respuesta de botones.
    """
    try:
        data = request.get_json()
        
        # Log del payload completo (útil para debugging)
        print("\n" + "="*60)
        print("📨 Webhook recibido:")
        print(json.dumps(data, indent=2))
        print("="*60)
        
        # Estructura de WhatsApp Cloud API:
        # data -> entry[] -> changes[] -> value -> messages[]
        if 'entry' not in data:
            print("⚠️  No hay campo 'entry' en el webhook")
            return 'OK', 200
        
        for entry in data['entry']:
            changes = entry.get('changes', [])
            
            for change in changes:
                value = change.get('value', {})
                messages = value.get('messages', [])
                
                for message in messages:
                    procesar_mensaje(message)
        
        return 'OK', 200
    
    except Exception as e:
        print(f"❌ Error procesando webhook: {e}")
        return 'Error', 500


def procesar_mensaje(message):
    """Procesa un mensaje individual del webhook."""
    # Extraer información básica
    wa_id = message.get('from', '')  # Teléfono del remitente (sin +)
    message_type = message.get('type', '')
    timestamp = message.get('timestamp', '')
    
    print(f"\n📱 Mensaje de: {wa_id}")
    print(f"   Tipo: {message_type}")
    
    respuesta_texto = None
    respuesta_id = None
    
    # Procesar según el tipo de mensaje
    if message_type == 'interactive':
        # Respuesta a botón interactivo
        interactive = message.get('interactive', {})
        button_reply = interactive.get('button_reply', {})
        
        respuesta_id = button_reply.get('id', '')  # "btn_si" o "btn_no"
        respuesta_texto = button_reply.get('title', '')  # "Sí confirmo ✅" o "No puedo ❌"
        
        print(f"   🔘 Botón presionado: {respuesta_texto} (ID: {respuesta_id})")
    
    elif message_type == 'text':
        # Respuesta de texto libre (por si el usuario escribe en vez de usar botones)
        text_body = message.get('text', {}).get('body', '')
        respuesta_texto = text_body
        respuesta_id = 'text_libre'
        
        print(f"   💬 Texto recibido: {text_body}")
    
    else:
        print(f"   ℹ️  Tipo de mensaje no procesado: {message_type}")
        return
    
    # Actualizar CSV si tenemos una respuesta
    if respuesta_texto:
        actualizar_respuesta_en_csv(wa_id, respuesta_texto, respuesta_id)
    else:
        print("   ⚠️  No se pudo extraer respuesta del mensaje")


@app.route('/status')
def status():
    """Endpoint para verificar el estado del webhook."""
    try:
        df = pd.read_csv(CSV_PATH, dtype=str)
        total = len(df)
        
        # Contar respuestas
        if 'respuesta' in df.columns:
            con_respuesta = df['respuesta'].notna().sum()
        else:
            con_respuesta = 0
        
        return jsonify({
            'status': 'active',
            'csv_path': CSV_PATH,
            'total_registros': total,
            'con_respuesta': int(con_respuesta),
            'sin_respuesta': total - int(con_respuesta)
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 WEBHOOK WHATSAPP - SERVIDOR FLASK")
    print("="*60)
    print(f"📂 CSV: {CSV_PATH}")
    print(f"🔐 Verify Token: {VERIFY_TOKEN}")
    print(f"🌐 Puerto: {PORT}")
    print()
    print("⚠️  IMPORTANTE: Debes exponer este servidor con ngrok o similar")
    print("   para que WhatsApp pueda enviar notificaciones.")
    print()
    print("   Comando: ngrok http " + str(PORT))
    print("="*60)
    print()
    
    app.run(host='0.0.0.0', port=PORT, debug=True)
