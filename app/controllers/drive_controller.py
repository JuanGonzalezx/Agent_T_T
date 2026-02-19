import io
from flask import Blueprint, request, jsonify, current_app
from app import google_drive_service, db_handler, sync_service
from app.utils.data_normalizer import normalize_phone_column, clean_phone_numbers, add_tracking_columns, validate_dataframe, map_column_aliases, concatenate_name_columns

drive_bp = Blueprint('drive', __name__)

@drive_bp.route('/google/upload', methods=['POST'])
def upload_from_google():
    """Procesa archivo de Drive, guarda en BD y configura Sync."""
    try:
        data = request.get_json() or {}
        file_id = data.get('fileId') or data.get('file_id')
        access_token = data.get('accessToken') or data.get('access_token')
        
        if not file_id or not access_token:
            return jsonify({'success': False, 'error': 'fileId y accessToken requeridos'}), 400
        
        current_app.logger.info(f"[DRIVE] Procesando archivo: {file_id}")
        
        # 1. Metadata
        success, metadata, error = google_drive_service.get_file_metadata(file_id, access_token)
        if not success: return jsonify({'success': False, 'error': error}), 400
        
        mime_type = metadata.get('mimeType', '')
        file_name = metadata.get('name', file_id)
        is_sheet = mime_type == 'application/vnd.google-apps.spreadsheet'
        
        # 2. Descargar y Parsear
        success, content, error = google_drive_service.download_file_content(file_id, access_token, is_sheet)
        if not success: return jsonify({'success': False, 'error': error}), 400
        
        success, df, error = google_drive_service.parse_file_content(content)
        if not success or df.empty: return jsonify({'success': False, 'error': error or 'Archivo vacío'}), 400
        
        # 3. Normalizar
        success, df, error = normalize_phone_column(df)
        if not success: return jsonify({'success': False, 'error': error}), 400
        
        df = clean_phone_numbers(df)
        df = map_column_aliases(df)
        df = concatenate_name_columns(df)
        df = add_tracking_columns(df)
        
        # 4. Validar
        valid, msg = validate_dataframe(df)
        if not valid: return jsonify({'success': False, 'error': msg}), 400
        
        # 5. Guardar en BD (Turso/SQLite)
        # 5a. Crear/actualizar bootcamps con nuevo esquema normalizado
        bootcamp_ids = df['bootcamp_id'].dropna().unique() if 'bootcamp_id' in df.columns else []
        bootcamp_id_map = {}  # codigo -> id (integer FK)
        for bid in bootcamp_ids:
            row = df[df['bootcamp_id'] == bid].iloc[0]
            db_handler.insert_or_update_bootcamp(
                codigo=str(bid),
                nombre=str(row.get('bootcamp_nombre', bid)),
                modalidad=str(row.get('modalidad', '')),
                horario=str(row.get('horario', '')),
                lugar=str(row.get('lugar', '')),
                fecha_inicio_ingles=str(row.get('ingles_inicio', row.get('fecha_inicio_ingles', ''))),
                fecha_fin_ingles=str(row.get('ingles_fin', row.get('fecha_fin_ingles', ''))),
                fecha_inicio_tecnica=str(row.get('inicio_formacion', row.get('fecha_inicio_tecnica', '')))
            )
            # Obtener el ID numérico del bootcamp recién creado
            bc = db_handler.get_bootcamp_by_codigo(str(bid))
            if bc:
                bootcamp_id_map[str(bid)] = bc['id']

        # 5b. Crear/actualizar estudiantes
        # Solo campos del usuario; el sistema asigna opt_in=0 y estado_academico='INSCRITO' por defecto
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            bootcamp_codigo = str(row_dict.get('bootcamp_id', ''))
            estudiante_data = {
                'telefono_e164': row_dict.get('telefono_e164', ''),
                'nombre': row_dict.get('nombre', ''),
                'documento': row_dict.get('documento', ''),
                'email': row_dict.get('email', ''),
                'bootcamp_id': bootcamp_id_map.get(bootcamp_codigo),
            }
            db_handler.insert_or_update_estudiante(estudiante_data)

        # 6. Actualizar Drive (Crear columnas nuevas)
        update_success = False
        if is_sheet:
            update_success, _ = google_drive_service.update_google_sheet(file_id, access_token, df)
        elif mime_type == 'text/csv':
            update_success, _ = google_drive_service.update_csv_file(file_id, access_token, df)
        
        # 7. Configurar Sincronización Automática
        sync_service.set_current_file(file_id, access_token, mime_type)
        
        csv_output = io.StringIO()
        df.to_csv(csv_output, index=False)
        
        return jsonify({
            'success': True,
            'message': 'Procesado y Sincronizado',
            'total_rows': len(df),
            'csv_data': csv_output.getvalue(),
            'columns': df.columns.tolist()
        }), 200

    except Exception as e:
        current_app.logger.error(f"[DRIVE] Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@drive_bp.route('/sync/drive-manual', methods=['POST'])
def sync_drive_manual():
    """Fuerza sync manual."""
    try:
        sync_service.mark_pending()
        sync_service._sync_job()
        return jsonify({'success': True, 'message': 'Sync ejecutado'}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500