from typing import TypedDict, Annotated, List, Optional
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # Historial de mensajes (se acumula automáticamente)
    messages: Annotated[List[dict], add_messages]
    
    # Datos del estudiante (Contexto)
    phone: str
    student_name: Optional[str]
    student_data: Optional[dict]
    
    # Intención detectada por Gemini
    intent: Optional[str]