"""
Nodo de respuestas rápidas determinísticas (sin IA).

Maneja saludos, agradecimientos, despedidas y confirmaciones
con respuestas pre-definidas para minimizar costos de tokens.
"""

import logging
from langchain_core.messages import AIMessage
from app.agent.state import AgentState

logger = logging.getLogger(__name__)


def quick_response_node(state: AgentState):
    """
    Genera respuestas determinísticas para intenciones simples.
    NO usa IA - costo de tokens: 0
    """
    intent = state.get('intent', '')
    name = state.get('student_name')
    student_data = state.get('student_data')
    
    # Nombre del usuario
    nombre = name if name and name != 'Estudiante' else ""
    saludo_nombre = f" {nombre}" if nombre else ""
    
    # Mapa de respuestas determinísticas
    responses = {
        "SALUDO": (
            f"¡Hola{saludo_nombre}! 👋 Soy el asistente de *Talento Tech*.\n\n"
            "¿En qué puedo ayudarte?\n\n"
            "📋 *estado* → Consultar tu matrícula\n"
            "🔑 *acceso* → Credenciales de la plataforma\n"
            "📅 *cita* → Agendar una cita\n"
            "❓ También puedo responder preguntas sobre horarios, inscripción y certificación."
        ),
        
        "GRACIAS": (
            f"¡Con gusto{saludo_nombre}! 😊\n"
            "Estoy aquí si necesitas algo más."
        ),
        
        "OK": (
            f"Perfecto{saludo_nombre} 👍\n"
            "Si tienes otra consulta, aquí estaré.\n\n"
            "Puedes escribirme:\n"
            "📋 *estado* · 🔑 *acceso* · 📅 *cita*"
        ),
        
        "CONFUSED": (
            f"¿En qué puedo ayudarte{saludo_nombre}? 🤔\n\n"
            "Estos son los temas en los que puedo asistirte:\n\n"
            "📋 *estado* → Consultar tu matrícula\n"
            "🔑 *acceso* → Credenciales de la plataforma\n"
            "📅 *cita* → Agendar una cita\n"
            "❓ También puedo responder sobre horarios, inscripción y costos."
        ),
        
        "DESPEDIDA": (
            f"¡Hasta pronto{saludo_nombre}! 👋\n"
            "Fue un gusto ayudarte. ¡Éxitos en tu formación!"
        ),
        
        # =====================================================
        # FAQs PRE-DEFINIDAS (0 tokens de Gemini)
        # =====================================================
        "INFO_TALENTO": (
            "*Talento Tech* es un programa de formación gratuita del MinTIC 🇨🇴\n\n"
            "✅ Bootcamps en tecnología (IA, Datos, Desarrollo)\n"
            "✅ Operado por U. de Caldas y U. de Antioquia\n"
            "✅ 100% virtual y gratuito\n"
            "✅ Certificación oficial del MinTIC\n\n"
            "¿Te gustaría saber cómo inscribirte? Escribe *inscripción*"
        ),
        
        "INFO_INSCRIPCION": (
            "📝 *Proceso de inscripción:*\n\n"
            "1️⃣ Ingresa a *siga.talentotech2.com.co*\n"
            "2️⃣ Registra tus datos personales\n"
            "3️⃣ Sube tu cédula en PDF (ambas caras)\n"
            "4️⃣ Selecciona el bootcamp de tu interés\n"
            "5️⃣ Espera confirmación por correo/WhatsApp\n\n"
            "💡 Si ya estás inscrito, escribe *estado* para verificar."
        ),
        
        "INFO_BOOTCAMPS": (
            "🎓 *Bootcamps disponibles:*\n\n"
            "🤖 Inteligencia Artificial\n"
            "📊 Análisis de Datos\n"
            "💻 Desarrollo de Software\n"
            "☁️ Cloud Computing\n"
            "🔒 Ciberseguridad\n\n"
            "Todos son *gratuitos* y con certificación MinTIC.\n"
            "Escribe *inscripción* para saber cómo aplicar."
        ),
        
        "INFO_HORARIO": (
            "⏰ *Horarios de clases:*\n\n"
            "📅 Lunes a Viernes\n"
            "🕕 6:00 PM a 10:00 PM\n"
            "⏱️ Duración: ~2 meses\n\n"
            "💡 El curso de inglés previo dura 1-4 días antes del bootcamp principal."
        ),
        
        "INFO_CERTIFICADO": (
            "🏆 *Certificación:*\n\n"
            "✅ Certificado oficial del *MinTIC*\n"
            "✅ Avalado como formación para el trabajo\n"
            "✅ Requisito: 75% de asistencia mínima\n\n"
            "El certificado se envía por correo al completar el bootcamp."
        ),
        
        "INFO_COSTO": (
            "💚 *¡Es 100% GRATIS!*\n\n"
            "Talento Tech es financiado por el MinTIC.\n"
            "No debes pagar absolutamente nada:\n"
            "• Sin matrícula\n"
            "• Sin mensualidades\n"
            "• Sin costo de certificado\n\n"
            "Escribe *inscripción* para saber cómo aplicar."
        ),
        
        "INFO_CONTACTO": (
            "📞 *Canales de soporte:*\n\n"
            "📧 soporte@talentotech.gov.co\n"
            "🌐 talentotech2.com.co\n\n"
            "También puedo ayudarte aquí. ¿Qué necesitas?"
        )
    }
    
    msg = responses.get(intent, responses["SALUDO"])
    
    logger.info(f"[QUICK] Respuesta determinística para intent={intent} (0 tokens IA)")
    
    return {"messages": [AIMessage(content=msg)]}
