"""
Nodo de consulta de notas y asistencia (MVP Regionalización).

Genera un reporte académico completo para el estudiante:
- Promedio general
- Total de fallas
- Detalle por módulo/materia
- Indicador de riesgo (75% asistencia mínima)

Usa Gemini para generar una respuesta natural si hay datos,
o respuesta determinística si no hay datos.
"""

import logging
from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from app.agent.state import AgentState
from app.utils.gemini_logger import invoke_with_logging

logger = logging.getLogger(__name__)

# Modelo para generar respuestas naturales con datos académicos
llm_notas = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    temperature=0.3,
    max_tokens=300,
    max_retries=2
)


def consulta_notas_node(state: AgentState):
    """
    Genera un reporte de notas y fallas del estudiante.

    Flujo:
    1. Toma academic_data y student_data del state
    2. Calcula promedio y acumulado de fallas
    3. Formatea tabla de módulos
    4. Genera respuesta natural con Gemini
    """
    name = state.get('student_name', 'Estudiante')
    student_data = state.get('student_data')
    academic_data = state.get('academic_data')

    # ─── Caso 1: Estudiante no encontrado ───
    if not student_data:
        msg = (
            f"Hola {name}, no encontré ningún registro asociado a este número. 🤔\n\n"
            "¿Ya estás inscrito en algún técnico de *U en tu Pueblo*?\n\n"
            "Si crees que es un error, comunícate con la coordinación de tu municipio."
        )
        return {"messages": [AIMessage(content=msg)]}

    # ─── Caso 2: Sin datos académicos cargados ───
    if not academic_data or len(academic_data) == 0:
        programa = student_data.get('bootcamp_nombre', 'tu programa')
        municipio = student_data.get('municipio', '')
        ubicacion = f" en {municipio}" if municipio else ""

        msg = (
            f"Hola {name} 👋\n\n"
            f"Estás inscrito/a en *{programa}*{ubicacion}, "
            "pero aún no tenemos notas cargadas en el sistema.\n\n"
            "📝 Los docentes están actualizando las calificaciones. "
            "Intenta de nuevo en unos días.\n\n"
            "Si ya llevas tiempo en clases y no aparecen tus notas, "
            "contacta a la coordinación."
        )
        return {"messages": [AIMessage(content=msg)]}

    # ─── Caso 3: Hay datos → Generar reporte ───
    programa = student_data.get('bootcamp_nombre', 'tu programa')
    municipio = student_data.get('municipio', '')
    region = student_data.get('region', '')

    # Calcular métricas
    notas_validas = [float(m['nota']) for m in academic_data
                     if m.get('nota') is not None and m['nota'] != '']
    total_fallas = sum(int(m.get('fallas', 0) or 0) for m in academic_data)
    promedio = round(sum(notas_validas) / len(notas_validas), 2) if notas_validas else 0.0
    modulos_con_nota = len(notas_validas)
    total_modulos = len(academic_data)

    # Construir tabla de módulos
    tabla_modulos = ""
    for mod in academic_data:
        nombre_mod = mod.get('modulo_nombre', f"Módulo {mod.get('modulo_numero', '?')}")
        nota = mod.get('nota')
        fallas = mod.get('fallas', 0)

        nota_str = str(nota) if nota is not None and nota != '' else "—"
        fallas_str = str(fallas) if fallas is not None else "0"

        # Emoji indicador
        if nota is not None and nota != '':
            nota_float = float(nota)
            if nota_float >= 4.0:
                emoji = "🟢"
            elif nota_float >= 3.0:
                emoji = "🟡"
            else:
                emoji = "🔴"
        else:
            emoji = "⚪"

        tabla_modulos += f"{emoji} *{nombre_mod}*: {nota_str} | Fallas: {fallas_str}\n"

    # Indicador de riesgo
    riesgo_msg = ""
    if total_fallas >= 10:
        riesgo_msg = "\n⚠️ *Atención:* Acumulas muchas fallas. Recuerda que se requiere mínimo 75% de asistencia para certificación."
    elif promedio > 0 and promedio < 3.0:
        riesgo_msg = "\n⚠️ *Atención:* Tu promedio está por debajo de 3.0. ¡Ánimo, puedes mejorar!"

    # Prompt para Gemini (respuesta natural)
    ubicacion = f" en {municipio}" if municipio else ""
    region_str = f" ({region})" if region else ""

    prompt = f"""Eres el asistente de "U en tu Pueblo" de la Universidad de Caldas.
Genera una respuesta cálida y profesional en formato WhatsApp para el estudiante.

DATOS DEL ESTUDIANTE:
- Nombre: {name}
- Programa: {programa}
- Ubicación: {municipio}{region_str}

RENDIMIENTO ACADÉMICO:
- Promedio actual: {promedio}/5.0
- Módulos calificados: {modulos_con_nota} de {total_modulos}
- Fallas acumuladas: {total_fallas}

DETALLE POR MÓDULO:
{tabla_modulos}

REGLAS:
- Usa formato WhatsApp (*negritas*, emojis moderados)
- Incluye el resumen estadístico (promedio + fallas)
- Incluye la lista de módulos con notas
- Si el promedio es bueno (>=4.0), felicita. Si es bajo (<3.0), motiva.
- Máximo 15 líneas
- NO inventes datos, usa SOLO lo proporcionado
- Menciona que necesita 75% de asistencia para certificarse

Responde:"""

    try:
        response = invoke_with_logging(llm_notas, prompt, context="CONSULTA_NOTAS")
        msg = response.content.strip()

        # Agregar riesgo si aplica y Gemini no lo mencionó
        if riesgo_msg and "75%" not in msg and "asistencia" not in msg.lower():
            msg += riesgo_msg

    except Exception as e:
        logger.error(f"[CONSULTA_NOTAS] Error con Gemini: {e}")
        # Fallback determinístico
        ubicacion_text = f" — {municipio}{region_str}" if municipio else ""
        msg = (
            f"📊 *Reporte Académico*\n\n"
            f"Hola *{name}*!\n"
            f"📚 *{programa}*{ubicacion_text}\n\n"
            f"{tabla_modulos}\n"
            f"📈 *Promedio actual:* {promedio}/5.0\n"
            f"⚠️ *Fallas acumuladas:* {total_fallas}\n"
            f"\n💡 Recuerda: se requiere mínimo 75% de asistencia para certificación."
            f"{riesgo_msg}"
        )

    logger.info(f"[CONSULTA_NOTAS] Reporte generado para {name}: promedio={promedio}, fallas={total_fallas}")
    return {"messages": [AIMessage(content=msg)]}
