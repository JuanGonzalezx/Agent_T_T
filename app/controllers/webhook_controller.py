import os
import threading
from flask import Blueprint, request, jsonify, current_app
from app import logic_brain  # Tu cerebro RegEx (Instancia Global)
from app.agent.graph import get_agent # Tu cerebro Gemini
from app.utils.message_dedup import get_deduplicator

webhook_bp = Blueprint('webhook', __name__)

@webhook_bp.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """Endpoint único que recibe eventos de Meta."""
    
    # 1. Verificación del Token (Handshake con Meta)
    if request.method == 'GET':
        verify_token = os.getenv('VERIFY_TOKEN', 'mi_token_secreto')
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')

        if mode == 'subscribe' and token == verify_token:
            current_app.logger.info('[WEBHOOK] Verificación - OK')
            return challenge, 200
        else:
            current_app.logger.warning('[WEBHOOK] Verificación - FAIL')
            return 'Forbidden', 403

    # 2. Recepción de Mensajes (POST)
    elif request.method == 'POST':
        try:
            body = request.get_json() or {}
            
            # Validación rápida: si no hay 'entry', no es un mensaje real
            if not body.get('entry'):
                return jsonify({'status': 'ignored'}), 200
            
            # --- FEATURE FLAG: ¿Usamos IA o RegEx? ---
            use_ai = os.getenv('USE_AI_AGENT', 'False').lower() == 'true'
            
            if use_ai:
                # === MODO 1: INTELIGENCIA ARTIFICIAL (GEMINI) ===
                current_app.logger.info("🧠 [IA] Procesando con Gemini...")
                
                # Extraer datos básicos del JSON de Meta (con validación)
                entries = body.get('entry', [])
                if not entries:
                    return jsonify({'status': 'no_entry'}), 200
                    
                entry = entries[0]
                changes = entry.get('changes', [])
                if not changes:
                    return jsonify({'status': 'no_changes'}), 200
                    
                value = changes[0].get('value', {})
                messages = value.get('messages', [])
                
                if messages:
                    message = messages[0]
                    message_id = message.get('id', '')  # wamid de Meta
                    from_number = message.get('from')
                    
                    # === DEDUPLICACIÓN: Evitar procesar el mismo mensaje múltiples veces ===
                    dedup = get_deduplicator()
                    if dedup.check_and_mark(message_id):
                        current_app.logger.info(f"[DEDUP] ⏭️ Mensaje duplicado ignorado: {message_id[:20]}...")
                        return jsonify({'status': 'duplicate_ignored'}), 200
                    
                    # Extraer texto (soporte simple para texto y botones)
                    text_body = ""
                    if message['type'] == 'text':
                        text_body = message['text']['body']
                    elif message['type'] == 'button':
                        text_body = message['button']['text']
                    elif message['type'] == 'interactive':
                        interactive = message.get('interactive', {})
                        if interactive.get('type') == 'button_reply':
                            text_body = interactive['button_reply'].get('title', '')
                        elif interactive.get('type') == 'list_reply':
                            text_body = interactive['list_reply'].get('title', '')
                    
                    if from_number and text_body:
                        # Procesar en background thread para responder 200 rápido
                        def process_message():
                            try:
                                from langchain_core.messages import HumanMessage
                                from flask import current_app
                                from app import whatsapp_service
                                
                                agent = get_agent()
                                inputs = {
                                    "messages": [HumanMessage(content=text_body)],
                                    "phone": from_number
                                }
                                
                                result = agent.invoke(inputs)
                                bot_response = result['messages'][-1].content
                                whatsapp_service.send_text_message(from_number, bot_response)
                                
                            except Exception as e:
                                import logging
                                logging.getLogger(__name__).error(f"[WEBHOOK-BG] Error procesando: {e}")
                        
                        current_app.logger.info(f"🧠 [IA] Mensaje: '{text_body}' de {from_number} (id: {message_id[:15]}...)")
                        
                        # Lanzar procesamiento en background
                        thread = threading.Thread(target=process_message, daemon=True)
                        thread.start()
                
                return jsonify({'status': 'accepted'}), 200
            
            else:
                # === MODO 2: MVP CLÁSICO (REGEX SÍ/NO) ===
                # Este método ya maneja la extracción, lógica y envío internamente
                if logic_brain:
                    logic_brain.process_webhook_event(body)
                return jsonify({'status': 'processed_by_regex'}), 200

        except Exception as e:
            current_app.logger.error(f"[WEBHOOK] Excepción: {str(e)}")
            return jsonify({'status': 'error'}), 500