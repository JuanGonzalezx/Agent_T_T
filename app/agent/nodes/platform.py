from langchain_core.messages import AIMessage
from app.agent.state import AgentState

def platform_access_node(state: AgentState):
    """Maneja las dudas de acceso a la plataforma."""
    data = state.get('student_data')
    name = state.get('student_name', 'Estudiante')
    
    if not data:
        msg = (
            f"Hola {name}, para acceder a la plataforma primero debes estar inscrito. 📝\n\n"
            "Si ya te inscribiste y no apareces, escríbenos a soporte@talentotech.gov.co"
        )
    else:
        # Verificar si tiene acceso
        respuesta = str(data.get('respuesta', '')).lower().strip()
        confirmo = respuesta in ('sí', 'si', 'yes')
        opt_in = str(data.get('opt_in', '')).upper() == 'TRUE'
        matriculado = data.get('estado_envio') in ('matriculado', 'confirmado')
        
        if opt_in or confirmo or matriculado:
            msg = (
                f"¡Hola {name}! Aquí tienes los datos de acceso: 🔐\n\n"
                "🔗 *Plataforma:*\n"
                "https://talentotech2.com.co/campus/login/index.php\n\n"
                "👤 *Usuario:* Tu número de cédula\n"
                "🔑 *Contraseña:* Tu número de cédula\n\n"
                "💡 *Tip:* Si es tu primera vez, al ingresar te pedirá cambiar la contraseña.\n\n"
                "¿Tienes problemas para entrar? Escríbeme y te ayudo. 🙋"
            )
        else:
            msg = (
                f"Hola {name}, tu acceso a la plataforma aún no está habilitado. ⏳\n\n"
                "Esto puede ser porque:\n"
                "• Aún no has confirmado tu matrícula\n"
                "• Tu inscripción está en proceso de validación\n\n"
                "¿Ya recibiste el mensaje de confirmación? Responde *SÍ* para activar tu cupo."
            )
        
    return {"messages": [AIMessage(content=msg)]}