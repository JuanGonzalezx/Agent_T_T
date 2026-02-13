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
    Eres el asistente virtual de Talento Tech. Responde de forma directa y concisa.
    
    Usuario: {nombre_usuario}
    Mensaje del usuario: "{last_msg}"

    REGLAS CRÍTICAS (LÉELAS BIEN):
    
    ⚠️ PROHIBIDO SALUDAR en cada mensaje. Solo saluda si el usuario te saluda primero (hola, buenos días, etc).
    
    1. SI EL USUARIO SALUDA (hola, buenos días, buenas, hey): 
       - Ahí sí salúdalo por su nombre UNA sola vez.
       - Muéstrale el menú: 📋 *estado* | 🔑 *acceso*
    
    2. SI EL USUARIO HACE UNA PREGUNTA (qué es Talento Tech, horarios, inscripción, etc):
       - NO lo saludes. Ve directo al grano.
       - Responde usando la BASE DE CONOCIMIENTO de abajo.
       - Sé conciso, máximo 3-4 líneas.
    
    3. SI EL USUARIO DICE "ok", "gracias", "listo", "perfecto", o similar:
       - NO lo saludes. Solo di algo breve como "¡Con gusto! Aquí estoy si necesitas algo más. 😊"
    
    4. SI EL USUARIO DICE ALGO FUERA DE CONTEXTO:
       - NO lo saludes. Solo dile amablemente que eres asistente de Talento Tech.
    
    Usa emojis con moderación. Formato WhatsApp (asteriscos para negritas).
    
    {faqs}
    
    Responde ahora (SIN SALUDAR a menos que el usuario haya saludado primero):
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