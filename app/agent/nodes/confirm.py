import logging
from langchain_core.messages import AIMessage
from app.agent.state import AgentState

logger = logging.getLogger(__name__)

def confirm_response_node(state: AgentState):
    """Procesa respuestas de confirmación (Sí/No) y guarda en BD."""
    from datetime import datetime
    from app import db_handler
    
    phone = state.get('phone')
    data = state.get('student_data')
    name = state.get('student_name', 'Estudiante')
    
    # Obtener el mensaje original
    messages = state.get('messages', [])
    if not messages:
        return {"messages": [AIMessage(content="No recibí tu mensaje.")]}
    
    # Manejar tanto objetos LangChain como diccionarios
    last_message = messages[-1]
    if hasattr(last_message, 'content'):
        text = last_message.content.strip().lower()
    elif isinstance(last_message, dict):
        text = last_message.get('content', '').strip().lower()
    else:
        text = str(last_message).strip().lower()
    
    logger.info(f"[AGENT] Procesando confirmación: '{text}' de {phone}")
    
    # Detectar respuesta
    si_patterns = ['sí', 'si', 'yes', 'acepto', 'confirmo', 'ok', 'dale', 'claro', 'listo']
    no_patterns = ['no', 'rechazo', 'cancelar', 'cancela', 'rechazar']
    
    respuesta = None
    if any(p in text for p in si_patterns):
        respuesta = 'Sí'
    elif any(p in text for p in no_patterns):
        respuesta = 'No'
    
    if not respuesta:
        msg = "Solamente puedes responder *SÍ* o *NO* para confirmar tu matrícula."
        return {"messages": [AIMessage(content=msg)]}
    
    # Verificar registro existe
    if not data:
        msg = "No encontré tu registro. 🧐 ¿Te inscribiste con este número?"
        return {"messages": [AIMessage(content=msg)]}
    
    # Verificar si ya respondió (doble validación por seguridad)
    respuesta_actual = data.get('respuesta', '')
    if respuesta_actual and respuesta_actual.strip() != '' and respuesta_actual.strip().lower() != 'default':
        msg = f"Ya registramos tu respuesta anterior: *{respuesta_actual}*. Si necesitas cambiarla, contacta a soporte."
        return {"messages": [AIMessage(content=msg)]}
    
    # Guardar respuesta
    try:
        fecha = datetime.now().isoformat()
        success, message = db_handler.update_respuesta(phone, respuesta, fecha)
        
        bootcamp = data.get('bootcamp_nombre', 'el bootcamp') if data else 'el bootcamp'
        inicio = data.get('inicio_formacion', '') if data else ''
        
        if success:
            if respuesta == 'Sí':
                msg = (
                    f"🎉 ¡Excelente {name}!\n\n"
                    f"Tu cupo en *{bootcamp}* ha sido confirmado.\n\n"
                    f"📅 *Inicio de clases:* {inicio}\n\n"
                    "Pronto recibirás más información sobre el acceso a la plataforma y materiales.\n\n"
                    "¡Nos vemos en clase! 🚀"
                )
            else:
                msg = (
                    f"Entendido {name}, hemos registrado que no podrás participar en esta ocasión. 📝\n\n"
                    "Si cambias de opinión o tienes alguna duda, no dudes en escribirnos.\n\n"
                    "¡Te esperamos en una próxima convocatoria! 👋"
                )
            logger.info(f"[AGENT] Respuesta '{respuesta}' guardada para {phone}")
        else:
            msg = (
                "Ups, tuvimos un problema al registrar tu respuesta. 😕\n\n"
                "Por favor, intenta de nuevo en unos minutos. Si el problema persiste, "
                "escríbenos a soporte@talentotech.gov.co"
            )
            logger.error(f"[AGENT] Error guardando respuesta: {message}")
            
    except Exception as e:
        logger.error(f"[AGENT] Excepción guardando respuesta: {e}")
        msg = (
            "Lo siento, ocurrió un error inesperado. 😕\n\n"
            "Nuestro equipo técnico ya fue notificado. Por favor intenta más tarde."
        )
    
    return {"messages": [AIMessage(content=msg)]}