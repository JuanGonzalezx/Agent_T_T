"""
Utilidades para normalización y transformación de datos.

Este módulo proporciona funciones para limpiar, normalizar y transformar
datos de contactos, especialmente enfocado en columnas de teléfonos y
preparación de DataFrames para envíos masivos.
"""

import unicodedata
import pandas as pd
from typing import Tuple


def normalize_column_name(col_name: str) -> str:
    """
    Normaliza un nombre de columna eliminando acentos, espacios y caracteres especiales.
    
    Args:
        col_name: Nombre de columna original
        
    Returns:
        str: Nombre normalizado en minúsculas sin acentos ni caracteres especiales
    """
    normalized = ''.join(
        c for c in unicodedata.normalize('NFD', col_name.lower())
        if unicodedata.category(c) != 'Mn'
    )
    return normalized.replace(' ', '').replace('_', '').replace('-', '')


def map_column_aliases(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mapea columnas del Excel con nombres alternativos a los nombres estándar del sistema.

    Aliases soportados:
      - Numero_documento / numero_documento / cedula → documento
      - Correo / correo_electronico → email
      - nombre2 / Apellido1 / Apellido2 se mantienen para concatenación posterior

    Args:
        df: DataFrame con columnas originales del Excel

    Returns:
        DataFrame: DataFrame con columnas renombradas si aplica
    """
    # Crear mapeo normalizado → nombre original
    normalized_map = {normalize_column_name(c): c for c in df.columns}

    alias_targets = {
        'documento': ['numerodocumento', 'cedula', 'numerocedula', 'nrodocumento', 'nodocumento', 'identificacion'],
        'email': ['correo', 'correoelectronico', 'mail', 'emailestudiante'],
    }

    for target_col, aliases in alias_targets.items():
        if target_col not in df.columns:
            for alias in aliases:
                if alias in normalized_map:
                    df = df.rename(columns={normalized_map[alias]: target_col})
                    break

    return df


def concatenate_name_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Concatena múltiples columnas de nombre en una sola columna 'nombre'.

    Si el DataFrame tiene columnas como nombre, nombre2, Apellido1, Apellido2,
    las concatena en un solo campo 'nombre' separado por espacios.

    Patrón detectado: nombre + nombre2 + apellido1 + apellido2
    Si solo existe 'nombre', no hace nada.

    Args:
        df: DataFrame que podría tener columnas de nombre fragmentadas

    Returns:
        DataFrame: DataFrame con columna 'nombre' consolidada
    """
    # Normalizar para detección
    normalized_map = {normalize_column_name(c): c for c in df.columns}

    # Componentes de nombre en orden (normalizado → original)
    name_parts_keys = ['nombre', 'nombre2', 'apellido1', 'apellido2']
    found_parts = []
    for key in name_parts_keys:
        if key in normalized_map:
            found_parts.append(normalized_map[key])

    # Solo concatenar si hay más de 1 componente de nombre
    if len(found_parts) <= 1:
        return df

    # Concatenar partes en 'nombre'
    def _concat_row(row):
        parts = []
        for col in found_parts:
            val = str(row.get(col, '')).strip()
            if val and val != 'nan' and val != '-':
                parts.append(val)
        return ' '.join(parts) if parts else ''

    df['nombre'] = df.apply(_concat_row, axis=1)

    # Eliminar columnas fragmentadas (excepto 'nombre' original si es una de ellas)
    cols_to_drop = [c for c in found_parts if c != 'nombre' and c in df.columns]
    df = df.drop(columns=cols_to_drop)

    return df


def normalize_phone_column(df: pd.DataFrame) -> Tuple[bool, pd.DataFrame, str]:
    """
    Normaliza y mapea la columna de teléfono a 'telefono_e164'.
    
    Busca entre múltiples variantes de nombres de columnas de teléfono
    y renombra la encontrada a 'telefono_e164' para estandarización.
    
    Args:
        df: DataFrame original
        
    Returns:
        Tuple[bool, DataFrame, str]: (éxito, dataframe_modificado, mensaje_error)
    """
    # Si ya existe telefono_e164, no hacer nada
    if 'telefono_e164' in df.columns:
        return True, df, ''
    
    # Crear mapeo de columnas normalizadas
    normalized_cols = {normalize_column_name(c): c for c in df.columns}
    
    # Variantes posibles de columna de teléfono
    phone_variants = [
        'telefono', 'telefonocelular', 'telefonoe164', 
        'phone', 'phonenumber', 'celular', 'cel',
        'telefonodelestudiante', 'telefonoestudiante',
        'movil', 'whatsapp', 'contacto', 'numero'
    ]
    
    # Buscar coincidencia
    for variant in phone_variants:
        if variant in normalized_cols:
            original_col = normalized_cols[variant]
            df = df.rename(columns={original_col: 'telefono_e164'})
            return True, df, ''
    
    # No se encontró columna de teléfono
    cols = ', '.join(df.columns.tolist())
    return False, df, f'Columna de teléfono no encontrada. Disponibles: {cols}'


def clean_phone_numbers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia y normaliza los números de teléfono.
    
    Elimina espacios, guiones, paréntesis y el símbolo + para dejar
    solo los dígitos del número telefónico.
    
    Args:
        df: DataFrame con columna telefono_e164
        
    Returns:
        DataFrame: DataFrame con teléfonos normalizados
    """
    if 'telefono_e164' not in df.columns:
        return df
    
    df['telefono_e164'] = (df['telefono_e164']
        .astype(str)
        .str.strip()
        .str.replace(' ', '', regex=False)
        .str.replace('-', '', regex=False)
        .str.replace('(', '', regex=False)
        .str.replace(')', '', regex=False)
        .str.replace('+', '', regex=False)
    )
    return df


def add_tracking_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Añade columnas auxiliares al DataFrame si no existen.
    
    En el esquema normalizado v3, los campos de tracking (opt_in,
    estado_academico, estado_envio, etc.) son manejados por el
    sistema automáticamente.  Aquí solo se garantizan columnas
    de datos del usuario que pueden no venir del Excel.
    
    Columnas añadidas:
    - documento: Número de documento (opcional del usuario)
    - email: Email del estudiante (opcional del usuario)
    
    Args:
        df: DataFrame original
        
    Returns:
        DataFrame: DataFrame con columnas auxiliares
    """
    aux_cols = {
        'documento': '',
        'email': ''
    }
    
    for col, default in aux_cols.items():
        if col not in df.columns:
            df[col] = default
    
    return df


def validate_dataframe(df: pd.DataFrame) -> Tuple[bool, str]:
    """
    Valida que el DataFrame tenga la estructura mínima requerida.
    
    Verifica que:
    - El DataFrame no esté vacío
    - Tenga la columna de teléfono (telefono_e164)
    - Los teléfonos no estén vacíos
    
    Args:
        df: DataFrame a validar
        
    Returns:
        Tuple[bool, str]: (es_válido, mensaje_error)
    """
    if df.empty:
        return False, "El DataFrame está vacío"
    
    if 'telefono_e164' not in df.columns:
        return False, "Falta la columna 'telefono_e164'"
    
    # Contar teléfonos válidos (no vacíos y no NaN)
    valid_phones = df['telefono_e164'].notna() & (df['telefono_e164'].astype(str).str.strip() != '')
    valid_count = valid_phones.sum()
    
    if valid_count == 0:
        return False, "No hay números de teléfono válidos"
    
    return True, f"{valid_count} contactos válidos"
