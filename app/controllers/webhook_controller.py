import os
import threading
import logging
from flask import Blueprint, request, jsonify, current_app
from app import logic_brain
from app.agent.graph import get_agent
from app.utils.message_dedup import get_deduplicator

webhook_bp = Blueprint('webhook', __name__)
logger = logging.getLogger(__name__)


def extract_message_data(body: dict) -> dict | None:
    """
    Extrae datos del mensaje de forma segura.
    Retorna None si no es un mensaje válido para procesar.
    """
    try:
        entries = body.get('entry', [])
        if not entries:
            return None
        
        changes = entries[0].get('changes', [])
        if not changes:
            return None
        
        value = changes[0].get('value', {})
        
        # ══════════════════════════════════════════════════════════════
        # 🛡️ FILTRO CRÍTICO: Ignorar STATUSES (sent/delivered/read)
        # Estos eventos NO son mensajes del usuario, son confirmaciones.
        # ══════════════════════════════════════════════════════════════
        if 'statuses' in value:
            return None  # NO procesar
        
        messages = value.get('messages', [])
        if not messages:
            return None
        
        message = messages[0]
        message_id = message.get('id', '')
        from_number = message.get('from', '')
        msg_type = message.get('type', '')
        
        if not message_id or not from_number:
            return None
        
        # Extraer texto según el tipo de mensaje
        text_body = ""
        if msg_type == 'text':
            text_body = message.get('text', {}).get('body', '')
        elif msg_type == 'button':
            text_body = message.get('button', {}).get('text', '')
        elif msg_type == 'interactive':
            interactive = message.get('interactive', {})
            int_type = interactive.get('type', '')
            if int_type == 'button_reply':
                text_body = interactive.get('button_reply', {}).get('title', '')
            elif int_type == 'list_reply':
                text_body = interactive.get('list_reply', {}).get('title', '')
        
        if not text_body.strip():
            return None
        
        return {
            'message_id': message_id,
            'from_number': from_number,
            'text': text_body.strip(),
            'type': msg_type
        }
    
    except Exception as e:
        logger.warning(f"[EXTRACT] Error extrayendo mensaje: {e}")
        return None


def process_message_background(from_number: str, text_body: str, message_id: str):
    """
    Procesa el mensaje en background. Esta función corre en un thread separado.
    """
    try:
        from langchain_core.messages import HumanMessage
        from app import whatsapp_service
        
        agent = get_agent()
        inputs = {
            "messages": [HumanMessage(content=text_body)],
            "phone": from_number
        }
        
        result = agent.invoke(inputs)
        bot_response = result['messages'][-1].content
        whatsapp_service.send_text_message(from_number, bot_response)
        
        logger.info(f"[BG] ✅ Respuesta enviada a {from_number}")
        
    except Exception as e:
        logger.error(f"[BG] ❌ Error procesando {message_id[:15]}: {e}")


@webhook_bp.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """
    Endpoint optimizado para WhatsApp Cloud API.
    
    BLINDAJE IMPLEMENTADO:
    1. Filtrado de statuses (sent/delivered/read) 
    2. Deduplicación atómica antes de cualquier procesamiento
    3. Respuesta 200 ultra-rápida
    4. Procesamiento en background thread
    """
    
    # ══════════════════════════════════════════════════════════════
    # GET: Verificación del webhook (handshake con Meta)
    # ══════════════════════════════════════════════════════════════
    if request.method == 'GET':
        verify_token = os.getenv('VERIFY_TOKEN', 'mi_token_secreto')
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')

        if mode == 'subscribe' and token == verify_token:
            logger.info('[WEBHOOK] ✅ Verificación OK')
            return challenge, 200
        
        logger.warning('[WEBHOOK] ❌ Verificación FAIL')
        return 'Forbidden', 403

    # ══════════════════════════════════════════════════════════════
    # POST: Recepción de eventos
    # ══════════════════════════════════════════════════════════════
    
    # 🚀 PASO 1: Parsear JSON (mínimo procesamiento)
    try:
        body = request.get_json(silent=True) or {}
    except Exception:
        return jsonify({'status': 'invalid_json'}), 200
    
    # 🚀 PASO 2: Validación básica - sin entry = ignorar
    if not body.get('entry'):
        return jsonify({'status': 'no_entry'}), 200
    
    # 🚀 PASO 3: Extraer datos del mensaje (incluye filtro de statuses)
    msg_data = extract_message_data(body)
    
    if msg_data is None:
        # Es un status (sent/delivered/read) o no tiene mensaje válido
        # Retornar 200 inmediatamente sin loggear nada pesado
        return jsonify({'status': 'ignored'}), 200
    
    message_id = msg_data['message_id']
    from_number = msg_data['from_number']
    text_body = msg_data['text']
    
    # 🚀 PASO 4: DEDUPLICACIÓN ATÓMICA (antes de cualquier cosa)
    dedup = get_deduplicator()
    if dedup.check_and_mark(message_id):
        # Ya se procesó o se está procesando
        logger.debug(f"[DEDUP] ⏭️ Duplicado: {message_id[:20]}")
        return jsonify({'status': 'duplicate'}), 200
    
    # 🚀 PASO 5: Log mínimo del mensaje recibido
    logger.info(f"[WH] 📩 '{text_body[:30]}' de {from_number[-4:]}")
    
    # 🚀 PASO 6: Determinar modo de procesamiento
    use_ai = os.getenv('USE_AI_AGENT', 'False').lower() == 'true'
    
    if use_ai:
        # ══════════════════════════════════════════════════════════
        # MODO IA: Procesar con Gemini en background
        # ══════════════════════════════════════════════════════════
        thread = threading.Thread(
            target=process_message_background,
            args=(from_number, text_body, message_id),
            daemon=True
        )
        thread.start()
        
        # 🚀 RESPUESTA INMEDIATA (antes de que Gemini termine)
        return jsonify({'status': 'accepted'}), 200
    
    else:
        # ══════════════════════════════════════════════════════════
        # MODO REGEX: Procesamiento síncrono (legacy)
        # ══════════════════════════════════════════════════════════
        if logic_brain:
            logic_brain.process_webhook_event(body)
        return jsonify({'status': 'processed'}), 200