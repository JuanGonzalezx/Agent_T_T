import os
import threading
import logging
import time
from flask import Blueprint, request, jsonify
from app import logic_brain
from app.agent.graph import get_agent
from app.utils.message_dedup import get_deduplicator

webhook_bp = Blueprint('webhook', __name__)
logger = logging.getLogger(__name__)

def process_message_background(from_number: str, text_body: str, message_id: str):
    """Procesa el mensaje en un hilo aparte para no bloquear el webhook."""
    try:
        from langchain_core.messages import HumanMessage
        from app import whatsapp_service
        
        # LOGICA IA
        agent = get_agent()
        inputs = {
            "messages": [HumanMessage(content=text_body)],
            "phone": from_number
        }
        
        # Ejecutar grafo
        result = agent.invoke(inputs)
        
        # Extraer respuesta
        if result and 'messages' in result and result['messages']:
            bot_response = result['messages'][-1].content
            whatsapp_service.send_text_message(from_number, bot_response)
            logger.info(f"[BG] ✅ Respuesta enviada a {from_number}")
        else:
            logger.warning(f"[BG] ⚠️ El agente no generó respuesta para {message_id}")

    except Exception as e:
        logger.error(f"[BG] ❌ Error CRÍTICO procesando mensaje {message_id}: {e}", exc_info=True)

@webhook_bp.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # --- GET: Verificación ---
    if request.method == 'GET':
        verify_token = os.getenv('VERIFY_TOKEN')
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode == 'subscribe' and token == verify_token:
            return challenge, 200
        return 'Forbidden', 403

    # --- POST: Mensajes ---
    try:
        body = request.get_json(silent=True) or {}
        entries = body.get('entry', [])
        
        if not entries:
            return jsonify({'status': 'ok'}), 200

        changes = entries[0].get('changes', [])
        if not changes:
            return jsonify({'status': 'ok'}), 200

        value = changes[0].get('value', {})
        
        # 1. IGNORAR STATUSES (Sent/Delivered/Read)
        if 'statuses' in value:
            return jsonify({'status': 'ignored'}), 200

        messages = value.get('messages', [])
        if not messages:
            return jsonify({'status': 'ignored'}), 200

        message = messages[0]
        msg_id = message.get('id')
        from_number = message.get('from')
        
        # 2. VALIDAR DATOS MÍNIMOS
        if not msg_id or not from_number:
            return jsonify({'status': 'invalid'}), 200

        # 3. FILTRO DE TIEMPO (Evitar procesar mensajes muy viejos que Meta reintente)
        msg_timestamp = int(message.get('timestamp', time.time()))
        if time.time() - msg_timestamp > 300: # Más de 5 minutos de antigüedad
             logger.warning(f"[WH] ⏳ Mensaje descartado por viejo: {msg_id}")
             return jsonify({'status': 'expired'}), 200

        # 4. DEDUPLICACIÓN ATÓMICA EN RAM
        dedup = get_deduplicator()
        if dedup.check_and_mark(msg_id):
            logger.info(f"[WH] ♻️ Duplicado detectado y detenido: {msg_id}")
            return jsonify({'status': 'duplicate'}), 200

        # 5. EXTRAER TEXTO (Soporte Text y Button Reply)
        msg_type = message.get('type')
        text_body = ""
        
        if msg_type == 'text':
            text_body = message.get('text', {}).get('body', '')
        elif msg_type == 'interactive':
            int_type = message.get('interactive', {}).get('type')
            if int_type == 'button_reply':
                text_body = message.get('interactive', {}).get('button_reply', {}).get('title', '')
            elif int_type == 'list_reply':
                text_body = message.get('interactive', {}).get('list_reply', {}).get('title', '')
        elif msg_type == 'button': # Legacy templates
             text_body = message.get('button', {}).get('text', '')

        if not text_body:
            return jsonify({'status': 'no_text'}), 200

        # 6. LANZAR PROCESAMIENTO (Fire & Forget)
        use_ai = os.getenv('USE_AI_AGENT', 'False').lower() == 'true'
        
        if use_ai:
            threading.Thread(
                target=process_message_background, 
                args=(from_number, text_body, msg_id),
                daemon=True
            ).start()
        else:
            # Fallback legacy
            if logic_brain:
                logic_brain.process_webhook_event(body)

        return jsonify({'status': 'received'}), 200

    except Exception as e:
        logger.error(f"[WH] Error general en webhook: {e}")
        # Siempre responder 200 a Meta para que deje de reintentar si fallamos nosotros
        return jsonify({'status': 'error_handled'}), 200