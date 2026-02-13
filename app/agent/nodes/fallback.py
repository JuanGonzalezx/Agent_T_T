from langchain_core.messages import AIMessage
from app.agent.state import AgentState

def llm_fallback_node(state: AgentState):
    """Respuesta contextual para mensajes generales."""
    messages = state.get('messages', [])
    name = state.get('student_name') or ''
    student_data = state.get('student_data')
    
    # Personalizar saludo según si conocemos al estudiante
    saludo_name = f" {name}" if name and name != 'Estudiante' else ""
    
    # Obtener el mensaje del usuario
    if messages:
        last_message = messages[-1]
        if hasattr(last_message, 'content'):
            text = last_message.content.strip().lower()
        elif isinstance(last_message, dict):
            text = last_message.get('content', '').strip().lower()
        else:
            text = str(last_message).strip().lower()
    else:
        text = ""
    
    # Respuestas contextuales más naturales
    agradecimientos = ['gracias', 'vale', 'ok', 'listo', 'perfecto', 'genial', 'entendido', 'claro', 'super', 'excelente', 'bueno']
    saludos = ['hola', 'buenos días', 'buenas tardes', 'buenas noches', 'hey', 'hi', 'buenas', 'qué tal', 'como estas']
    despedidas = ['chao', 'adiós', 'bye', 'hasta luego', 'nos vemos', 'chau', 'adios']
    ayuda = ['ayuda', 'help', 'menu', 'menú', 'opciones', 'que puedes hacer', 'qué haces']
    
    if any(p in text for p in agradecimientos):
        msg = f"¡Con gusto{saludo_name}! 😊 Estoy aquí si necesitas algo más."
    elif any(p in text for p in saludos):
        if student_data:
            bootcamp = student_data.get('bootcamp_nombre', '')
            msg = (
                f"¡Hola{saludo_name}! 👋\n\n"
                f"Veo que estás inscrito en *{bootcamp}*.\n\n"
                "¿En qué puedo ayudarte hoy?\n\n"
                "📋 Escribe *estado* para ver tu matrícula\n"
                "🔑 Escribe *acceso* para datos de la plataforma"
            )
        else:
            msg = (
                f"¡Hola{saludo_name}! 👋 Soy el asistente virtual de *Talento Tech*.\n\n"
                "Puedo ayudarte con:\n\n"
                "📋 *Estado de matrícula* - ¿cómo va mi inscripción?\n"
                "🔑 *Acceso a plataforma* - usuario y contraseña\n\n"
                "¿Qué necesitas?"
            )
    elif any(p in text for p in despedidas):
        msg = f"¡Hasta pronto{saludo_name}! 👋 Fue un gusto ayudarte."
    elif any(p in text for p in ayuda):
        msg = (
            "¡Claro! Estas son las cosas en las que puedo ayudarte:\n\n"
            "📋 *Estado* - Consultar el estado de tu matrícula\n"
            "🔑 *Acceso* - Obtener usuario y contraseña de la plataforma\n"
            "✅ *Confirmar* - Confirmar o rechazar tu cupo\n\n"
            "Solo escribe lo que necesitas 😊"
        )
    else:
        # Mensaje por defecto más amigable
        msg = (
            f"Hola{saludo_name}, no estoy seguro de cómo ayudarte con eso. 🤔\n\n"
            "Puedo asistirte con:\n"
            "• Estado de tu matrícula\n"
            "• Acceso a la plataforma\n\n"
            "¿Cuál de estas opciones necesitas?"
        )
    
    return {"messages": [AIMessage(content=msg)]}