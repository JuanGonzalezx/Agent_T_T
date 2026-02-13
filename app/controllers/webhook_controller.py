import os
from flask import Blueprint, request, jsonify, current_app
from app import logic_brain  # Tu cerebro RegEx (Instancia Global)
from app.agent.graph import get_agent # Tu cerebro Gemini

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
                    from_number = message.get('from')
                    
                    # Extraer texto (soporte simple para texto y botones)
                    text_body = ""
                    if message['type'] == 'text':
                        text_body = message['text']['body']
                    elif message['type'] == 'button':
                        text_body = message['button']['text']
                    
                    if from_number and text_body:
                        # INVOCAR LANGGRAPH
                        agent = get_agent()
                        inputs = {
                            "messages": [{"role": "user", "content": text_body}],
                            "phone": from_number
                        }
                        
                        # Ejecutar grafo
                        result = agent.invoke(inputs)
                        
                        # Obtener la última respuesta del bot
                        bot_response = result['messages'][-1].content
                        
                        # Enviar respuesta por WhatsApp
                        from app import whatsapp_service
                        whatsapp_service.send_text_message(from_number, bot_response)
                
                return jsonify({'status': 'processed_by_ai'}), 200
            
            else:
                # === MODO 2: MVP CLÁSICO (REGEX SÍ/NO) ===
                # Este método ya maneja la extracción, lógica y envío internamente
                if logic_brain:
                    logic_brain.process_webhook_event(body)
                return jsonify({'status': 'processed_by_regex'}), 200

        except Exception as e:
            current_app.logger.error(f"[WEBHOOK] Excepción: {str(e)}")
            return jsonify({'status': 'error'}), 500