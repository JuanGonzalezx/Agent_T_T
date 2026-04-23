import os
import logging
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from app.agent.state import AgentState
from app.utils.gemini_logger import invoke_with_logging, log_token_usage

# Importamos de la carpeta 'nodes'
from app.agent.nodes import (
    load_context_node,
    check_status_node,
    platform_access_node,
    confirm_response_node,
    confirm_event_node,
    llm_fallback_node,
    quick_response_node,
    citas_node
)

logger = logging.getLogger(__name__)

# 1. Configuración del Modelo Gemini (Router)
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite", # O el que estés usando y no te dé error
    temperature=0.0,  # 0.0 para el Router porque queremos precisión matemática, no creatividad
    max_tokens=10,    # Solo necesitamos 1 palabra de respuesta
    timeout=30,
    max_retries=2,
)

def router(state: AgentState):
    """El Router lee el mensaje y decide a qué experto enviarlo."""
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
    
    # ==========================================================
    # 🎯 PRIORIDAD 0: Campaña activa esperando respuesta
    # ==========================================================
    # Si el estudiante tiene una campaña (EVENTO, etc.) con envío hecho
    # y sin respuesta, enrutar al nodo correspondiente.
    active_campaign = state.get('active_campaign')
    
    if active_campaign:
        campana_tipo = active_campaign.get('campana_tipo', '').upper()
        respuesta_usuario = active_campaign.get('respuesta_usuario', '')
        
        if not respuesta_usuario or respuesta_usuario.strip() == '':
            if campana_tipo == 'EVENTO':
                logger.info(f"[ROUTER] Campaña EVENTO activa → CONFIRM_EVENT")
                return {"intent": "CONFIRM_EVENT"}
            if campana_tipo == 'MATRICULA':
                logger.info(f"[ROUTER] Campaña MATRICULA activa → CONFIRM")
                return {"intent": "CONFIRM"}
    
    # ==========================================================
    # 📅 PRIORIDAD 0.5: Sesión de citas activa
    # ==========================================================
    # Si el usuario está en medio del flujo de citas (ya le mostramos
    # los horarios y está enviando la descripción), SIEMPRE va a CITA
    # sin importar qué keywords tenga su mensaje.
    from app.agent.nodes.citas import has_active_cita_session
    
    phone = state.get('phone', '')
    if has_active_cita_session(phone):
        logger.info("[ROUTER] Sesión de cita activa → CITA (bypass keywords)")
        return {"intent": "CITA"}
    
    # ==========================================================
    # 📅 PRIORIDAD 1: CITAS - Keywords explícitas (ANTES de todo)
    # ==========================================================
    # Se evalúa PRIMERO para evitar que "matrícula", "horario", etc.
    # roben mensajes que son parte del flujo de agendamiento.
    cita_keywords = [
        'cita', 'agendar', 'agendar cita', 'cancelar cita', 'estado cita',
        'mi cita', 'bienestar', 'psicolog', 'reunión', 'reunion',
        'solicitar cita', 'pedir cita', 'reservar cita',
        'quisiera cancelar', 'quiero cancelar', 'me gustaria cancelar',
        'me gustaría cancelar', 'consultar cita', 'ver cita',
        'estado de mi cita', 'estado de una cita',
    ]
    if any(kw in last_msg for kw in cita_keywords):
        logger.info("[ROUTER] Fast-Path: CITA (sin IA)")
        return {"intent": "CITA"}

    # ==========================================================
    # 🔒 REGLA DE ORO: Modo "Confirmación" por estado académico
    # ==========================================================
    student_data = state.get('student_data')
    
    if student_data:
        estado_academico = str(student_data.get('estado_academico', 'INSCRITO')).upper()
            
    # ==========================================================
    # 🚀 ESCUDO ANTI-CUOTAS (FAST-PATH EXPANDIDO)
    # ==========================================================
    # Detectar patrones comunes SIN usar IA (ahorra tokens y tiempo)
    
    # STATUS patterns
    status_keywords = ['estado', 'matrícula', 'matricula', 'inscripción', 'inscripcion', 
                       'como voy', 'cómo voy', 'mi estado', 'estoy inscrito']
    if any(kw in last_msg for kw in status_keywords):
        logger.info("[ROUTER] Fast-Path: STATUS")
        return {"intent": "STATUS"}
    
    # ACCESS patterns  
    access_keywords = ['acceso', 'plataforma', 'clave', 'contraseña', 'usuario', 
                       'entrar', 'ingresar', 'moodle', 'login', 'credenciales']
    if any(kw in last_msg for kw in access_keywords):
        logger.info("[ROUTER] Fast-Path: ACCESS")
        return {"intent": "ACCESS"}
    
    # SALUDOS - respuesta determinística (sin IA)
    saludos = ['hola', 'buenos días', 'buenos dias', 'buenas tardes', 'buenas noches',
               'buenas', 'hey', 'hi', 'hello', 'saludos', 'qué tal', 'que tal']
    if any(s in last_msg for s in saludos) and len(last_msg) < 30:
        logger.info("[ROUTER] Fast-Path: SALUDO (sin IA)")
        return {"intent": "SALUDO"}
    
    # AGRADECIMIENTOS - respuesta determinística
    gracias_keywords = ['gracias', 'thanks', 'thank you', 'te agradezco', 'muy amable']
    if any(g in last_msg for g in gracias_keywords):
        logger.info("[ROUTER] Fast-Path: GRACIAS (sin IA)")
        return {"intent": "GRACIAS"}
    
    # CONFIRMACIONES SIMPLES - respuesta determinística
    ok_keywords = ['ok', 'listo', 'perfecto', 'entendido', 'vale', 'genial', 'excelente']
    if last_msg in ok_keywords or (len(last_msg) < 15 and any(k in last_msg for k in ok_keywords)):
        logger.info("[ROUTER] Fast-Path: OK (sin IA)")
        return {"intent": "OK"}
    
    # DESPEDIDAS - respuesta determinística
    despedidas = ['chao', 'adiós', 'adios', 'bye', 'hasta luego', 'nos vemos']
    if any(d in last_msg for d in despedidas):
        logger.info("[ROUTER] Fast-Path: DESPEDIDA (sin IA)")
        return {"intent": "DESPEDIDA"}
    
    # ==========================================================
    # 📚 FAQs COMUNES - respuestas pre-definidas (sin IA)
    # ==========================================================
    # Qué es Talento Tech
    info_talento = ['qué es talento', 'que es talento', 'talento tech', 'talentotech', 
                    'de qué trata', 'de que trata', 'qué programa', 'que programa']
    if any(kw in last_msg for kw in info_talento):
        logger.info("[ROUTER] Fast-Path: INFO_TALENTO (sin IA)")
        return {"intent": "INFO_TALENTO"}
    
    # Inscripción/registro
    info_inscripcion = ['cómo me inscribo', 'como me inscribo', 'inscribirme', 'registrarme',
                        'quiero inscribirme', 'donde me inscribo', 'dónde me inscribo',
                        'proceso de inscripción', 'proceso de inscripcion', 'requisitos']
    if any(kw in last_msg for kw in info_inscripcion):
        logger.info("[ROUTER] Fast-Path: INFO_INSCRIPCION (sin IA)")
        return {"intent": "INFO_INSCRIPCION"}
    
    # Bootcamps disponibles
    info_bootcamps = ['bootcamp', 'cursos', 'programas', 'qué puedo estudiar', 'que puedo estudiar',
                      'carreras', 'opciones', 'oferta', 'qué hay', 'que hay']
    if any(kw in last_msg for kw in info_bootcamps):
        logger.info("[ROUTER] Fast-Path: INFO_BOOTCAMPS (sin IA)")
        return {"intent": "INFO_BOOTCAMPS"}
    
    # Horarios
    info_horario = ['horario', 'horarios', 'a qué hora', 'a que hora', 'cuando son las clases',
                    'duración', 'duracion', 'cuánto dura', 'cuanto dura']
    if any(kw in last_msg for kw in info_horario):
        logger.info("[ROUTER] Fast-Path: INFO_HORARIO (sin IA)")
        return {"intent": "INFO_HORARIO"}
    
    # Certificación
    info_certificado = ['certificado', 'certificación', 'certificacion', 'diploma', 'título', 'titulo',
                        'al terminar', 'cuando termine', 'acredita']
    if any(kw in last_msg for kw in info_certificado):
        logger.info("[ROUTER] Fast-Path: INFO_CERTIFICADO (sin IA)")
        return {"intent": "INFO_CERTIFICADO"}
    
    # Costos
    info_costo = ['gratis', 'gratuito', 'costo', 'precio', 'cuánto cuesta', 'cuanto cuesta', 'pagar']
    if any(kw in last_msg for kw in info_costo):
        logger.info("[ROUTER] Fast-Path: INFO_COSTO (sin IA)")
        return {"intent": "INFO_COSTO"}
    
    # Soporte/contacto
    info_contacto = ['contacto', 'soporte', 'ayuda', 'número', 'numero', 'correo', 'email', 'teléfono']
    if any(kw in last_msg for kw in info_contacto):
        logger.info("[ROUTER] Fast-Path: INFO_CONTACTO (sin IA)")
        return {"intent": "INFO_CONTACTO"}

    # ==========================================================
    # 🧠 SOLO para consultas MUY ESPECÍFICAS: Usamos Gemini
    # ==========================================================
    system_prompt = (
        "Clasifica la intención. Responde SOLO: STATUS, ACCESS o GENERAL.\n"
        "STATUS=estado matrícula. ACCESS=plataforma/clave. GENERAL=otro.\n"
        f"Mensaje: \"{last_msg}\"\nIntención:"
    )
    
    try:
        response = invoke_with_logging(llm, system_prompt, context="ROUTER")
        raw_intent = response.content.strip().upper()
        logger.info(f"[ROUTER] Gemini respuesta raw: '{raw_intent}'")
        
        # Limpieza de seguridad
        if "STATUS" in raw_intent: intent = "STATUS"
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
    
    if intent == 'CONFIRM_EVENT': return "confirm_event"
    if intent == 'CONFIRM': return "confirm_response"
    if intent == 'STATUS': return "check_status"
    if intent == 'ACCESS': return "platform_access"
    if intent == 'CITA': return "citas"
    
    # Respuestas determinísticas (sin IA) - COSTO 0 TOKENS
    quick_intents = ('SALUDO', 'GRACIAS', 'OK', 'DESPEDIDA', 
                     'INFO_TALENTO', 'INFO_INSCRIPCION', 'INFO_BOOTCAMPS',
                     'INFO_HORARIO', 'INFO_CERTIFICADO', 'INFO_COSTO', 'INFO_CONTACTO')
    if intent in quick_intents:
        return "quick_response"
    
    # Solo consultas MUY específicas usan IA (última opción)
    return "general_response"

