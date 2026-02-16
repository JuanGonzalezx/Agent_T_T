"""
Nodo de respuestas rápidas determinísticas (sin IA).

Maneja saludos, agradecimientos, despedidas y confirmaciones
con respuestas pre-definidas para minimizar costos de tokens.
"""

import logging
from langchain_core.messages import AIMessage
from app.agent.state import AgentState

logger = logging.getLogger(__name__)


def quick_response_node(state: AgentState):
    """
    Genera respuestas determinísticas para intenciones simples.
    NO usa IA - costo de tokens: 0
    """
    intent = state.get('intent', '')
    name = state.get('student_name')
    student_data = state.get('student_data')
    
    # Nombre del usuario
    nombre = name if name and name != 'Estudiante' else ""
    saludo_nombre = f" {nombre}" if nombre else ""
    
    # Mapa de respuestas determinísticas
    responses = {
        "SALUDO": (
            f"¡Hola{saludo_nombre}! 👋 Soy el asistente de *Talento Tech*.\n\n"
            "¿En qué puedo ayudarte?\n\n"
            "📋 *estado* → Consultar tu matrícula\n"
            "🔑 *acceso* → Credenciales de la plataforma\n"
            "❓ También puedo responder preguntas sobre horarios, inscripción y certificación."
        ),
        
        "GRACIAS": (
            f"¡Con gusto{saludo_nombre}! 😊\n"
            "Estoy aquí si necesitas algo más."
        ),
        
        "OK": (
            "Perfecto 👍\n"
            "Si tienes otra consulta, aquí estaré."
        ),
        
        "DESPEDIDA": (
            f"¡Hasta pronto{saludo_nombre}! 👋\n"
            "Fue un gusto ayudarte. ¡Éxitos en tu formación!"
        )
    }
    
    msg = responses.get(intent, responses["SALUDO"])
    
    logger.info(f"[QUICK] Respuesta determinística para intent={intent} (0 tokens IA)")
    
    return {"messages": [AIMessage(content=msg)]}
