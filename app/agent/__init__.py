"""
Módulo Agent - Agente IA con LangGraph para mesa de ayuda.

Este agente clasifica intenciones usando Gemini y responde consultas
de estudiantes sobre estado de matrícula y acceso a plataforma.

Uso:
    from app.agent import get_agent
    
    agent = get_agent()
    result = agent.invoke({
        "messages": [{"role": "user", "content": "¿cómo voy con mi inscripción?"}],
        "phone": "573001234567"
    })
"""

from app.agent.graph import get_agent, build_agent_graph
from app.agent.state import AgentState

__all__ = ['get_agent', 'build_agent_graph', 'AgentState']
