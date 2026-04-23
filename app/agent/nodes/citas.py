"""
Nodo de agendamiento de citas vía WhatsApp.

Maneja 3 sub-flujos:
  1. Agendar cita: Muestra slots numerados → usuario elige → pide motivo → Gemini extrae → crea cita
  2. Consultar estado: Busca la cita activa del estudiante
  3. Cancelar cita: Cancela la cita activa

Regla clave: cada usuario solo puede tener UNA cita activa (PENDIENTE o CONFIRMADA).

Usa sesiones in-memory para mantener contexto entre mensajes y Gemini para
extraer el motivo limpio de mensajes del usuario.
"""

import logging
from datetime import datetime, timedelta
from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from app.agent.state import AgentState
from app.utils.gemini_logger import invoke_with_logging

logger = logging.getLogger(__name__)

DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
SLOT_EMOJIS = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣']

# ═══════════════════════════════════════════════════════════════
# SESIÓN IN-MEMORY
# ═══════════════════════════════════════════════════════════════
_cita_sessions = {}   # phone_clean -> {step, timestamp, extra}
SESSION_TTL_SECONDS = 300  # 5 minutos

# ═══════════════════════════════════════════════════════════════
# LLM para extracción de motivo
# ═══════════════════════════════════════════════════════════════
_cita_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    temperature=0.0,
    max_tokens=60,
    timeout=15,
    max_retries=1,
)


# ─── Utilidades de sesión ────────────────────────────────────

def _clean_phone(phone: str) -> str:
    return phone.replace('+', '').replace(' ', '').replace('-', '')


def has_active_cita_session(phone: str) -> bool:
    """Llamado por el router para decidir si el mensaje va al nodo citas."""
    phone_clean = _clean_phone(phone)
    session = _cita_sessions.get(phone_clean)
    if not session:
        return False
    elapsed = (datetime.now() - session['timestamp']).total_seconds()
    if elapsed > SESSION_TTL_SECONDS:
        del _cita_sessions[phone_clean]
        logger.info(f"[CITAS] Sesión expirada para {phone_clean}")
        return False
    return True


def _set_session(phone: str, step: str, extra: dict = None):
    phone_clean = _clean_phone(phone)
    _cita_sessions[phone_clean] = {
        'step': step,
        'timestamp': datetime.now(),
        'extra': extra or {}
    }
    logger.info(f"[CITAS] Sesión: {phone_clean} → {step}")


def _clear_session(phone: str):
    phone_clean = _clean_phone(phone)
    _cita_sessions.pop(phone_clean, None)
    logger.info(f"[CITAS] Sesión limpiada: {phone_clean}")


def _get_session(phone: str) -> dict:
    phone_clean = _clean_phone(phone)
    return _cita_sessions.get(phone_clean, {})


# ─── Detección de intención interna (más amplia) ─────────────

def _is_cancel_intent(text_lower: str) -> bool:
    """Detecta intención de cancelar con patterns amplios."""
    # "cancelar cita", "cancelar mi cita", "quisiera cancelar una cita",
    # "quiero cancelar", "me gustaria cancelar", etc.
    return 'cancelar' in text_lower


def _is_status_intent(text_lower: str) -> bool:
    """Detecta intención de consultar estado."""
    status_words = ['estado', 'consultar', 'ver mi', 'revisar',
                    'como va', 'cómo va', 'tengo cita',
                    'mi cita', 'ver cita', 'cuál es mi cita']
    return any(w in text_lower for w in status_words) and 'cita' in text_lower


# ─── Generación de slots ────────────────────────────────────

def _generate_slots(horarios: list) -> list:
    """
    A partir de la config de horarios, genera slots individuales
    con fecha concreta para los próximos 14 días.
    Retorna máximo 6 slots.
    """
    slots = []
    hoy = datetime.now()

    for dias_adelante in range(1, 15):
        fecha = hoy + timedelta(days=dias_adelante)
        dia_semana = fecha.weekday()  # 0=Lunes

        for h in horarios:
            h_dia = int(h.get('dia_semana', -1))
            if h_dia != dia_semana or not int(h.get('activo', 0)):
                continue

            h_inicio = h.get('hora_inicio', '08:00')
            h_fin = h.get('hora_fin', '12:00')
            duracion = int(h.get('duracion_minutos', 30))

            # Generar slots individuales dentro de la franja
            inicio_parts = h_inicio.split(':')
            fin_parts = h_fin.split(':')
            current_min = int(inicio_parts[0]) * 60 + int(inicio_parts[1])
            fin_min = int(fin_parts[0]) * 60 + int(fin_parts[1])

            while current_min + duracion <= fin_min and len(slots) < 6:
                hora = f"{current_min // 60:02d}:{current_min % 60:02d}"
                slots.append({
                    'dia': DIAS_SEMANA[dia_semana],
                    'fecha': fecha.strftime('%Y-%m-%d'),
                    'hora': hora,
                    'duracion': duracion,
                })
                current_min += duracion

        if len(slots) >= 6:
            break

    return slots


