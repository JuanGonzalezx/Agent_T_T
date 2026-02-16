import logging
from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from app.agent.state import AgentState
from app.utils.gemini_logger import invoke_with_logging, log_token_usage

logger = logging.getLogger(__name__)

# Instanciamos el modelo para el Agente FAQ
llm_faq = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-lite", 
    temperature=0.3, # Un poco de creatividad para que converse naturalmente
    max_retries=2
)

def llm_fallback_node(state: AgentState):
    """Respuesta Inteligente para FAQs, Saludos y Fallbacks usando Gemini."""
    messages = state.get('messages', [])
    name = state.get('student_name')
    student_data = state.get('student_data')
    
    # Manejo del nombre
    nombre_usuario = name if name and name != 'Estudiante' else "Estudiante"
    
    # Obtener el mensaje del usuario
    last_msg = ""
    if messages:
        last_message = messages[-1]
        if hasattr(last_message, 'content'):
            last_msg = last_message.content.strip()
        elif isinstance(last_message, dict):
            last_msg = last_message.get('content', '').strip()
        else:
            last_msg = str(last_message).strip()

    # Base de Conocimiento compacta (optimizada para menos tokens)
    prompt = f"""Asistente de Talento Tech. Responde DIRECTO, sin saludar. Max 3 líneas.

Pregunta: "{last_msg}"

DATOS:
- Bootcamps gratuitos MinTIC (U.Caldas/U.Antioquia). IA, Datos, etc.
- Inscripción: SIGA (siga.talentotech2.com.co). Cédula PDF ambas caras.
- Horario: L-V 6pm-10pm. Duración ~2 meses. Inglés previo 1-4 días.
- Plataforma: talentotech2.com.co/campus. Usuario/clave = cédula.
- Certificado oficial MinTIC. 75% asistencia requerida.

Si no sabes, di que contacten soporte@talentotech.gov.co
Formato WhatsApp (*negritas*). Responde:"""

    try:
        logger.info(f"[FAQ NODO] Procesando mensaje general/FAQ para {nombre_usuario}")
        response = invoke_with_logging(llm_faq, prompt, context="FAQ_NODO")
        msg = response.content.strip()
        
    except Exception as e:
        logger.error(f"[FAQ NODO] Error con Gemini FAQ: {e}")
        # Fallback de emergencia si Gemini falla
        msg = (
            "Disculpa, no pude procesar tu consulta en este momento. 😕\n\n"
            "Mientras tanto, puedo ayudarte con:\n"
            "📋 *estado* → Consultar tu matrícula\n"
            "🔑 *acceso* → Credenciales de la plataforma\n\n"
            "O escríbenos a soporte@talentotech.gov.co"
        )

    return {"messages": [AIMessage(content=msg)]}