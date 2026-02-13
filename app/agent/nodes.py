import logging
from langchain_core.messages import AIMessage
from app.agent.state import AgentState

logger = logging.getLogger(__name__)

# --- NODO 1: CARGAR CONTEXTO ---
def load_context_node(state: AgentState):
    """Carga los datos del estudiante desde Turso/SQLite."""
    # Import diferido para evitar circular imports
    from app import db_handler
    
    phone = state['phone']
    logger.info(f"[AGENT] Cargando contexto para: {phone}")
    
    try:
        estudiantes = db_handler.get_estudiante_by_phone(phone)
        
        if estudiantes:
            student = estudiantes[0]
            logger.info(f"[AGENT] Estudiante encontrado: {student.get('nombre')}")
            return {
                "student_name": student.get('nombre', 'Estudiante'),
                "student_data": student
            }
    except Exception as e:
        logger.error(f"[AGENT] Error cargando contexto: {e}")
        
    return {"student_name": None, "student_data": None}

# --- NODO 2: ESTADO DE INSCRIPCIÓN ---
def check_status_node(state: AgentState):
    data = state.get('student_data')
    name = state.get('student_name', 'Estudiante')
    
    if not data:
        msg = "No encontré tu registro. 🧐 ¿Te inscribiste con este número?"
    else:
        # Mapeo de estados según tu Excel
        estado = data.get('estado_envio', 'Pendiente')
        bootcamp = data.get('bootcamp_nombre', 'el curso')
        
        msg = f"Hola {name}, tu estado en *{bootcamp}* es: *{estado}*."
        
        if estado == 'sent':
            msg += "\n\nEstamos esperando tu confirmación. Responde *SÍ* para iniciar."
        elif estado == 'matriculado':
            msg += "\n\n¡Ya eres parte del equipo! Nos vemos en clase. 🚀"

    return {"messages": [AIMessage(content=msg)]}

# --- NODO 3: ACCESO A PLATAFORMA ---
def platform_access_node(state: AgentState):
    data = state.get('student_data')
    
    if not data:
        msg = "No estás inscrito. 📝 Regístrate aquí: [LINK_INSCRIPCION]"
    else:
        # Normalizar comparación de respuesta (Sí/Si/SI → True)
        respuesta = str(data.get('respuesta', '')).lower().strip()
        confirmo = respuesta in ('sí', 'si', 'yes')
        opt_in = str(data.get('opt_in', '')).upper() == 'TRUE'
        matriculado = data.get('estado_envio') == 'matriculado'
        
        if opt_in or confirmo or matriculado:
            msg = (
                "🔑 **Acceso a la Plataforma**\n\n"
                "🔗 Link: https://talentotech2.com.co/campus/login/index.php\n"
                "👤 Usuario: Tu cédula\n"
                "🔒 Contraseña: Tu cédula"
            )
        else:
            msg = "Tu usuario está en proceso de verificación. Te avisaremos pronto. ⏳"
        
    return {"messages": [AIMessage(content=msg)]}

# --- NODO 4: RESPUESTA GENÉRICA ---
def llm_fallback_node(state: AgentState):
    msg = "Soy el asistente virtual de Talento Tech. Puedo ayudarte con tu estado de matrícula o acceso a la plataforma."
    return {"messages": [AIMessage(content=msg)]}