# ─── Extracción de motivo con Gemini ─────────────────────────

def _extract_motivo_with_llm(text: str) -> str:
    """Usa Gemini para extraer un motivo limpio y corto."""
    try:
        prompt = (
            "Del siguiente mensaje, extrae SOLO el motivo o razón "
            "por la que el estudiante quiere una cita. "
            "Responde en máximo 12 palabras, sin comillas. "
            "Ignora referencias a horarios, días u horas. "
            "Si no hay motivo claro, responde: Consulta general\n\n"
            f"Mensaje: \"{text}\"\n"
            "Motivo:"
        )
        response = invoke_with_logging(_cita_llm, prompt, context="CITAS_MOTIVO")
        motivo = response.content.strip().strip('"').strip("'").strip()
        # Limpieza extra
        motivo = motivo.replace("Motivo:", "").strip()
        if len(motivo) < 3 or motivo.lower() in ('ninguno', 'n/a', 'no hay'):
            motivo = "Consulta general"
        return motivo[:100]
    except Exception as e:
        logger.error(f"[CITAS] Error LLM motivo: {e}")
        # Fallback: intentar limpiar manualmente
        return text[:80] if len(text) > 5 else "Consulta general"


# ═══════════════════════════════════════════════════════════════
# NODO PRINCIPAL
# ═══════════════════════════════════════════════════════════════

def citas_node(state: AgentState):
    """
    Nodo principal. Detecta sub-intent y maneja flujo con sesiones.
    """
    from app import db_handler

    phone = state.get('phone', '')
    name = state.get('student_name', 'Estudiante')
    messages = state.get('messages', [])

    if not messages:
        return {"messages": [AIMessage(content="No recibí tu mensaje.")]}

    last_message = messages[-1]
    if hasattr(last_message, 'content'):
        text = last_message.content.strip()
    elif isinstance(last_message, dict):
        text = last_message.get('content', '').strip()
    else:
        text = str(last_message).strip()

    text_lower = text.lower()
    session = _get_session(phone)
    current_step = session.get('step', '')

    logger.info(f"[CITAS] '{text}' | phone={phone} | step={current_step}")

    # ──────────────────────────────────────────────
    # 1. CANCELAR (siempre se evalúa primero)
    # ──────────────────────────────────────────────
    if _is_cancel_intent(text_lower):
        _clear_session(phone)
        return _handle_cancelar(db_handler, phone, name)

    # ──────────────────────────────────────────────
    # 2. CONSULTAR ESTADO
    # ──────────────────────────────────────────────
    if _is_status_intent(text_lower):
        _clear_session(phone)
        return _handle_consultar(db_handler, phone, name)

    # ──────────────────────────────────────────────
    # 3. SESIÓN: Esperando selección de slot
    # ──────────────────────────────────────────────
    if current_step == 'awaiting_slot':
        slots = session.get('extra', {}).get('slots', [])
        return _handle_slot_selection(db_handler, phone, name, text, slots)

    # ──────────────────────────────────────────────
    # 4. SESIÓN: Esperando motivo
    # ──────────────────────────────────────────────
    if current_step == 'awaiting_motivo':
        slot = session.get('extra', {}).get('selected_slot', {})
        _clear_session(phone)
        motivo = _extract_motivo_with_llm(text)
        return _create_cita(db_handler, phone, name, slot, motivo)

    # ──────────────────────────────────────────────
    # 5. AGENDAR (intento nuevo o genérico)
    # ──────────────────────────────────────────────
    # Constraint: solo 1 cita activa por usuario
    cita_existente = db_handler.get_cita_pendiente_by_phone(phone)
    if cita_existente:
        return _show_existing_cita(cita_existente)

    # Mostrar slots disponibles
    return _show_slots(db_handler, phone)


