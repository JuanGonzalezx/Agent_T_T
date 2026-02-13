import logging
from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from app.agent.state import AgentState

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
    messages = state.get('messages', [])
    
    # Saber qué preguntó exactamente el usuario para darle contexto a la IA
    last_msg = messages[-1].content if messages else "estado de matrícula"
    
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

    # 3. EL CEREBRO EN ACCIÓN: Prompt dinámico
    prompt = f"""
    Eres el asistente virtual amable y profesional de Talento Tech.
    El estudiante {name} te acaba de escribir: "{last_msg}".
    Tu trabajo es informarle su estado de matrícula basándote ÚNICAMENTE en estos datos de la base de datos:

    DATOS DEL ESTUDIANTE:
    - Bootcamp: {bootcamp}
    - Modalidad: {modalidad}
    - Fecha de inicio: {inicio}
    - Respuesta de confirmación dada: {respuesta}
    - Estado en el sistema: {estado_envio}

    REGLAS ESTRICTAS PARA TU RESPUESTA:
    1. Si la "Respuesta de confirmación" es "Sí" o "Si": Dile con mucho entusiasmo que su cupo está CONFIRMADO, que ya está inscrito oficialmente y recuérdale la fecha de inicio y modalidad.
    2. Si la "Respuesta de confirmación" es "No": Dile de forma muy amable que entendemos, que su estado es CANCELADO o NO INSCRITO para esta cohorte, y despídete cordialmente deseando verle en el futuro.
    3. Si el "Estado en el sistema" es "matriculado" o "graduado": Felicítalo acorde a su estado.
    4. NUNCA le pidas que confirme respondiendo SÍ o NO (porque si está aquí, es porque ya pasó esa etapa o su estado es diferente).
    5. Usa formato de WhatsApp (negritas con asteriscos *, listas, emojis) para que se vea muy ordenado y bonito.
    6. Sé conciso y directo al grano, no inventes datos que no estén en la lista.

    Redacta la respuesta para el estudiante ahora:
    """

    try:
        logger.info(f"[STATUS NODO] IA redactando estado para {name} (Respuesta BD: {respuesta})")
        # Invocamos a Gemini para que haga la magia
        response = llm_redactor.invoke(prompt)
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