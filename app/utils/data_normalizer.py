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
    
    En el esquema normalizado v3, el tracking de envíos vive en
    campana_miembros, no en estudiantes.  Aquí solo se garantizan
    columnas base que pueden no venir del Excel.
    
    Columnas añadidas:
    - opt_in: Consentimiento WhatsApp (0/1)
    - estado_academico: INSCRITO por defecto
    - documento: Número de documento
    - email: Email del estudiante
    
    Args:
        df: DataFrame original
        
    Returns:
        DataFrame: DataFrame con columnas auxiliares
    """
    aux_cols = {
        'opt_in': '0',
        'estado_academico': 'INSCRITO',
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