# ═══════════════════════════════════════════════════════════════
# HANDLERS
# ═══════════════════════════════════════════════════════════════

def _show_existing_cita(cita: dict) -> dict:
    """Muestra la cita activa del usuario (constraint 1 cita)."""
    estado = cita.get('estado', 'PENDIENTE')
    fecha = cita.get('fecha_cita', 'N/A')
    hora = cita.get('hora_cita', 'N/A')
    desc = cita.get('descripcion', 'N/A')

    msg = (
        f"📋 Ya tienes una cita *{estado}*:\n\n"
        f"📅 Fecha: *{fecha}*\n"
        f"🕐 Hora: *{hora}*\n"
        f"📝 Motivo: _{desc}_\n\n"
    )
    if estado == 'PENDIENTE':
        msg += "⏳ Estamos revisando tu solicitud. Te notificaremos pronto.\n\n"
    elif estado == 'CONFIRMADA':
        msg += "✅ Tu cita está confirmada. ¡No olvides asistir!\n\n"
    msg += "Para cancelarla, escribe *cancelar cita*."

    return {"messages": [AIMessage(content=msg)]}


def _show_slots(db_handler, phone: str) -> dict:
    """Muestra slots numerados para que el usuario elija."""
    horarios = db_handler.get_horarios_disponibles(solo_activos=True)

    if not horarios:
        return {"messages": [AIMessage(content=(
            "📅 *Agendar Cita*\n\n"
            "No hay horarios disponibles en este momento. 😕\n"
            "Contacta directamente a la secretaría."
        ))]}

    slots = _generate_slots(horarios)

    if not slots:
        return {"messages": [AIMessage(content=(
            "📅 *Agendar Cita*\n\n"
            "No hay horarios disponibles en los próximos días. 😕\n"
            "Contacta directamente a la secretaría."
        ))]}

    # Formatear slots numerados
    slots_txt = ""
    for i, s in enumerate(slots):
        slots_txt += f"{SLOT_EMOJIS[i]} *{s['dia']} {s['fecha']}* a las *{s['hora']}*\n"

    # Marcar sesión
    _set_session(phone, 'awaiting_slot', {'slots': slots})

    msg = (
        f"📅 *Agendar Cita*\n\n"
        f"Horarios disponibles:\n{slots_txt}\n"
        f"Envía el *número* del horario que prefieras.\n"
        f"Ej: *1*"
    )
    return {"messages": [AIMessage(content=msg)]}


def _handle_slot_selection(db_handler, phone: str, name: str,
                           text: str, slots: list) -> dict:
    """Procesa la selección del slot por número."""
    # Extraer número del mensaje
    slot_num = None
    text_stripped = text.strip()

    for i in range(1, min(7, len(slots) + 1)):
        if str(i) in text_stripped:
            slot_num = i
            break

    if slot_num is None or slot_num > len(slots):
        # No reconocido → mostrar slots de nuevo
        slots_txt = ""
        for i, s in enumerate(slots):
            slots_txt += f"{SLOT_EMOJIS[i]} *{s['dia']} {s['fecha']}* a las *{s['hora']}*\n"

        _set_session(phone, 'awaiting_slot', {'slots': slots})
        msg = (
            f"⚠️ No reconocí tu selección.\n\n"
            f"Elige un horario:\n{slots_txt}\n"
            f"Envía solo el *número* (1-{len(slots)})"
        )
        return {"messages": [AIMessage(content=msg)]}

    selected = slots[slot_num - 1]

    # Pedir motivo
    _set_session(phone, 'awaiting_motivo', {'selected_slot': selected})

    msg = (
        f"📌 Seleccionaste: *{selected['dia']} {selected['fecha']}* "
        f"a las *{selected['hora']}*\n\n"
        f"Ahora, describe brevemente el *motivo* de tu cita.\n\n"
        f"📝 Ej: _\"Necesito asesoría sobre mi proceso de matrícula\"_"
    )
    return {"messages": [AIMessage(content=msg)]}


