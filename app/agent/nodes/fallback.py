import logging
from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from app.agent.state import AgentState

logger = logging.getLogger(__name__)

# Instanciamos el modelo para el Agente FAQ
llm_faq = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite", 
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

    # Base de Conocimiento (FAQs provistas)
    faqs = """
    BASE DE CONOCIMIENTO DE TALENTO TECH:
    1. Información general: Proyecto del MinTIC, ejecutado por U. de Caldas y U. de Antioquia. Son bootcamps gratuitos y certificados en IA, Análisis de Datos, etc. Para mayores de edad en Colombia. Hay modalidad presencial y virtual.
    2. Inscripción: En SIGA (https://siga.talentotech2.com.co/siga_new/web/app.php/inscripcionpublica_talentotech2/). Se necesita cédula en PDF legible por ambas caras.
    3. Horarios: Lunes a viernes de 6:00 p.m. a 10:00 p.m. Duración aprox de 2 meses. Hay un curso virtual de inglés técnico de 1 a 4 días ANTES de iniciar.
    4. Plataforma de clases: https://talentotech2.com.co/campus/login/index.php. Usuario y contraseña es el número de cédula. Las clases son en vivo (sincrónicas) y se pide 75% de asistencia.
    5. Certificación: Oficial por MinTIC, U. de Caldas y U. de Antioquia.
    6. Extras: Si pierden clase, hay grabaciones. Pueden invitar amigos con links. Hay cupos limitados.
    """

    prompt = f"""
    Eres el asistente virtual principal de Talento Tech. Tu labor es responder preguntas, saludar amablemente y guiar al usuario.
    
    Usuario: {nombre_usuario}
    Mensaje del usuario: "{last_msg}"

    INSTRUCCIONES ESTRICTAS:
    1. Si el usuario saluda (hola, buenos días) o agradece: Responde cordialmente, dile que estás para ayudar, y muéstrale este menú de opciones corto y directo:
       - 📋 Escribe *estado* para ver tu matrícula.
       - 🔑 Escribe *acceso* para datos de la plataforma.
    2. Si el usuario hace una pregunta sobre el programa: Usa ÚNICAMENTE la "BASE DE CONOCIMIENTO DE TALENTO TECH" de abajo para responderle de forma concisa y amigable. No inventes información.
    3. Si el usuario hace una pregunta o comentario FUERA de contexto (ej: recetas, política, chistes, "¿qué hora es?"): Responde amablemente que eres el asistente de Talento Tech y no puedes ayudar con eso. Luego, muéstrale las opciones principales (Estado o Acceso).
    4. Responde SIEMPRE en un tono optimista, usando emojis moderadamente, y con formato amigable para WhatsApp (asteriscos para negritas, listas).
    5. Si en su mensaje pregunta algo que no está en la base de conocimiento de Talento Tech, dile que puedes ayudarle a consultar su "estado de matrícula" o "acceso a la plataforma", o que escriba a soporte.
    
    {faqs}
    
    Redacta tu respuesta a continuación:
    """

    try:
        logger.info(f"[FAQ NODO] Procesando mensaje general/FAQ para {nombre_usuario}")
        response = llm_faq.invoke(prompt)
        msg = response.content.strip()
        
    except Exception as e:
        logger.error(f"[FAQ NODO] Error con Gemini FAQ: {e}")
        # Fallback de emergencia si Gemini falla (Código determinista de seguridad)
        msg = (
            f"¡Hola {nombre_usuario}! 👋 Soy el asistente virtual de Talento Tech.\n\n"
            "Puedo ayudarte con:\n"
            "📋 Escribe *estado* para consultar tu matrícula.\n"
            "🔑 Escribe *acceso* para obtener credenciales de la plataforma.\n\n"
            "¿Qué necesitas?"
        )

    return {"messages": [AIMessage(content=msg)]}