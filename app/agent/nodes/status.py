import logging
from langchain_core.messages import AIMessage
from app.agent.state import AgentState

logger = logging.getLogger(__name__)

def check_status_node(state: AgentState):
    """Revisa el estado de la matrícula basándose en el campo 'respuesta'."""
    data = state.get('student_data')
    name = state.get('student_name', 'Estudiante')
    
    # 1. Validación rápida si no hay datos
    if not data:
        msg = (
            f"Hola {name}, no encontré ningún registro asociado a este número. 🤔\n\n"
            "¿Ya te inscribiste al programa? Si crees que es un error, "
            "escríbenos a soporte@talentotech.gov.co"
        )
        return {"messages": [AIMessage(content=msg)]}

    # 2. Extraer contexto de la Base de Datos
    respuesta_raw = str(data.get('respuesta', 'default')).strip().lower()
    bootcamp = data.get('bootcamp_nombre', 'tu bootcamp')
    modalidad = data.get('modalidad', 'No especificada')
    inicio = data.get('inicio_formacion', 'Pronto')
    
    logger.info(f"[STATUS NODO] Consultando estado para {name} (Respuesta BD: '{respuesta_raw}')")
    
    # 3. Determinar estado basado en el campo 'respuesta' (NO estado_envio)
    if respuesta_raw in ['sí', 'si', 'yes']:
        # El estudiante ya confirmó su cupo
        msg = (
            f"🎉 ¡Hola {name}!\n\n"
            f"Tu cupo en *{bootcamp}* ({modalidad}) está *CONFIRMADO*.\n\n"
            f"📅 *Inicio de clases:* {inicio}\n\n"
            "Pronto recibirás información sobre acceso a la plataforma. ¡Nos vemos! 🚀"
        )
    elif respuesta_raw == 'no':
        # El estudiante rechazó el cupo
        msg = (
            f"Hola {name},\n\n"
            f"Según nuestros registros, indicaste que no participarás en *{bootcamp}*.\n\n"
            "Si esto fue un error o cambiaste de opinión, contáctanos a soporte@talentotech.gov.co\n\n"
            "¡Te esperamos en una próxima convocatoria! 👋"
        )
    else:
        # respuesta_raw == 'default' o vacío: Pendiente de confirmación
        msg = (
            f"Hola {name} 👋\n\n"
            f"Estás registrado/a en *{bootcamp}* ({modalidad}).\n\n"
            f"📅 *Inicio:* {inicio}\n\n"
            "⚠️ *Aún no has confirmado tu cupo.* Responde *SÍ* para confirmar o *NO* si no podrás asistir."
        )
    
    return {"messages": [AIMessage(content=msg)]}