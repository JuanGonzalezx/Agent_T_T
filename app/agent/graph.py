import os
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from app.agent.state import AgentState
from app.agent.nodes import (
    load_context_node,
    check_status_node,
    platform_access_node,
    llm_fallback_node
)

# 1. Configuración del Modelo Gemini
# Usamos 'gemini-1.5-flash' porque es el más rápido y barato para chatbots
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    # La API Key la toma automáticamente de os.environ["GOOGLE_API_KEY"]
)

def router(state: AgentState):
    """
    El Router lee el mensaje y decide a qué experto enviarlo.
    """
    messages = state['messages']
    last_msg = messages[-1].content
    
    # Prompt de Sistema para Clasificación
    system_prompt = (
        "Eres un clasificador de intenciones para la mesa de ayuda de Talento Tech.\n"
        "Analiza el mensaje del usuario y responde ÚNICAMENTE con una de estas palabras clave:\n\n"
        "STATUS -> Si pregunta por estado de matrícula, inscripción, '¿cómo voy?', fechas.\n"
        "ACCESS -> Si menciona plataforma, clave, usuario, link, 'no puedo entrar'.\n"
        "GENERAL -> Saludos, gracias, insultos o temas fuera de contexto.\n\n"
        f"Mensaje: {last_msg}"
    )
    
    try:
        response = llm.invoke(system_prompt)
        intent = response.content.strip().upper()
        
        # Limpieza de seguridad por si el modelo responde con texto extra
        if "STATUS" in intent: intent = "STATUS"
        elif "ACCESS" in intent: intent = "ACCESS"
        else: intent = "GENERAL"
        
    except Exception as e:
        print(f"⚠️ Error invocando Gemini: {e}")
        intent = "GENERAL"
    
    return {"intent": intent}

def decide_next_node(state: AgentState):
    """Semáforo que dirige el tráfico según la intención."""
    intent = state.get('intent')
    if intent == 'STATUS': return "check_status"
    if intent == 'ACCESS': return "platform_access"
    return "general_response"

# 2. Construcción del Grafo
def build_agent_graph():
    workflow = StateGraph(AgentState)
    
    # Agregar Nodos (Expertos)
    workflow.add_node("load_context", load_context_node)
    workflow.add_node("router_gemini", router)
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
            "check_status": "check_status",
            "platform_access": "platform_access",
            "general_response": "general_response"
        }
    )
    
    # Finalizar
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