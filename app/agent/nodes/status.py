from langchain_core.messages import AIMessage
from app.agent.state import AgentState

def check_status_node(state: AgentState):
    """Revisa el estado de la matrícula."""
    data = state.get('student_data')
    name = state.get('student_name', 'Estudiante')
    
    if not data:
        msg = (
            f"Hola {name}, no encontré ningún registro asociado a este número. 🤔\n\n"
            "¿Ya te inscribiste al programa? Si crees que es un error, "
            "escríbenos a soporte@talentotech.gov.co"
        )
    else:
        estado = data.get('estado_envio', 'pendiente')
        bootcamp = data.get('bootcamp_nombre', 'tu bootcamp')
        modalidad = data.get('modalidad', '')
        inicio = data.get('inicio_formacion', '')
        
        # Estados más descriptivos y amigables
        if estado == 'sent':
            msg = (
                f"¡Hola {name}! 👋\n\n"
                f"Tu inscripción a *{bootcamp}* está registrada.\n\n"
                f"📋 *Estado:* Esperando tu confirmación\n"
                f"📚 *Modalidad:* {modalidad}\n"
                f"📅 *Inicio:* {inicio}\n\n"
                "Para confirmar tu cupo, responde *SÍ* a este chat."
            )
        elif estado == 'matriculado' or estado == 'confirmado':
            msg = (
                f"¡Felicidades {name}! 🎉\n\n"
                f"Ya estás oficialmente inscrito en *{bootcamp}*.\n\n"
                f"📅 *Inicio de clases:* {inicio}\n"
                f"📚 *Modalidad:* {modalidad}\n\n"
                "¡Nos vemos pronto en clase! 🚀"
            )
        elif estado == 'error':
            msg = (
                f"Hola {name}, parece que hubo un problema con tu notificación. 😕\n\n"
                "No te preocupes, nuestro equipo ya está al tanto. "
                "Te contactaremos pronto."
            )
        else:
            msg = (
                f"Hola {name}, tu registro en *{bootcamp}* está en proceso. ⏳\n\n"
                "Te notificaremos cuando tengamos novedades."
            )

    return {"messages": [AIMessage(content=msg)]}