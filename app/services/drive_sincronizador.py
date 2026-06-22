"""
Sincronizador de datos académicos desde Google Drive.

Lee las plantillas de seguimiento de Regionalización ("U en tu Pueblo")
y carga notas/fallas en la base de datos Turso.

Estructura de Drive:
    Año → Subregiones → Municipio → Técnicos → Malla → Excel (Plantilla de seguimiento)

Estructura del Excel (Plantilla Juan David):
    - Filas 1-2: Encabezados institucionales (SKIP)
    - Fila 3: Nombres de módulos (cada 2 columnas desde col D)
    - Fila 4: Nombres de docentes (cada 2 columnas desde col D)
    - Fila 5+: Datos de estudiantes
      - Col A: Número (índice)
      - Col B: Nombre completo
      - Col C: Cédula/Documento
      - Col D en adelante: [Nota_Mod1, Fallas_Mod1, Nota_Mod2, Fallas_Mod2, ...]
"""

import os
import logging
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


def parse_plantilla_regionalizacion(
    excel_path: str,
    drive_source: str = "",
    header_rows: int = 2,
    col_nombre: int = 1,
    col_documento: int = 2,
    col_datos_inicio: int = 3
) -> List[Dict[str, Any]]:
    """
    Lee la plantilla de seguimiento de Regionalización y extrae notas/fallas.

    Args:
        excel_path: Ruta al archivo Excel descargado
        drive_source: Ruta original en Drive (para trazabilidad)
        header_rows: Número de filas de encabezado institucional a saltar (default: 2)
        col_nombre: Índice de columna del nombre (0-indexed, default: 1 = col B)
        col_documento: Índice de columna del documento (0-indexed, default: 2 = col C)
        col_datos_inicio: Índice de inicio de datos de módulos (0-indexed, default: 3 = col D)

    Returns:
        Lista de dicts con: nombre, documento, modulo_numero, modulo_nombre,
        docente, nota, fallas, drive_source
    """
    try:
        df = pd.read_excel(excel_path, header=None, engine='openpyxl')
    except Exception as e:
        logger.error(f"[PARSER] Error leyendo Excel {excel_path}: {e}")
        return []

    if len(df) < header_rows + 3:
        logger.warning(f"[PARSER] Excel demasiado corto ({len(df)} filas): {excel_path}")
        return []

    # ─── 1. Extraer nombres de módulos y docentes ───
    fila_modulos_idx = header_rows      # Fila de nombres de módulos
    fila_docentes_idx = header_rows + 1  # Fila de nombres de docentes
    fila_datos_inicio = header_rows + 2  # Primera fila de datos de estudiantes

    fila_modulos = df.iloc[fila_modulos_idx] if fila_modulos_idx < len(df) else pd.Series()
    fila_docentes = df.iloc[fila_docentes_idx] if fila_docentes_idx < len(df) else pd.Series()

    modulos = []
    modulo_num = 1
    for i in range(col_datos_inicio, len(fila_modulos), 2):
        # Columna par = Nota, columna impar = Fallas
        nombre_mod = _safe_str(fila_modulos.iloc[i]) if i < len(fila_modulos) else None
        if not nombre_mod:
            nombre_mod = f"Módulo {modulo_num}"

        docente = _safe_str(fila_docentes.iloc[i]) if i < len(fila_docentes) else "Sin asignar"

        modulos.append({
            "numero": modulo_num,
            "nombre": nombre_mod,
            "docente": docente if docente else "Sin asignar",
            "col_nota": i,
            "col_fallas": i + 1
        })
        modulo_num += 1

    if not modulos:
        logger.warning(f"[PARSER] No se encontraron módulos en: {excel_path}")
        return []

    logger.info(f"[PARSER] {len(modulos)} módulos detectados en {excel_path}")

    # ─── 2. Iterar estudiantes ───
    registros = []
    estudiantes_procesados = 0

    for row_idx in range(fila_datos_inicio, len(df)):
        row = df.iloc[row_idx]

        nombre = _safe_str(row.iloc[col_nombre]) if col_nombre < len(row) else None
        documento = _safe_str(row.iloc[col_documento]) if col_documento < len(row) else None

        # Saltar filas vacías o de resumen
        if not nombre:
            continue

        # Limpiar documento (quitar puntos, comas, espacios)
        if documento:
            documento = documento.replace('.', '').replace(',', '').replace(' ', '').strip()

        estudiantes_procesados += 1

        # ─── 3. Extraer notas y fallas por módulo ───
        for mod in modulos:
            nota = _safe_float(row.iloc[mod["col_nota"]]) if mod["col_nota"] < len(row) else None
            fallas = _safe_int(row.iloc[mod["col_fallas"]]) if mod["col_fallas"] < len(row) else 0

            registros.append({
                "nombre": nombre,
                "documento": documento,
                "modulo_numero": mod["numero"],
                "modulo_nombre": mod["nombre"],
                "docente": mod["docente"],
                "nota": nota,
                "fallas": fallas,
                "drive_source": drive_source
            })

    logger.info(
        f"[PARSER] Procesados: {estudiantes_procesados} estudiantes, "
        f"{len(registros)} registros de rendimiento desde {excel_path}"
    )
    return registros


