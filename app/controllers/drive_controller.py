import io
from flask import Blueprint, request, jsonify, current_app
from app import google_drive_service, db_handler, sync_service
from app.utils.data_normalizer import normalize_phone_column, clean_phone_numbers, add_tracking_columns, validate_dataframe

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
        df = add_tracking_columns(df)
        
        # 4. Validar
        valid, msg = validate_dataframe(df)
        if not valid: return jsonify({'success': False, 'error': msg}), 400
        
        # 5. Guardar en BD (Turso/SQLite)
        # (Aquí iría tu lógica de inserción detallada, simplificada por brevedad)
        # Asumimos que tienes el loop de inserción aquí como en tu app.py original...
        # ... [INSERTAR CÓDIGO DE LOOP DE INSERCIÓN AQUÍ] ...
        # Para mantener el ejemplo funcional, invocamos lo básico:
        bootcamp_ids = df['bootcamp_id'].dropna().unique()
        for bid in bootcamp_ids:
            row = df[df['bootcamp_id'] == bid].iloc[0]
            db_handler.insert_or_update_bootcamp(bid, row.get('bootcamp_nombre', ''))
            
        for _, row in df.iterrows():
            # Construye el diccionario estudiante_data completo aquí
            estudiante_data = row.to_dict() # Simplificado, ajusta a tu modelo exacto
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