"""
Nodo de agendamiento de citas vía WhatsApp.

Maneja 3 sub-flujos:
  1. Agendar cita: Pide descripción → muestra horarios → crea cita PENDIENTE
  2. Consultar estado: Busca citas del estudiante → muestra estado
  3. Cancelar cita: Confirma cancelación → actualiza estado

Costo de tokens: 0 (respuestas determinísticas)
"""

import re
import logging
from datetime import datetime, timedelta
from langchain_core.messages import AIMessage
from app.agent.state import AgentState

logger = logging.getLogger(__name__)

# Días de la semana en español
DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']


def citas_node(state: AgentState):
    """
    Nodo principal de gestión de citas desde WhatsApp.

    Detecta el sub-intent del usuario y responde apropiadamente.
    """
    from app import db_handler

    phone = state.get('phone', '')
    name = state.get('student_name', 'Estudiante')
    messages = state.get('messages', [])

    if not messages:
        return {"messages": [AIMessage(content="No recibí tu mensaje.")]}

    # Obtener texto del último mensaje
    last_message = messages[-1]
    if hasattr(last_message, 'content'):
        text = last_message.content.strip()
    elif isinstance(last_message, dict):
        text = last_message.get('content', '').strip()
    else:
        text = str(last_message).strip()

    text_lower = text.lower()

    logger.info(f"[CITAS] Procesando: '{text}' de {phone}")

    # ──────────────────────────────────────────────
    # Sub-intent: CANCELAR CITA
    # ──────────────────────────────────────────────
    cancelar_patterns = ['cancelar cita', 'cancelar mi cita', 'anular cita', 'no quiero la cita']
    if any(p in text_lower for p in cancelar_patterns):
        return _handle_cancelar_cita(db_handler, phone, name)

    # ──────────────────────────────────────────────
    # Sub-intent: CONSULTAR ESTADO DE CITA
    # ──────────────────────────────────────────────
    estado_patterns = ['estado de mi cita', 'mi cita', 'tengo cita', 'cómo va mi cita',
                       'como va mi cita', 'estado cita', 'ver mi cita', 'consultar cita']
    if any(p in text_lower for p in estado_patterns):
        return _handle_consultar_cita(db_handler, phone, name)

    # ──────────────────────────────────────────────
    # Sub-intent: AGENDAR NUEVA CITA
    # ──────────────────────────────────────────────
    # Si el mensaje contiene una descripción larga (>10 chars), es la solicitud directa
    # Si no, mostramos el menú de citas
    agendar_patterns = ['agendar cita', 'solicitar cita', 'pedir cita', 'necesito cita',
                        'quiero una cita', 'reservar cita', 'bienestar', 'cita psicolog',
                        'cita con', 'agendar', 'reunión', 'reunion']

    if any(p in text_lower for p in agendar_patterns):
        # Verificar si ya tiene una cita pendiente
        cita_pendiente = db_handler.get_cita_pendiente_by_phone(phone)
        if cita_pendiente:
            estado = cita_pendiente.get('estado', 'PENDIENTE')
            fecha = cita_pendiente.get('fecha_cita', 'N/A')
            hora = cita_pendiente.get('hora_cita', 'N/A')
            msg = (
                f"📋 Ya tienes una cita *{estado}*:\n\n"
                f"📅 Fecha: *{fecha}*\n"
                f"🕐 Hora: *{hora}*\n"
                f"📝 Motivo: {cita_pendiente.get('descripcion', 'N/A')}\n\n"
            )
            if estado == 'PENDIENTE':
                msg += "⏳ Estamos revisando tu solicitud. Te notificaremos pronto.\n\n"
            elif estado == 'CONFIRMADA':
                msg += "✅ Tu cita está confirmada. ¡No olvides asistir!\n\n"

            msg += "Si deseas cancelarla, escribe *cancelar cita*."
            return {"messages": [AIMessage(content=msg)]}

        # Mostrar horarios disponibles y pedir descripción
        return _handle_solicitar_cita(db_handler, phone, name)

    # ──────────────────────────────────────────────
    # MENSAJE CON DESCRIPCIÓN (flujo de solicitud en curso)
    # ──────────────────────────────────────────────
    # Si llega un texto que no matchea ningún pattern específico
    # y tiene más de 10 caracteres, intentamos crear la cita
    if len(text) > 10:
        return _handle_crear_cita_directa(db_handler, phone, name, text)

    # Default: menú de citas
    msg = (
        f"📅 *Módulo de Citas*\n\n"
        f"Hola{' ' + name if name != 'Estudiante' else ''}, "
        f"¿qué deseas hacer?\n\n"
        f"1️⃣ Escribe *agendar cita* + motivo\n"
        f"   Ej: _\"Agendar cita: necesito asesoría sobre mi matrícula\"_\n\n"
        f"2️⃣ Escribe *estado cita* para consultar\n\n"
        f"3️⃣ Escribe *cancelar cita* para anular\n"
    )
    return {"messages": [AIMessage(content=msg)]}


