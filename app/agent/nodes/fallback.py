import logging
from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from app.agent.state import AgentState
from app.utils.gemini_logger import invoke_with_logging, log_token_usage

logger = logging.getLogger(__name__)

# Instanciamos el modelo para el Agente FAQ
llm_faq = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite", 
    temperature=0.4,  # Más natural
    max_tokens=150,   # Respuestas cortas pero con personalidad
    max_retries=2
)

def llm_fallback_node(state: AgentState):
    """Respuesta Inteligente para FAQs y Fallbacks usando Gemini."""
    messages = state.get('messages', [])
    name = state.get('student_name')
    student_data = state.get('student_data')
    
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

    # Prompt conversacional y humano
    prompt = f"""Eres un asistente virtual amigable de Talento Tech. Te llaman "Asistente Talento Tech".
Tu nombre de usuario es {nombre_usuario}.

REGLAS ESTRICTAS:
- Responde de forma natural, cálida y breve (máximo 4 líneas)
- Usa formato WhatsApp (*negritas*, _cursiva_)
- Si el mensaje no tiene que ver con Talento Tech o educación, responde amablemente que solo puedes ayudar con temas del programa
- Si no entiendes el mensaje, ofrece el menú: estado, acceso, cita
- NUNCA inventes información. Si no sabes algo, sugiere contactar soporte
- Personaliza la respuesta usando el nombre del usuario cuando sea natural

CONTEXTO DE TALENTO TECH:
- Programa de formación gratuita del MinTIC 🇨🇴
- Bootcamps: IA, Análisis de Datos, Desarrollo de Software, Cloud, Ciberseguridad
- Operado por Universidad de Caldas y Universidad de Antioquia
- Inscripción en SIGA (siga.talentotech2.com.co)
- Horario: Lunes a Viernes 6pm-10pm, duración ~2 meses
- Plataforma: talentotech2.com.co/campus (usuario y clave = número de cédula)
- Certificación oficial MinTIC, 75% asistencia mínima
- Soporte: soporte@talentotech.gov.co

OPCIONES DEL MENÚ que puedes sugerir:
📋 estado → consultar matrícula
🔑 acceso → credenciales plataforma
📅 cita → agendar cita

Mensaje del estudiante: "{last_msg}"

Responde:"""

    try:
        logger.info(f"[FAQ NODO] Procesando mensaje para {nombre_usuario}: '{last_msg}'")
        response = invoke_with_logging(llm_faq, prompt, context="FAQ_NODO")
        msg = response.content.strip()
        
    except Exception as e:
        logger.error(f"[FAQ NODO] Error con Gemini FAQ: {e}")
        msg = (
            f"Disculpa{' ' + nombre_usuario if nombre_usuario != 'Estudiante' else ''}, "
            "no pude procesar tu consulta. 😕\n\n"
            "Puedo ayudarte con:\n"
            "📋 *estado* → Consultar tu matrícula\n"
            "🔑 *acceso* → Credenciales de la plataforma\n"
            "📅 *cita* → Agendar una cita\n\n"
            "O escríbenos a soporte@talentotech.gov.co"
        )

    return {"messages": [AIMessage(content=msg)]}