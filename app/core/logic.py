import re
from datetime import datetime

class ResponseLogic:
    def __init__(self, db_handler, whatsapp_service):
        self.db = db_handler
        self.wpp = whatsapp_service

    def process_webhook_event(self, data):
        # Extraer mensaje (Lógica simplificada para el ejemplo)
        try:
            entry = data.get('entry', [])[0]
            changes = entry.get('changes', [])[0]
            value = changes.get('value', {})
            messages = value.get('messages', [])
            
            if not messages: return

            message = messages[0]
            phone = message.get('from', '')
            msg_type = message.get('type')
            
            text = ""
            if msg_type == 'text':
                text = message['text']['body']
            elif msg_type == 'button':
                text = message['button']['text']
            elif msg_type == 'interactive':
                # Manejo simple de botones interactivos
                text = message['interactive']['button_reply']['title']

            if phone and text:
                self._handle_response(phone, text)
        except Exception as e:
            print(f"Error procesando webhook: {e}")

    def _handle_response(self, phone, text):
        msg = text.strip().lower()
        
        # Verificar si ya respondió
        ya_respondio, _ = self.db.get_respuesta_existente(phone)
        if ya_respondio: return

        # Lógica Sí/No
        if re.search(r'\b(si|sí|yes|confirmar|acepto)\b', msg):
            self.db.update_respuesta(phone, "Si", datetime.now().isoformat())
            self.wpp.send_text_message(phone, "¡Gracias por confirmar! 🎉\nTe enviaremos los detalles pronto.")
        elif re.search(r'\b(no|rechazar|cancelar)\b', msg):
            self.db.update_respuesta(phone, "No", datetime.now().isoformat())
            self.wpp.send_text_message(phone, "Entendido. Gracias por avisarnos.")
        else:
            self.wpp.send_text_message(phone, "Por favor responde solo SÍ o NO.")