def _handle_solicitar_cita(db_handler, phone, name):
    """Muestra horarios disponibles e invita a describir el motivo."""
    horarios = db_handler.get_horarios_disponibles(solo_activos=True)

    if not horarios:
        msg = (
            "📅 *Agendar Cita*\n\n"
            "En este momento no hay horarios configurados para citas. 😕\n\n"
            "Por favor contacta directamente a la secretaría o "
            "intenta más tarde."
        )
        return {"messages": [AIMessage(content=msg)]}

    # Formatear horarios disponibles
    horarios_txt = ""
    dias_vistos = set()
    for h in horarios:
        dia = int(h.get('dia_semana', 0))
        dia_nombre = DIAS_SEMANA[dia] if 0 <= dia <= 6 else f"Día {dia}"
        if dia_nombre not in dias_vistos:
            dias_vistos.add(dia_nombre)
            h_inicio = h.get('hora_inicio', '')
            h_fin = h.get('hora_fin', '')
            horarios_txt += f"  📌 *{dia_nombre}*: {h_inicio} - {h_fin}\n"

    msg = (
        f"📅 *Agendar Cita*\n\n"
        f"Horarios disponibles:\n{horarios_txt}\n"
        f"Para agendar tu cita, envía un mensaje describiendo "
        f"brevemente el motivo.\n\n"
        f"📝 Ejemplo:\n"
        f"_\"Necesito asesoría sobre mi proceso de matrícula\"_\n\n"
        f"La secretaría revisará tu solicitud y te confirmará "
        f"la fecha y hora exacta. 👍"
    )
    return {"messages": [AIMessage(content=msg)]}


def _handle_crear_cita_directa(db_handler, phone, name, descripcion):
    """Crea una cita con la próxima fecha/hora disponible."""
    # Buscar el próximo slot disponible
    horarios = db_handler.get_horarios_disponibles(solo_activos=True)

    if not horarios:
        msg = (
            "No hay horarios disponibles en este momento. 😕\n"
            "Por favor contacta directamente a la secretaría."
        )
        return {"messages": [AIMessage(content=msg)]}

    # Calcular próxima fecha disponible
    hoy = datetime.now()
    fecha_cita = None
    hora_cita = None

    for dias_adelante in range(1, 15):  # Buscar en los próximos 14 días
        fecha_candidata = hoy + timedelta(days=dias_adelante)
        dia_semana = fecha_candidata.weekday()  # 0=Lunes

        for h in horarios:
            h_dia = int(h.get('dia_semana', -1))
            if h_dia == dia_semana and int(h.get('activo', 0)):
                fecha_cita = fecha_candidata.strftime('%Y-%m-%d')
                hora_cita = h.get('hora_inicio', '08:00')
                break

        if fecha_cita:
            break

    if not fecha_cita:
        msg = (
            "No encontré un horario disponible en los próximos días. 😕\n"
            "Por favor contacta directamente a la secretaría."
        )
        return {"messages": [AIMessage(content=msg)]}

    # Buscar estudiante_id (puede ser None si no está registrado)
    estudiante_id = None
    estudiantes = db_handler.get_estudiante_by_phone(phone)
    if estudiantes:
        est = estudiantes[0]
        est_id = est.get('id')
        if isinstance(est_id, dict):
            estudiante_id = int(est_id.get('value', 0))
        else:
            estudiante_id = int(est_id) if est_id else None

    # Crear la cita
    success, result = db_handler.insert_cita(
        estudiante_id=estudiante_id,
        telefono=phone,
        nombre=name if name != 'Estudiante' else phone,
        descripcion=descripcion,
        fecha_cita=fecha_cita,
        hora_cita=hora_cita
    )

    if success:
        # Formatear fecha legible
        fecha_obj = datetime.strptime(fecha_cita, '%Y-%m-%d')
        dia_nombre = DIAS_SEMANA[fecha_obj.weekday()]

        msg = (
            f"✅ *Solicitud de Cita Registrada*\n\n"
            f"👤 Nombre: *{name}*\n"
            f"📅 Fecha tentativa: *{dia_nombre} {fecha_cita}*\n"
            f"🕐 Hora tentativa: *{hora_cita}*\n"
            f"📝 Motivo: _{descripcion}_\n\n"
            f"⏳ Tu cita está *PENDIENTE* de confirmación.\n"
            f"La secretaría revisará disponibilidad y te notificará "
            f"por este medio.\n\n"
            f"Si necesitas cancelar, escribe *cancelar cita*."
        )
        logger.info(f"[CITAS] Cita #{result} creada para {phone}")
    else:
        msg = (
            "Hubo un problema al registrar tu cita. 😕\n"
            "Por favor intenta de nuevo en unos minutos."
        )
        logger.error(f"[CITAS] Error creando cita: {result}")

    return {"messages": [AIMessage(content=msg)]}


