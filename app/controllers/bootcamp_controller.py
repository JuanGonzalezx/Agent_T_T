from flask import Blueprint, jsonify
from app import db_handler

bootcamp_bp = Blueprint('bootcamps', __name__)

@bootcamp_bp.route('', methods=['GET'])
@bootcamp_bp.route('/', methods=['GET'])
def get_all():
    try:
        bootcamps = db_handler.get_all_bootcamps()
        return jsonify({'success': True, 'bootcamps': bootcamps}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bootcamp_bp.route('/delete/<bootcamp_id>', methods=['DELETE'])
def delete_bootcamp(bootcamp_id):
    try:
        success, msg = db_handler.delete_bootcamp(bootcamp_id)
        return jsonify({'success': success, 'message': msg}), 200 if success else 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bootcamp_bp.route('/clear-all', methods=['DELETE'])
def clear_all():
    try:
        success, msg = db_handler.clear_all_bootcamps()
        return jsonify({'success': success, 'message': msg}), 200 if success else 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500