import os
import logging
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from app.agent.state import AgentState

# Importamos de la carpeta 'nodes'
from app.agent.nodes import (
    load_context_node,
    check_status_node,
    platform_access_node,
    confirm_response_node,
    llm_fallback_node
)

logger = logging.getLogger(__name__)

# 1. Configuración del Modelo Gemini (Router)
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite", # O el que estés usando y no te dé error
    temperature=0.0,  # 0.0 para el Router porque queremos precisión matemática, no creatividad
    max_tokens=10,    # Solo necesitamos 1 palabra de respuesta
    timeout=30,
    max_retries=2,
)

def router(state: AgentState):
    """El Router lee el mensaje y decide a qué experto enviarlo."""
    messages = state.get('messages', [])
    
    if not messages:
        logger.warning("[ROUTER] No hay mensajes en el state")
        return {"intent": "GENERAL"}
    
    # Obtener el contenido del último mensaje
    last_message = messages[-1]
    
    if hasattr(last_message, 'content'):
        last_msg = last_message.content.strip().lower()
    elif isinstance(last_message, dict):
        last_msg = last_message.get('content', '').strip().lower()
    else:
        last_msg = str(last_message).strip().lower()
    
    logger.info(f"[ROUTER] Procesando mensaje: '{last_msg}'")
    
    # ==========================================================
    # 🔒 REGLA DE ORO DEL FLUJO 1: Modo "Confirmación Estricta"
    # ==========================================================
    student_data = state.get('student_data')
    
    if student_data:
        estado_envio = student_data.get('estado_envio', '')
        respuesta_actual = student_data.get('respuesta', '')
        
        espera_confirmacion = (
            estado_envio == 'sent' and 
            (not respuesta_actual or respuesta_actual.strip() == '' or respuesta_actual.strip().lower() == 'default')
        )
        
        if espera_confirmacion:
            logger.info("[ROUTER] Estudiante en modo de confirmación estricta.")
            return {"intent": "CONFIRM"}
            
    # ==========================================================
    # 🚀 ESCUDO ANTI-CUOTAS (FAST-PATH)
    # ==========================================================
    # Si detecta palabras exactas del menú, ataja sin usar IA (ahorra saldo y tiempo)
    if last_msg in ['estado', 'estado de matrícula', 'estado de matricula', 'mi estado', 'como voy']:
        logger.info("[ROUTER] Fast-Path: Detectado STATUS")
        return {"intent": "STATUS"}
        
    if last_msg in ['acceso', 'acceso plataforma', 'acceso a la plataforma', 'plataforma', 'claves']:
        logger.info("[ROUTER] Fast-Path: Detectado ACCESS")
        return {"intent": "ACCESS"}

    # ==========================================================
    # 🧠 FLUJO 2, 3 y FAQ: Usamos Gemini para intenciones complejas
    # ==========================================================
    system_prompt = (
        "Eres un clasificador de intenciones para la mesa de ayuda de Talento Tech.\n"
        "Analiza el mensaje del usuario y responde ÚNICAMENTE con una de estas palabras clave:\n\n"
        "STATUS -> Si pregunta por su propio estado de matrícula, inscripción, '¿cómo voy?', 'mi estado'.\n"
        "ACCESS -> Si menciona problemas con la plataforma, clave, usuario, link de Moodle, 'no puedo entrar'.\n"
        "GENERAL -> Si hace PREGUNTAS FRECUENTES del programa (qué es, horarios, duración, certificados, cómo inscribirse, inglés), o si saluda, agradece, se despide, pide ayuda, o habla de temas fuera de contexto.\n\n"
        f"Mensaje del usuario: \"{last_msg}\"\n\n"
        "Responde con UNA sola palabra: STATUS, ACCESS, o GENERAL."
    )
    
    try:
        response = llm.invoke(system_prompt)
        raw_intent = response.content.strip().upper()
        logger.info(f"[ROUTER] Gemini respuesta raw: '{raw_intent}'")
        
        # Limpieza de seguridad
        if "STATUS" in raw_intent: intent = "STATUS"
        elif "ACCESS" in raw_intent: intent = "ACCESS"
        else: intent = "GENERAL"
        
        logger.info(f"[ROUTER] Intención clasificada: {intent}")
        
    except Exception as e:
        logger.error(f"[ROUTER] Error invocando Gemini: {e}")
        intent = "GENERAL"
    
    return {"intent": intent}

def decide_next_node(state: AgentState):
    """Semáforo que dirige el tráfico según la intención."""
    intent = state.get('intent')
    
    if intent == 'CONFIRM': return "confirm_response"
    if intent == 'STATUS': return "check_status"
    if intent == 'ACCESS': return "platform_access"
    
    return "general_response"

# Construcción del Grafo
def build_agent_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("load_context", load_context_node)
    workflow.add_node("router_gemini", router)
    workflow.add_node("confirm_response", confirm_response_node)
    workflow.add_node("check_status", check_status_node)
    workflow.add_node("platform_access", platform_access_node)
    workflow.add_node("general_response", llm_fallback_node)
    
    workflow.set_entry_point("load_context")
    workflow.add_edge("load_context", "router_gemini")
    
    workflow.add_conditional_edges(
        "router_gemini",
        decide_next_node,
        {
            "confirm_response": "confirm_response",
            "check_status": "check_status",
            "platform_access": "platform_access",
            "general_response": "general_response"
        }
    )
    
    workflow.add_edge("confirm_response", END)
    workflow.add_edge("check_status", END)
    workflow.add_edge("platform_access", END)
    workflow.add_edge("general_response", END)
    
    return workflow.compile()

_agent_instance = None
def get_agent():
    global _agent_instance
    if not _agent_instance:
        _agent_instance = build_agent_graph()
    return _agent_instance