import logging
from app.agent.state import AgentState

logger = logging.getLogger(__name__)

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
        
    return {"student_name": "Estudiante", "student_data": None}