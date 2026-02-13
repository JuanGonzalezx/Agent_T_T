import os
import logging
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from app.agent.state import AgentState

# 💡 AHORA IMPORTAMOS DE LA CARPETA 'nodes' QUE CREAMOS
from app.agent.nodes import (
    load_context_node,
    check_status_node,
    platform_access_node,
    confirm_response_node,
    llm_fallback_node
)

logger = logging.getLogger(__name__)

# 1. Configuración del Modelo Gemini
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0.1,  # Un poco de variabilidad para respuestas más naturales
    max_tokens=100,   # Limitado ya que solo clasificamos
    timeout=30,
    max_retries=2,
)

def router(state: AgentState):
    """
    El Router lee el mensaje y decide a qué experto enviarlo.
    """
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
    
    # 🚀 FAST-PATH: Ahorrar tokens y tiempo si el usuario presionó Sí/No
    botones_confirmacion = ['si', 'sí', 'no', 'acepto', 'rechazar', 'cancelar']
    if last_msg in botones_confirmacion:
        logger.info("[ROUTER] Fast-Path: Detectado botón de confirmación.")
        return {"intent": "CONFIRM"}
    
    # Si no es un botón, usamos Gemini
    system_prompt = (
        "Eres un clasificador de intenciones para la mesa de ayuda de Talento Tech.\n"
        "Analiza el mensaje del usuario y responde ÚNICAMENTE con una de estas palabras clave:\n\n"
        "CONFIRM -> Si el mensaje es una confirmación o negación simple: 'sí', 'si', 'no', 'acepto', 'confirmo', 'rechazo', 'yes', 'ok'.\n"
        "STATUS -> Si pregunta por estado de matrícula, inscripción, '¿cómo voy?', 'estado de matrícula', 'mi estado', fechas.\n"
        "ACCESS -> Si menciona plataforma, clave, usuario, link, 'no puedo entrar', 'acceso plataforma', 'acceso'.\n"
        "GENERAL -> SOLO para saludos como 'hola', 'gracias', despedidas, o temas completamente fuera de contexto.\n\n"
        f"Mensaje del usuario: \"{last_msg}\"\n\n"
        "Responde con UNA sola palabra: CONFIRM, STATUS, ACCESS, o GENERAL."
    )
    
    try:
        response = llm.invoke(system_prompt)
        raw_intent = response.content.strip().upper()
        logger.info(f"[ROUTER] Gemini respuesta raw: '{raw_intent}'")
        
        # Limpieza de seguridad
        if "CONFIRM" in raw_intent: intent = "CONFIRM"
        elif "STATUS" in raw_intent: intent = "STATUS"
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
    student_data = state.get('student_data')
    
    # Validar si CONFIRM es aplicable según lógica de negocio
    if intent == 'CONFIRM':
        if student_data:
            estado_envio = student_data.get('estado_envio', '')
            respuesta_actual = student_data.get('respuesta', '')
            
            respuesta_vacia = (
                not respuesta_actual or 
                respuesta_actual.strip() == '' or 
                respuesta_actual.strip().lower() == 'default'
            )
            
            espera_confirmacion = (estado_envio == 'sent' and respuesta_vacia)
            
            if espera_confirmacion:
                return "confirm_response"
            else:
                return "general_response"
        else:
            return "general_response"
    
    if intent == 'STATUS': return "check_status"
    if intent == 'ACCESS': return "platform_access"
    
    return "general_response"

# 2. Construcción del Grafo
def build_agent_graph():
    workflow = StateGraph(AgentState)
    
    # Agregar Nodos (Expertos)
    workflow.add_node("load_context", load_context_node)
    workflow.add_node("router_gemini", router)
    workflow.add_node("confirm_response", confirm_response_node)
    workflow.add_node("check_status", check_status_node)
    workflow.add_node("platform_access", platform_access_node)
    workflow.add_node("general_response", llm_fallback_node)
    
    # Conectar Nodos (Flujo)
    workflow.set_entry_point("load_context")
    workflow.add_edge("load_context", "router_gemini")
    
    # Aristas Condicionales
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
    
    # Finalizar
    workflow.add_edge("confirm_response", END)
    workflow.add_edge("check_status", END)
    workflow.add_edge("platform_access", END)
    workflow.add_edge("general_response", END)
    
    return workflow.compile()

# Singleton para importar
_agent_instance = None

def get_agent():
    global _agent_instance
    if not _agent_instance:
        _agent_instance = build_agent_graph()
    return _agent_instance