"""
Controlador de Campañas.

Gestiona el ciclo de vida de campañas: crear, listar, agregar miembros,
enviar y consultar estadísticas. Soporta tipos: MATRICULA, EVENTO, INFO.
"""

import time
import json
import logging
from flask import Blueprint, request, jsonify, current_app
from app import whatsapp_service, db_handler

campaign_bp = Blueprint('campaigns', __name__)
logger = logging.getLogger(__name__)

# ─── Plantillas por defecto según tipo de campaña ───
TEMPLATE_DEFAULTS = {
    'MATRICULA': {'plantilla': 'prueba_matricula', 'language': 'es'},
    'EVENTO': {'plantilla': 'confirmacion_evento_quindio', 'language': 'es_CO'},
    'INFO': {'plantilla': 'recordatorio_presencial', 'language': 'es'},
    'CAPTACION': {'plantilla': 'mensaje_interesados', 'language': 'es'},
}

# Catálogo de plantillas INFO disponibles para recordatorios/anuncios
INFO_TEMPLATES = {
    'recordatorio_presencial': {
        'language': 'es',
        'descripcion': 'Recordatorio inicio bootcamp presencial',
        'params': ['nombre', 'bootcamp_nombre', 'fecha_inicio_tecnica', 'horario', 'lugar'],
    },
    'recordatorio_virtual': {
        'language': 'es',
        'descripcion': 'Recordatorio inicio bootcamp virtual',
        'params': ['nombre', 'bootcamp_nombre', 'fecha_inicio_tecnica', 'horario', 'link_plataforma'],
    },
    'mensaje_interesados': {
        'language': 'es',
        'descripcion': 'Mensaje para captación de interesados',
        'params': ['nombre'],
    },
}

LINK_PLATAFORMA = 'https://talentotech2.com.co/campus'


@campaign_bp.route('/templates', methods=['GET'])
def get_templates():
    """
    Devuelve el mapeo de tipos de campaña → plantilla de Meta por defecto.
    El frontend lo usa para preseleccionar la plantilla al elegir tipo.
    """
    tipos = [
        {'tipo': 'MATRICULA', 'plantilla': TEMPLATE_DEFAULTS['MATRICULA']['plantilla'], 'language': TEMPLATE_DEFAULTS['MATRICULA']['language'], 'descripcion': 'Confirmación de matrícula'},
        {'tipo': 'EVENTO', 'plantilla': TEMPLATE_DEFAULTS['EVENTO']['plantilla'], 'language': TEMPLATE_DEFAULTS['EVENTO']['language'], 'descripcion': 'Confirmación de evento'},
        {'tipo': 'INFO', 'plantilla': TEMPLATE_DEFAULTS['INFO']['plantilla'], 'language': TEMPLATE_DEFAULTS['INFO']['language'], 'descripcion': 'Recordatorio / Anuncio'},
        {'tipo': 'CAPTACION', 'plantilla': TEMPLATE_DEFAULTS['CAPTACION']['plantilla'], 'language': TEMPLATE_DEFAULTS['CAPTACION']['language'], 'descripcion': 'Captación de interesados'},
    ]
    # Incluir catálogo de plantillas INFO disponibles
    info_templates = [
        {'plantilla': k, 'language': v['language'], 'descripcion': v['descripcion'], 'params': v['params']}
        for k, v in INFO_TEMPLATES.items()
    ]
    return jsonify({'success': True, 'templates': tipos, 'info_templates': info_templates}), 200