# Construcción del Grafo
def build_agent_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("load_context", load_context_node)
    workflow.add_node("router_gemini", router)
    workflow.add_node("confirm_event", confirm_event_node)
    workflow.add_node("confirm_response", confirm_response_node)
    workflow.add_node("check_status", check_status_node)
    workflow.add_node("platform_access", platform_access_node)
    workflow.add_node("quick_response", quick_response_node)  # Sin IA
    workflow.add_node("general_response", llm_fallback_node)   # Con IA
    workflow.add_node("citas", citas_node)                     # Citas (sin IA)
    
    workflow.set_entry_point("load_context")
    workflow.add_edge("load_context", "router_gemini")
    
    workflow.add_conditional_edges(
        "router_gemini",
        decide_next_node,
        {
            "confirm_event": "confirm_event",
            "confirm_response": "confirm_response",
            "check_status": "check_status",
            "platform_access": "platform_access",
            "quick_response": "quick_response",
            "general_response": "general_response",
            "citas": "citas"
        }
    )
    
    workflow.add_edge("confirm_event", END)
    workflow.add_edge("confirm_response", END)
    workflow.add_edge("check_status", END)
    workflow.add_edge("platform_access", END)
    workflow.add_edge("quick_response", END)
    workflow.add_edge("general_response", END)
    workflow.add_edge("citas", END)
    
    return workflow.compile()

_agent_instance = None
def get_agent():
    global _agent_instance
    if not _agent_instance:
        _agent_instance = build_agent_graph()
    return _agent_instance