def _handle_consultar_cita(db_handler, phone, name):
    """Consulta las citas del estudiante."""
    citas = db_handler.get_citas_by_phone(phone)

    if not citas:
        msg = (
            f"No tienes citas registradas en este momento.\n\n"
            f"Si deseas agendar una, escribe *agendar cita*."
        )
        return {"messages": [AIMessage(content=msg)]}

    msg = f"📋 *Tus Citas*\n\n"

    estados_emoji = {
        'PENDIENTE': '⏳',
        'CONFIRMADA': '✅',
        'RECHAZADA': '❌',
        'CANCELADA': '🚫',
        'COMPLETADA': '✔️'
    }

    for i, cita in enumerate(citas[:5], 1):  # Máximo 5 citas
        estado = cita.get('estado', 'PENDIENTE')
        emoji = estados_emoji.get(estado, '📋')
        fecha = cita.get('fecha_cita', 'N/A')
        hora = cita.get('hora_cita', 'N/A')
        desc = cita.get('descripcion', 'Sin descripción')

        msg += (
            f"{emoji} *Cita #{cita.get('id', i)}*\n"
            f"   📅 {fecha} a las {hora}\n"
            f"   📝 {desc[:50]}{'...' if len(desc) > 50 else ''}\n"
            f"   Estado: *{estado}*\n"
        )
        if estado == 'RECHAZADA' and cita.get('motivo_rechazo'):
            msg += f"   💬 Motivo: {cita.get('motivo_rechazo')}\n"
        msg += "\n"

    msg += "Para cancelar una cita, escribe *cancelar cita*."

    return {"messages": [AIMessage(content=msg)]}


def _handle_cancelar_cita(db_handler, phone, name):
    """Cancela la cita pendiente o confirmada más reciente del estudiante."""
    cita = db_handler.get_cita_pendiente_by_phone(phone)

    if not cita:
        msg = (
            "No tienes citas pendientes o confirmadas para cancelar.\n\n"
            "Si deseas agendar una nueva, escribe *agendar cita*."
        )
        return {"messages": [AIMessage(content=msg)]}

    cita_id = cita.get('id')
    if isinstance(cita_id, dict):
        cita_id = int(cita_id.get('value', 0))
    else:
        cita_id = int(cita_id)

    success, msg_result = db_handler.cancelar_cita(cita_id)

    if success:
        msg = (
            f"🚫 *Cita Cancelada*\n\n"
            f"Tu cita del {cita.get('fecha_cita', '')} "
            f"a las {cita.get('hora_cita', '')} ha sido cancelada.\n\n"
            f"Si necesitas reagendar, escribe *agendar cita*."
        )
        logger.info(f"[CITAS] Cita #{cita_id} cancelada por {phone}")
    else:
        msg = (
            "No se pudo cancelar tu cita en este momento. 😕\n"
            "Por favor intenta de nuevo."
        )

    return {"messages": [AIMessage(content=msg)]}