@campaign_bp.route('', methods=['POST'])
def create_campaign():
    """
    Crea una nueva campaña.
    
    Body JSON:
        nombre (str): Nombre de la campaña
        tipo (str): MATRICULA | EVENTO | INFO
        plantilla_whatsapp (str, optional): Nombre del template en Meta
        bootcamp_objetivo_id (str, optional): Filtro por bootcamp
    """
    try:
        data = request.get_json() or {}
        nombre = data.get('nombre')
        tipo = data.get('tipo')
        
        if not nombre or not tipo:
            return jsonify({'success': False, 'error': 'nombre y tipo son requeridos'}), 400
        
        # Sanitizar bootcamp_objetivo_id: convertir a int o None
        raw_bootcamp_id = data.get('bootcamp_objetivo_id')
        bootcamp_objetivo_id = None
        if raw_bootcamp_id not in (None, '', 0, '0'):
            try:
                bootcamp_objetivo_id = int(raw_bootcamp_id)
            except (ValueError, TypeError):
                bootcamp_objetivo_id = None

        success, result = db_handler.insert_campana(
            nombre=nombre,
            tipo=tipo,
            plantilla_whatsapp=data.get('plantilla_whatsapp', ''),
            bootcamp_objetivo_id=bootcamp_objetivo_id
        )
        
        if success:
            return jsonify({
                'success': True,
                'campana_id': result,
                'message': f'Campaña "{nombre}" creada con ID {result}'
            }), 201
        return jsonify({'success': False, 'error': result}), 400
        
    except Exception as e:
        logger.error(f"[CAMPAIGN] Error creando campaña: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@campaign_bp.route('', methods=['GET'])
def list_campaigns():
    """Lista todas las campañas."""
    try:
        campanas = db_handler.get_all_campanas()
        return jsonify({'success': True, 'campanas': campanas, 'total': len(campanas)}), 200
    except Exception as e:
        logger.error(f"[CAMPAIGN] Error listando campañas: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@campaign_bp.route('/<int:campana_id>', methods=['GET'])
def get_campaign(campana_id):
    """Obtiene una campaña por ID con sus estadísticas."""
    try:
        campana = db_handler.get_campana_by_id(campana_id)
        if not campana:
            return jsonify({'success': False, 'error': 'Campaña no encontrada'}), 404
        
        stats = db_handler.get_campana_stats(campana_id)
        return jsonify({'success': True, 'campana': campana, 'stats': stats}), 200
    except Exception as e:
        logger.error(f"[CAMPAIGN] Error obteniendo campaña: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@campaign_bp.route('/<int:campana_id>/members', methods=['POST'])
def add_members(campana_id):
    """
    Agrega miembros a una campaña.
    
    Duplicados se ignoran automáticamente (UNIQUE constraint en DB).
    
    Body JSON opción 1 (por IDs):
        estudiante_ids (list[int]): IDs de estudiantes
        variables_contexto (list[str], optional): JSON strings por estudiante
    
    Body JSON opción 2 (por bootcamp):
        bootcamp_id (str): Agrega todos los estudiantes de este bootcamp
        
    Body JSON opción 3 (todos, filtrado inteligente):
        all_opt_in (bool): True para agregar estudiantes.
            - Para MATRICULA/EVENTO: solo agrega los que NO hayan recibido
              una campaña del mismo tipo (evita duplicados entre campañas).
            - Para INFO: agrega TODOS (notificaciones pueden repetirse).
    """
    try:
        campana = db_handler.get_campana_by_id(campana_id)
        if not campana:
            return jsonify({'success': False, 'error': 'Campaña no encontrada'}), 404
        
        data = request.get_json() or {}
        estudiante_ids = []
        variables_list = data.get('variables_contexto', [])
        tipo_campana = campana.get('tipo', '').upper()
        
        if 'estudiante_ids' in data:
            # Opción 1: IDs directos (selección manual desde el panel)
            estudiante_ids = [int(x) for x in data['estudiante_ids']]
            
        elif 'bootcamp_id' in data:
            # Opción 2: Por bootcamp (con filtro opcional por estado_academico)
            bootcamp_id = data['bootcamp_id']
            estado_filtro = data.get('estado_academico_filtro')
            if estado_filtro:
                estudiantes = db_handler.get_estudiantes_by_bootcamp_and_estado(bootcamp_id, estado_filtro)
            else:
                estudiantes = db_handler.get_estudiantes_by_bootcamp(bootcamp_id)
            estudiante_ids = [int(e['id']) for e in estudiantes if e.get('id')]
            
        elif data.get('all_opt_in'):
            # Opción 3: Todos — con filtro inteligente según tipo
            if tipo_campana == 'INFO':
                # INFO (notificaciones) → se puede enviar a TODOS
                estudiantes = db_handler.get_estudiantes_opt_in()
            else:
                # MATRICULA / EVENTO → solo a quienes NO hayan recibido
                # una campaña del mismo tipo con estado 'sent'
                estudiantes = db_handler.get_estudiantes_sin_campana_enviada(tipo_campana)
            estudiante_ids = [int(e['id']) for e in estudiantes if e.get('id')]
        else:
            return jsonify({
                'success': False, 
                'error': 'Proporciona estudiante_ids, bootcamp_id, o all_opt_in=true'
            }), 400
        
        if not estudiante_ids:
            return jsonify({
                'success': False,
                'error': 'No se encontraron estudiantes elegibles. '
                         'Posiblemente todos ya fueron enviados en otra campaña del mismo tipo.'
            }), 404
        
        success, msg = db_handler.insert_campana_miembros(
            campana_id, estudiante_ids, variables_list
        )
        
        if success:
            # Obtener conteo real post-inserción (duplicados fueron ignorados)
            total_actual = db_handler.count_miembros_campana(campana_id)
            return jsonify({
                'success': True,
                'message': msg,
                'total_miembros_campana': total_actual
            }), 200
        return jsonify({'success': False, 'error': msg}), 400
        
    except Exception as e:
        logger.error(f"[CAMPAIGN] Error agregando miembros: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@campaign_bp.route('/<int:campana_id>/send', methods=['POST'])
def send_campaign(campana_id):
    """
    Envía los mensajes de una campaña a todos los miembros pendientes.
    
    Body JSON (optional):
        language_code (str): Código de idioma (default: es)
        has_header_param (bool): Si la plantilla tiene parámetro en header
    """
    try:
        campana = db_handler.get_campana_by_id(campana_id)
        if not campana:
            return jsonify({'success': False, 'error': 'Campaña no encontrada'}), 404
        
        template_name = campana.get('plantilla_whatsapp', '')
        if not template_name:
            return jsonify({'success': False, 'error': 'Campaña sin plantilla configurada'}), 400
        
        data = request.get_json() or {}
        # Resolver language_code según tipo de campaña
        tipo = campana.get('tipo', 'MATRICULA').upper()
        default_lang = TEMPLATE_DEFAULTS.get(tipo, {}).get('language', 'es')
        language_code = data.get('language_code') or default_lang
        has_header_param = data.get('has_header_param', False)
        
        # Obtener miembros pendientes
        pendientes = db_handler.get_miembros_pendientes_envio(campana_id)
        
        if not pendientes:
            return jsonify({
                'success': True, 
                'message': 'No hay miembros pendientes de envío',
                'stats': db_handler.get_campana_stats(campana_id)
            }), 200
        
        logger.info(f"[CAMPAIGN] Enviando campaña {campana_id} ({template_name}) a {len(pendientes)} miembros")
        
        # Actualizar estado de campaña a SENDING
        db_handler.update_campana_estado(campana_id, 'SENDING')
        
        results = []
        delay = current_app.config.get('DELAY_SECONDS', 1.5)
        
        for i, miembro in enumerate(pendientes):
            phone = miembro.get('telefono_e164')
            if not phone:
                continue
            
            # Construir parámetros según variables_contexto o datos del estudiante
            params = _build_template_params(miembro, campana.get('tipo', ''), template_name)
            
            logger.info(f"[CAMPAIGN] Enviando a {phone} [{i+1}/{len(pendientes)}]")
            
            success, result = whatsapp_service.send_template_message(
                phone, template_name, params, language_code,
                has_header_param=has_header_param
            )
            
            # Actualizar estado del miembro
            miembro_id = miembro.get('miembro_id')
            status = 'sent' if success else 'error'
            db_handler.update_miembro_estado_envio(
                int(miembro_id), status, result if success else None
            )
            
            results.append({
                'phone': phone, 
                'success': success, 
                'result': result,
                'miembro_id': miembro_id
            })
            
            if i < len(pendientes) - 1:
                time.sleep(delay)
        
        # Actualizar estado de campaña
        db_handler.update_campana_estado(campana_id, 'COMPLETED')
        
        enviados = sum(1 for r in results if r['success'])
        errores = sum(1 for r in results if not r['success'])
        
        return jsonify({
            'success': True,
            'message': f'Campaña enviada: {enviados} exitosos, {errores} errores',
            'stats': {
                'processed': len(results),
                'sent': enviados,
                'errors': errores
            }
        }), 200
        
    except Exception as e:
        logger.error(f"[CAMPAIGN] Error enviando campaña: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@campaign_bp.route('/<int:campana_id>/stats', methods=['GET'])
def campaign_stats(campana_id):
    """Obtiene estadísticas detalladas de una campaña."""
    try:
        campana = db_handler.get_campana_by_id(campana_id)
        if not campana:
            return jsonify({'success': False, 'error': 'Campaña no encontrada'}), 404
        
        stats = db_handler.get_campana_stats(campana_id)
        return jsonify({'success': True, 'stats': stats}), 200
    except Exception as e:
        logger.error(f"[CAMPAIGN] Error obteniendo estadísticas: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@campaign_bp.route('/<int:campana_id>', methods=['DELETE'])
def delete_campaign(campana_id):
    """Elimina una campaña y todos sus miembros."""
    try:
        success, msg = db_handler.delete_campana(campana_id)
        if success:
            return jsonify({'success': True, 'message': msg}), 200
        return jsonify({'success': False, 'error': msg}), 404
    except Exception as e:
        logger.error(f"[CAMPAIGN] Error eliminando campaña: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def _build_template_params(miembro: dict, tipo_campana: str, plantilla: str = '') -> list:
    """
    Construye la lista de parámetros para la plantilla de WhatsApp.
    
    Si el miembro tiene variables_contexto (JSON), las usa.
    Si no, construye a partir de los datos del estudiante.
    
    Args:
        miembro: Diccionario con datos del miembro (JOIN estudiante + bootcamp).
        tipo_campana: Tipo de campaña (MATRICULA, EVENTO, INFO).
        plantilla: Nombre de la plantilla de WhatsApp (para INFO determina los params).
    """
    # Intentar usar variables_contexto si están definidas
    variables_raw = miembro.get('variables_contexto', '')
    if variables_raw and variables_raw.strip():
        try:
            variables = json.loads(variables_raw)
            if isinstance(variables, list):
                return variables
            elif isinstance(variables, dict):
                return list(variables.values())
        except (json.JSONDecodeError, TypeError):
            pass
    
    # Construir desde datos del estudiante según tipo de campaña
    if tipo_campana == 'MATRICULA':
        return [
            str(miembro.get('nombre', '')),
            str(miembro.get('modalidad', '')),
            str(miembro.get('bootcamp_nombre', '')),
            str(miembro.get('fecha_inicio_ingles', '')),
            str(miembro.get('fecha_fin_ingles', '')),
            str(miembro.get('fecha_inicio_tecnica', '')),
            str(miembro.get('horario', '')),
            str(miembro.get('lugar', ''))
        ]
    elif tipo_campana == 'EVENTO':
        return [
            str(miembro.get('nombre', ''))
        ]
    elif tipo_campana == 'CAPTACION':
        # Captación de interesados: solo nombre
        return [str(miembro.get('nombre', ''))]
    elif tipo_campana == 'INFO':
        # Buscar definición en el catálogo INFO_TEMPLATES
        tpl_config = INFO_TEMPLATES.get(plantilla)
        if tpl_config:
            params = []
            for field in tpl_config['params']:
                if field == 'link_plataforma':
                    params.append(LINK_PLATAFORMA)
                else:
                    params.append(str(miembro.get(field, '')))
            return params
        # Fallback: solo nombre si la plantilla no está en el catálogo
        return [str(miembro.get('nombre', ''))]
    
    # Fallback genérico
    return [str(miembro.get('nombre', ''))]