def sincronizar_excel_a_db(
    excel_path: str,
    db_handler,
    programa_codigo: str = None,
    drive_source: str = "",
    **parser_kwargs
) -> Dict[str, Any]:
    """
    Pipeline completo: Lee Excel → Parsea → UPSERT en DB.

    Args:
        excel_path: Ruta al archivo Excel
        db_handler: Instancia de DatabaseHandler
        programa_codigo: Código del programa/bootcamp asociado (para vincular estudiantes)
        drive_source: Ruta original en Drive
        **parser_kwargs: Args adicionales para parse_plantilla_regionalizacion

    Returns:
        Dict con estadísticas: estudiantes_nuevos, estudiantes_actualizados,
        rendimiento_ok, rendimiento_error
    """
    stats = {
        "estudiantes_nuevos": 0,
        "estudiantes_actualizados": 0,
        "rendimiento_ok": 0,
        "rendimiento_error": 0,
        "errores": []
    }

    # 1. Parsear el Excel
    registros = parse_plantilla_regionalizacion(excel_path, drive_source, **parser_kwargs)

    if not registros:
        stats["errores"].append("No se encontraron registros en el Excel")
        return stats

    # 2. Obtener bootcamp_id si se proporcionó código
    bootcamp_id = None
    if programa_codigo:
        bootcamp = db_handler.get_bootcamp_by_codigo(programa_codigo)
        if bootcamp:
            bootcamp_id = int(bootcamp.get('id', 0))

    # 3. Agrupar registros por estudiante (nombre + documento)
    estudiantes_map = {}  # key: documento -> registros
    for reg in registros:
        key = reg.get('documento') or reg.get('nombre', 'UNKNOWN')
        if key not in estudiantes_map:
            estudiantes_map[key] = {
                "nombre": reg["nombre"],
                "documento": reg.get("documento"),
                "modulos": []
            }
        estudiantes_map[key]["modulos"].append(reg)

    # 4. Procesar cada estudiante
    for key, est_data in estudiantes_map.items():
        documento = est_data.get("documento")
        nombre = est_data["nombre"]

        # Buscar estudiante existente por documento
        estudiante = None
        if documento:
            estudiante = db_handler.get_estudiante_by_documento(documento)

        if estudiante:
            estudiante_id = int(estudiante.get('id'))
            stats["estudiantes_actualizados"] += 1
        else:
            # Crear estudiante nuevo (sin teléfono por ahora)
            # Se le asignará teléfono cuando se vincule manualmente o por SIA
            telefono_placeholder = f"+57000{documento}" if documento else f"+5700000{stats['estudiantes_nuevos']}"
            ok, result = db_handler.insert_or_update_estudiante({
                "telefono_e164": telefono_placeholder,
                "nombre": nombre,
                "documento": documento or "",
                "bootcamp_id": bootcamp_id,
                "estado_academico": "INSCRITO"
            })
            if ok and result:
                estudiante_id = int(result)
                stats["estudiantes_nuevos"] += 1
            else:
                stats["errores"].append(f"Error creando estudiante {nombre}: {result}")
                continue

        # 5. UPSERT rendimiento por módulo
        for mod in est_data["modulos"]:
            ok, msg = db_handler.upsert_rendimiento(
                estudiante_id=estudiante_id,
                modulo_numero=mod["modulo_numero"],
                modulo_nombre=mod.get("modulo_nombre"),
                docente=mod.get("docente"),
                nota=mod.get("nota"),
                fallas=mod.get("fallas", 0),
                drive_source=mod.get("drive_source", "")
            )
            if ok:
                stats["rendimiento_ok"] += 1
            else:
                stats["rendimiento_error"] += 1
                stats["errores"].append(msg)

    logger.info(
        f"[SYNC] Sincronización completada: "
        f"{stats['estudiantes_nuevos']} nuevos, "
        f"{stats['estudiantes_actualizados']} actualizados, "
        f"{stats['rendimiento_ok']} notas OK, "
        f"{stats['rendimiento_error']} errores"
    )
    return stats


# ─── Utilidades internas ───

def _safe_str(val) -> Optional[str]:
    """Convierte un valor a string limpio, retorna None si está vacío/NaN."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    return s if s and s.lower() != 'nan' else None


def _safe_float(val) -> Optional[float]:
    """Convierte un valor a float, retorna None si no es numérico."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        result = float(val)
        return result
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> int:
    """Convierte un valor a int, retorna 0 si no es numérico."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0
