import os
from flask import Blueprint, request, jsonify, current_app

webhook_bp = Blueprint('webhook', __name__)

@webhook_bp.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """Webhook para recibir notificaciones de WhatsApp."""
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

    elif request.method == 'POST':
        try:
            body = request.get_json()
            # Importación diferida para evitar import circular
            from app import logic_brain
            # Delegar procesamiento al cerebro lógico
            if logic_brain:
                logic_brain.process_webhook_event(body)
            return jsonify({'status': 'ok'}), 200
        except Exception as e:
            current_app.logger.error(f"[WEBHOOK] Excepción: {str(e)}")
            return jsonify({'status': 'error'}), 200
