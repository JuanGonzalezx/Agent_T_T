"""
Nodo de confirmación de asistencia a eventos.

Procesa respuestas de tipo "Asisto" / "No Asisto" para campañas de EVENTO.
Actualiza campana_miembros sin tocar la tabla estudiantes.
"""

import logging
from langchain_core.messages import AIMessage
from app.agent.state import AgentState

logger = logging.getLogger(__name__)


def confirm_event_node(state: AgentState):
    """
    Procesa respuestas de asistencia a eventos y guarda en campana_miembros.
    
    A diferencia de confirm_response_node (matrícula), este nodo:
    - Detecta "Asisto" / "No Asisto" (botones o texto libre)
    - Actualiza SOLO campana_miembros (NO toca tabla estudiantes)
    - Preserva el estado académico del estudiante intacto
    """
    from app import db_handler
    
    phone = state.get('phone')
    name = state.get('student_name', 'Estudiante')
    active_campaign = state.get('active_campaign')
    
    # Obtener el mensaje original
    messages = state.get('messages', [])
    if not messages:
        return {"messages": [AIMessage(content="No recibí tu mensaje.")]}
    
    last_message = messages[-1]
    if hasattr(last_message, 'content'):
        text = last_message.content.strip()
    elif isinstance(last_message, dict):
        text = last_message.get('content', '').strip()
    else:
        text = str(last_message).strip()
    
    text_lower = text.lower()
    
    logger.info(f"[EVENT] Procesando respuesta evento: '{text}' de {phone}")
    
    # Validar que hay campaña activa
    if not active_campaign:
        msg = (
            "No encontré una invitación activa para ti. 🤔\n\n"
            "Si recibiste una invitación, puede que ya hayas respondido.\n"
            "¿Necesitas algo más? Escribe *estado* para ver tu información."
        )
        return {"messages": [AIMessage(content=msg)]}
    
    campana_nombre = active_campaign.get('campana_nombre', 'el evento')
    miembro_id = active_campaign.get('miembro_id')
    
    # Verificar si ya respondió (doble validación)
    respuesta_existente = active_campaign.get('respuesta_usuario', '')
    if respuesta_existente and respuesta_existente.strip():
        msg = (
            f"Ya registramos tu respuesta anterior: *{respuesta_existente}*.\n\n"
            "Si necesitas cambiarla, contacta a soporte@talentotech.gov.co"
        )
        return {"messages": [AIMessage(content=msg)]}
    
    # Detectar respuesta: "Asisto" / "No Asisto" (botones o texto libre)
    asiste_patterns = ['asisto', 'asistiré', 'asistire', 'voy', 'iré', 'ire', 
                       'confirmo', 'sí', 'si', 'yes', 'claro', 'dale', 'ok',
                       'acepto', 'ahí estaré', 'ahi estare', 'cuenten conmigo']
    no_asiste_patterns = ['no asisto', 'no asistiré', 'no asistire', 'no voy', 'no iré', 
                          'no ire', 'no puedo', 'no', 'rechazo', 'cancelar', 'paso',
                          'no podré', 'no podre', 'imposible']
    
    respuesta = None
    # Primero verificar los patrones negativos (más específicos)
    if any(p in text_lower for p in no_asiste_patterns):
        respuesta = 'NO_ASISTE'
    elif any(p in text_lower for p in asiste_patterns):
        respuesta = 'ASISTE'
    
    if not respuesta:
        msg = (
            f"Para confirmar tu asistencia a *{campana_nombre}*, "
            "responde *Asisto* o *No Asisto*.\n\n"
            "También puedes usar los botones de abajo 👇"
        )
        return {"messages": [AIMessage(content=msg)]}
    
    # Guardar respuesta en campana_miembros
    try:
        if miembro_id:
            miembro_id_int = int(miembro_id)
            success, message = db_handler.update_miembro_respuesta(
                miembro_id_int, respuesta, text
            )
        else:
            success = False
            message = "No se encontró el registro de campaña"
        
        if success:
            if respuesta == 'ASISTE':
                msg = (
                    f"🎉 ¡Excelente {name}!\n\n"
                    f"Tu asistencia a *{campana_nombre}* ha sido confirmada. ✅\n\n"
                    "¡Te esperamos! No olvides llegar puntual. 🕐"
                )
            else:
                msg = (
                    f"Entendido {name}, hemos registrado que no podrás asistir "
                    f"a *{campana_nombre}*. 📝\n\n"
                    "Si cambias de opinión, contáctanos a soporte@talentotech.gov.co\n\n"
                    "¡Esperamos verte en un próximo evento! 👋"
                )
            logger.info(f"[EVENT] Respuesta '{respuesta}' guardada para miembro {miembro_id}")
        else:
            msg = (
                "Ups, tuvimos un problema al registrar tu respuesta. 😕\n\n"
                "Por favor, intenta de nuevo en unos minutos. Si el problema persiste, "
                "escríbenos a soporte@talentotech.gov.co"
            )
            logger.error(f"[EVENT] Error guardando respuesta evento: {message}")
            
    except Exception as e:
        logger.error(f"[EVENT] Excepción guardando respuesta evento: {e}")
        msg = (
            "Lo siento, ocurrió un error inesperado. 😕\n\n"
            "Nuestro equipo técnico ya fue notificado. Por favor intenta más tarde."
        )
    
    return {"messages": [AIMessage(content=msg)]}
