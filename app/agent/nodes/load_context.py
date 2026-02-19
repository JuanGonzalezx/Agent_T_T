import logging
from app.agent.state import AgentState

logger = logging.getLogger(__name__)

def load_context_node(state: AgentState):
    """Carga los datos del estudiante y campaña activa desde Turso/SQLite."""
    # Import diferido para evitar circular imports
    from app import db_handler
    
    phone = state['phone']
    logger.info(f"[AGENT] Cargando contexto para: {phone}")
    
    result = {"student_name": "Estudiante", "student_data": None, "active_campaign": None}
    
    try:
        estudiantes = db_handler.get_estudiante_by_phone(phone)
        
        if estudiantes:
            student = estudiantes[0]
            logger.info(f"[AGENT] Estudiante encontrado: {student.get('nombre')}")
            result["student_name"] = student.get('nombre', 'Estudiante')
            result["student_data"] = student
            
            # Buscar campaña activa esperando respuesta
            student_id = student.get('id')
            if student_id:
                try:
                    student_id_int = int(student_id)
                    active_campaign = db_handler.get_campana_activa_for_student(student_id_int)
                    if active_campaign:
                        logger.info(
                            f"[AGENT] Campaña activa encontrada: "
                            f"{active_campaign.get('campana_nombre')} "
                            f"(tipo={active_campaign.get('campana_tipo')})"
                        )
                        result["active_campaign"] = active_campaign
                except (ValueError, TypeError):
                    logger.warning(f"[AGENT] No se pudo convertir student_id: {student_id}")
    except Exception as e:
        logger.error(f"[AGENT] Error cargando contexto: {e}")
        
    return result