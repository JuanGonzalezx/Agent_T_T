from flask import Blueprint, request, jsonify, current_app
from app import db_handler

student_bp = Blueprint('students', __name__)

@student_bp.route('/estudiantes/all', methods=['GET'])
def get_all_estudiantes():
    try:
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        estudiantes, total = db_handler.get_all_estudiantes(limit, offset)
        return jsonify({'success': True, 'total': total, 'estudiantes': estudiantes}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@student_bp.route('/estudiantes/bootcamp/<bootcamp_id>', methods=['GET'])
def get_by_bootcamp(bootcamp_id):
    try:
        estudiantes = db_handler.get_estudiantes_by_bootcamp(bootcamp_id)
        return jsonify({'success': True, 'estudiantes': estudiantes}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@student_bp.route('/estudiantes/phone/<phone>', methods=['GET'])
def get_by_phone(phone):
    try:
        estudiantes = db_handler.get_estudiante_by_phone(phone)
        return jsonify({'success': True, 'estudiantes': estudiantes}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@student_bp.route('/estudiantes/update-field', methods=['PUT'])
def update_field():
    try:
        data = request.get_json()
        success, msg = db_handler.update_estudiante_field(data.get('telefono'), data.get('field'), data.get('value'))
        return jsonify({'success': success, 'message': msg}), 200 if success else 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@student_bp.route('/estudiantes/delete/<phone>', methods=['DELETE'])
def delete_student(phone):
    try:
        success, msg = db_handler.delete_estudiante(phone)
        return jsonify({'success': success, 'message': msg}), 200 if success else 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@student_bp.route('/contacts/stats', methods=['GET'])
@student_bp.route('/estadisticas', methods=['GET'])
def get_stats():
    """Obtiene estadísticas generales."""
    try:
        stats = db_handler.get_estadisticas()
        return jsonify({'success': True, 'stats': stats}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@student_bp.route('/contacts/pending', methods=['GET'])
def get_pending():
    """Obtiene pendientes de envío."""
    try:
        pending = db_handler.get_estudiantes_pendientes_envio()
        return jsonify({'success': True, 'contacts': pending}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500