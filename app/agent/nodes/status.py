import logging
from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from app.agent.state import AgentState
from app.utils.gemini_logger import invoke_with_logging, log_token_usage

logger = logging.getLogger(__name__)

# Instanciamos el modelo aquí para que el nodo tenga su propio "cerebro" redactor
llm_redactor = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite", # Usamos el que te está funcionando rápido
    temperature=0.4, # Un poco de creatividad para que no suene robótico
    max_retries=2
)

def check_status_node(state: AgentState):
    """Revisa el estado de la matrícula usando IA para redactar el mensaje."""
    data = state.get('student_data')
    name = state.get('student_name', 'Estudiante')
    
    # 1. Validación rápida si no hay datos
    if not data:
        msg = (
            f"Hola {name}, no encontré ningún registro asociado a este número. 🤔\n\n"
            "¿Ya te inscribiste al programa? Si crees que es un error, "
            "escríbenos a soporte@talentotech.gov.co"
        )
        return {"messages": [AIMessage(content=msg)]}

    # 2. Extraer contexto de la Base de Datos
    estado_envio = str(data.get('estado_envio', '')).strip().lower()
    respuesta = str(data.get('respuesta', '')).strip().title() # Quedará como 'Sí', 'No', o 'Default'
    bootcamp = data.get('bootcamp_nombre', 'tu bootcamp')
    modalidad = data.get('modalidad', 'No especificada')
    inicio = data.get('inicio_formacion', 'Pronto')

    # 3. Prompt optimizado (reducido para menos tokens)
    prompt = f"""Informa estado de matrícula a {name}. Respuesta concisa, formato WhatsApp.

Datos BD:
- Bootcamp: {bootcamp}
- Modalidad: {modalidad}
- Inicio: {inicio}
- Confirmación: {respuesta}
- Estado: {estado_envio}

Reglas:
- Si confirmó "Sí": cupo CONFIRMADO, felicita, indica inicio.
- Si "No": estado CANCELADO, despide cordialmente.
- Si matriculado/graduado: felicita.
- NO pidas confirmar SÍ/NO.
- Max 4 líneas. Usa emojis con moderación."""

    try:
        logger.info(f"[STATUS NODO] IA redactando estado para {name} (Respuesta BD: {respuesta})")
        # Invocamos a Gemini para que haga la magia
        response = invoke_with_logging(llm_redactor, prompt, context="STATUS_NODO")
        msg = response.content.strip()
        
    except Exception as e:
        logger.error(f"[STATUS NODO] Error con Gemini redactor: {e}")
        # Fallback de emergencia por si la API se cae o hay límite de cuota
        msg = (
            f"¡Hola {name}! 👋 Tu estado actual en *{bootcamp}* es: *Confirmado/Registrado*.\n"
            f"Tu respuesta guardada es: {respuesta}.\n"
            "Si tienes dudas adicionales, escríbenos a soporte."
        )

    return {"messages": [AIMessage(content=msg)]}