"""
Controlador de Citas.

Gestiona el módulo de agendamiento de citas:
- Configuración de horarios disponibles
- CRUD de citas
- Confirmación/rechazo con notificación por WhatsApp
"""

import logging
from flask import Blueprint, request, jsonify
from app import db_handler, whatsapp_service

cita_bp = Blueprint('citas', __name__)
logger = logging.getLogger(__name__)


# =================================================================
# HORARIOS DISPONIBLES
# =================================================================

@cita_bp.route('/horarios', methods=['GET'])
def get_horarios():
    """Lista todos los horarios disponibles configurados."""
    try:
        horarios = db_handler.get_horarios_disponibles()
        return jsonify({'success': True, 'horarios': horarios}), 200
    except Exception as e:
        logger.error(f"[CITAS] Error listando horarios: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@cita_bp.route('/horarios', methods=['POST'])
def create_horario():
    """
    Crea un nuevo slot de horario disponible.

    Body JSON:
        dia_semana (int): 0=Lunes ... 6=Domingo
        hora_inicio (str): "08:00"
        hora_fin (str): "12:00"
        duracion_minutos (int, optional): Duración de cada cita (default: 30)
        max_citas_simultaneas (int, optional): Máximo simultáneas (default: 1)
    """
    try:
        data = request.get_json() or {}
        dia = data.get('dia_semana')
        h_inicio = data.get('hora_inicio')
        h_fin = data.get('hora_fin')

        if dia is None or not h_inicio or not h_fin:
            return jsonify({
                'success': False,
                'error': 'dia_semana, hora_inicio y hora_fin son requeridos'
            }), 400

        success, result = db_handler.insert_horario_disponible(
            dia_semana=int(dia),
            hora_inicio=h_inicio,
            hora_fin=h_fin,
            duracion_minutos=int(data.get('duracion_minutos', 30)),
            max_citas=int(data.get('max_citas_simultaneas', 1))
        )

        if success:
            return jsonify({
                'success': True,
                'horario_id': result,
                'message': 'Horario creado correctamente'
            }), 201
        return jsonify({'success': False, 'error': result}), 400

    except Exception as e:
        logger.error(f"[CITAS] Error creando horario: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@cita_bp.route('/horarios/<int:horario_id>/toggle', methods=['PUT'])
def toggle_horario(horario_id):
    """Activa o desactiva un horario."""
    try:
        success, msg = db_handler.toggle_horario(horario_id)
        if success:
            return jsonify({'success': True, 'message': msg}), 200
        return jsonify({'success': False, 'error': msg}), 404
    except Exception as e:
        logger.error(f"[CITAS] Error toggling horario: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@cita_bp.route('/horarios/<int:horario_id>', methods=['DELETE'])
def delete_horario(horario_id):
    """Elimina un horario disponible."""
    try:
        success, msg = db_handler.delete_horario(horario_id)
        if success:
            return jsonify({'success': True, 'message': msg}), 200
        return jsonify({'success': False, 'error': msg}), 404
    except Exception as e:
        logger.error(f"[CITAS] Error eliminando horario: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =================================================================
# CITAS
# =================================================================

@cita_bp.route('', methods=['GET'])
@cita_bp.route('/', methods=['GET'])
def list_citas():
    """
    Lista todas las citas, opcionalmente filtradas por estado.

    Query params:
        estado (str, optional): PENDIENTE|CONFIRMADA|RECHAZADA|CANCELADA|COMPLETADA
    """
    try:
        estado = request.args.get('estado')
        if estado:
            citas = db_handler.get_citas_by_estado(estado.upper())
        else:
            citas = db_handler.get_all_citas()
        return jsonify({'success': True, 'citas': citas, 'total': len(citas)}), 200
    except Exception as e:
        logger.error(f"[CITAS] Error listando citas: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@cita_bp.route('/<int:cita_id>', methods=['GET'])
def get_cita(cita_id):
    """Obtiene el detalle de una cita."""
    try:
        cita = db_handler.get_cita_by_id(cita_id)
        if not cita:
            return jsonify({'success': False, 'error': 'Cita no encontrada'}), 404
        return jsonify({'success': True, 'cita': cita}), 200
    except Exception as e:
        logger.error(f"[CITAS] Error obteniendo cita: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@cita_bp.route('/<int:cita_id>/confirmar', methods=['PUT'])
def confirmar_cita(cita_id):
    """
    Confirma una cita y envía notificación por WhatsApp al estudiante.

    Body JSON (optional):
        notas_internas (str): Notas internas de la secretaria
    """
    try:
        cita = db_handler.get_cita_by_id(cita_id)
        if not cita:
            return jsonify({'success': False, 'error': 'Cita no encontrada'}), 404

        if cita.get('estado') != 'PENDIENTE':
            return jsonify({
                'success': False,
                'error': f"La cita ya tiene estado: {cita.get('estado')}"
            }), 400

        data = request.get_json() or {}
        notas = data.get('notas_internas', '')

        success, msg = db_handler.update_cita_estado(
            cita_id, 'CONFIRMADA', notas_internas=notas
        )

        if success:
            # Enviar WhatsApp de confirmación
            phone = cita.get('telefono_e164')
            nombre = cita.get('nombre', 'Estudiante')
            fecha = cita.get('fecha_cita', '')
            hora = cita.get('hora_cita', '')

            mensaje_wpp = (
                f"✅ *Cita Confirmada*\n\n"
                f"Hola {nombre}, tu cita ha sido *confirmada*.\n\n"
                f"📅 Fecha: *{fecha}*\n"
                f"🕐 Hora: *{hora}*\n"
                f"📝 Motivo: {cita.get('descripcion', 'N/A')}\n\n"
                f"Por favor, llega puntual. Si necesitas cancelar, "
                f"escríbenos por este medio con la palabra *cancelar cita*."
            )

            wpp_success, wpp_result = whatsapp_service.send_text_message(
                phone, mensaje_wpp
            )

            return jsonify({
                'success': True,
                'message': 'Cita confirmada y notificación enviada',
                'whatsapp_sent': wpp_success,
                'whatsapp_result': wpp_result
            }), 200

        return jsonify({'success': False, 'error': msg}), 400

    except Exception as e:
        logger.error(f"[CITAS] Error confirmando cita: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@cita_bp.route('/<int:cita_id>/rechazar', methods=['PUT'])
def rechazar_cita(cita_id):
    """
    Rechaza una cita y envía notificación por WhatsApp al estudiante.

    Body JSON:
        motivo_rechazo (str): Motivo del rechazo
    """
    try:
        cita = db_handler.get_cita_by_id(cita_id)
        if not cita:
            return jsonify({'success': False, 'error': 'Cita no encontrada'}), 404

        if cita.get('estado') != 'PENDIENTE':
            return jsonify({
                'success': False,
                'error': f"La cita ya tiene estado: {cita.get('estado')}"
            }), 400

        data = request.get_json() or {}
        motivo = data.get('motivo_rechazo', 'No disponible en el horario solicitado')

        success, msg = db_handler.update_cita_estado(
            cita_id, 'RECHAZADA', motivo_rechazo=motivo
        )

        if success:
            # Enviar WhatsApp de rechazo
            phone = cita.get('telefono_e164')
            nombre = cita.get('nombre', 'Estudiante')

            mensaje_wpp = (
                f"📋 *Actualización de tu Cita*\n\n"
                f"Hola {nombre}, lamentamos informarte que tu solicitud "
                f"de cita no pudo ser confirmada.\n\n"
                f"📝 Motivo: {motivo}\n\n"
                f"Puedes solicitar una nueva cita escribiendo *agendar cita* "
                f"o contactando a soporte."
            )

            wpp_success, wpp_result = whatsapp_service.send_text_message(
                phone, mensaje_wpp
            )

            return jsonify({
                'success': True,
                'message': 'Cita rechazada y notificación enviada',
                'whatsapp_sent': wpp_success,
                'whatsapp_result': wpp_result
            }), 200

        return jsonify({'success': False, 'error': msg}), 400

    except Exception as e:
        logger.error(f"[CITAS] Error rechazando cita: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@cita_bp.route('/stats', methods=['GET'])
def citas_stats():
    """Obtiene estadísticas generales de citas."""
    try:
        stats = db_handler.get_citas_stats()
        return jsonify({'success': True, 'stats': stats}), 200
    except Exception as e:
        logger.error(f"[CITAS] Error obteniendo estadísticas: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