def _create_cita(db_handler, phone: str, name: str,
                 slot: dict, motivo: str) -> dict:
    """Crea la cita en la base de datos."""
    # Buscar estudiante_id
    estudiante_id = None
    try:
        estudiantes = db_handler.get_estudiante_by_phone(phone)
        if estudiantes:
            est = estudiantes[0]
            est_id = est.get('id')
            if isinstance(est_id, dict):
                estudiante_id = int(est_id.get('value', 0))
            else:
                estudiante_id = int(est_id) if est_id else None
    except Exception:
        pass

    success, result = db_handler.insert_cita(
        estudiante_id=estudiante_id,
        telefono=phone,
        nombre=name if name != 'Estudiante' else phone,
        descripcion=motivo,
        fecha_cita=slot.get('fecha', ''),
        hora_cita=slot.get('hora', ''),
        duracion=slot.get('duracion', 30)
    )

    if success:
        msg = (
            f"✅ *Solicitud de Cita Registrada*\n\n"
            f"👤 Nombre: *{name}*\n"
            f"📅 Fecha: *{slot['dia']} {slot['fecha']}*\n"
            f"🕐 Hora: *{slot['hora']}*\n"
            f"📝 Motivo: _{motivo}_\n\n"
            f"⏳ Tu cita está *PENDIENTE* de confirmación.\n"
            f"La secretaría te notificará por este medio.\n\n"
            f"Para cancelar, escribe *cancelar cita*."
        )
        logger.info(f"[CITAS] Cita #{result} creada para {phone}")
    else:
        msg = (
            "Hubo un problema al registrar tu cita. 😕\n"
            "Intenta de nuevo en unos minutos."
        )
        logger.error(f"[CITAS] Error: {result}")

    return {"messages": [AIMessage(content=msg)]}


def _handle_consultar(db_handler, phone: str, name: str) -> dict:
    """Consulta la cita activa del estudiante."""
    cita = db_handler.get_cita_pendiente_by_phone(phone)

    if not cita:
        # Buscar historial completo
        citas_all = db_handler.get_citas_by_phone(phone)
        if not citas_all:
            return {"messages": [AIMessage(content=(
                "No tienes citas registradas.\n\n"
                "Para agendar una, escribe *agendar cita*."
            ))]}

        # Mostrar la más reciente
        cita = citas_all[0]

    estado = cita.get('estado', 'PENDIENTE')
    estados_emoji = {
        'PENDIENTE': '⏳', 'CONFIRMADA': '✅', 'RECHAZADA': '❌',
        'CANCELADA': '🚫', 'COMPLETADA': '✔️'
    }
    emoji = estados_emoji.get(estado, '📋')

    msg = (
        f"📋 *Tu Cita*\n\n"
        f"{emoji} Estado: *{estado}*\n"
        f"📅 Fecha: *{cita.get('fecha_cita', 'N/A')}*\n"
        f"🕐 Hora: *{cita.get('hora_cita', 'N/A')}*\n"
        f"📝 Motivo: _{cita.get('descripcion', 'N/A')}_\n"
    )

    if estado == 'RECHAZADA' and cita.get('motivo_rechazo'):
        msg += f"💬 Motivo rechazo: {cita.get('motivo_rechazo')}\n"

    if estado in ('PENDIENTE', 'CONFIRMADA'):
        msg += "\nPara cancelar, escribe *cancelar cita*."
    else:
        msg += "\nPara agendar una nueva, escribe *agendar cita*."

    return {"messages": [AIMessage(content=msg)]}


def _handle_cancelar(db_handler, phone: str, name: str) -> dict:
    """Cancela la cita activa (PENDIENTE o CONFIRMADA)."""
    cita = db_handler.get_cita_pendiente_by_phone(phone)

    if not cita:
        return {"messages": [AIMessage(content=(
            "No tienes citas pendientes o confirmadas para cancelar.\n\n"
            "Para agendar una nueva, escribe *agendar cita*."
        ))]}

    cita_id = cita.get('id')
    if isinstance(cita_id, dict):
        cita_id = int(cita_id.get('value', 0))
    else:
        cita_id = int(cita_id)

    success, _ = db_handler.cancelar_cita(cita_id)

    if success:
        msg = (
            f"🚫 *Cita Cancelada*\n\n"
            f"Tu cita del *{cita.get('fecha_cita', '')}* "
            f"a las *{cita.get('hora_cita', '')}* ha sido cancelada.\n\n"
            f"Si deseas reagendar, escribe *agendar cita*."
        )
        logger.info(f"[CITAS] Cita #{cita_id} cancelada por {phone}")
    else:
        msg = (
            "No se pudo cancelar tu cita en este momento. 😕\n"
            "Intenta de nuevo."
        )

    return {"messages": [AIMessage(content=msg)]}
