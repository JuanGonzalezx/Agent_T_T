"""
Utilidad de logging para llamadas a la API de Gemini.

Este módulo proporciona funciones helper para loggear el uso de tokens
en cada petición a la API de Gemini, facilitando el monitoreo de costos.
"""

import logging
from typing import Any, Optional
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)


def log_token_usage(response: Any, context: str = "GEMINI") -> dict:
    """
    Extrae y loggea información de uso de tokens de una respuesta de Gemini.
    
    Args:
        response: Objeto de respuesta de ChatGoogleGenerativeAI.invoke()
        context: Contexto/nodo desde donde se hace la llamada (para identificar en logs)
        
    Returns:
        dict: Diccionario con los datos de uso de tokens
    """
    usage_data = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "context": context
    }
    
    try:
        # Intentar extraer de usage_metadata directamente (LangChain Google GenAI)
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = response.usage_metadata
            # Puede ser dict o objeto, manejamos ambos casos
            if isinstance(usage, dict):
                usage_data["input_tokens"] = usage.get('input_tokens', 0) or usage.get('prompt_token_count', 0)
                usage_data["output_tokens"] = usage.get('output_tokens', 0) or usage.get('candidates_token_count', 0)
                usage_data["total_tokens"] = usage.get('total_tokens', 0) or usage.get('total_token_count', 0)
            else:
                usage_data["input_tokens"] = getattr(usage, 'input_tokens', 0)
                usage_data["output_tokens"] = getattr(usage, 'output_tokens', 0)
                usage_data["total_tokens"] = getattr(usage, 'total_tokens', 0)
        
        # Fallback: LangChain response_metadata
        elif hasattr(response, 'response_metadata') and response.response_metadata:
            metadata = response.response_metadata
            # Buscar en usage_metadata dentro de response_metadata
            usage_metadata = metadata.get('usage_metadata', metadata)
            
            # Probar múltiples nombres de claves (varían según versión)
            usage_data["input_tokens"] = (
                usage_metadata.get('input_tokens', 0) or 
                usage_metadata.get('prompt_token_count', 0) or
                usage_metadata.get('promptTokenCount', 0)
            )
            usage_data["output_tokens"] = (
                usage_metadata.get('output_tokens', 0) or 
                usage_metadata.get('candidates_token_count', 0) or
                usage_metadata.get('candidatesTokenCount', 0)
            )
            usage_data["total_tokens"] = (
                usage_metadata.get('total_tokens', 0) or 
                usage_metadata.get('total_token_count', 0) or
                usage_metadata.get('totalTokenCount', 0)
            )
            
            # Si aún es 0, calcular total
            if usage_data["total_tokens"] == 0:
                usage_data["total_tokens"] = usage_data["input_tokens"] + usage_data["output_tokens"]
        
        # Debug: si todo sigue en 0, loggear la estructura completa
        if usage_data["total_tokens"] == 0:
            debug_info = {}
            if hasattr(response, 'usage_metadata'):
                debug_info['usage_metadata'] = str(response.usage_metadata)
            if hasattr(response, 'response_metadata'):
                debug_info['response_metadata'] = str(response.response_metadata)[:500]
            logger.debug(f"[{context}] DEBUG metadata: {debug_info}")
        
        # Log con formato estructurado
        msg = (
            f"[{context}] 📊 Tokens usados - "
            f"Input: {usage_data['input_tokens']} | "
            f"Output: {usage_data['output_tokens']} | "
            f"Total: {usage_data['total_tokens']}"
        )
        logger.info(msg)
        print(msg, flush=True)  # Backup directo a stdout para Render
        
    except Exception as e:
        logger.warning(f"[{context}] No se pudo extraer info de tokens: {e}")
        print(f"[{context}] ⚠️ No se pudo extraer info de tokens: {e}", flush=True)
    
    return usage_data


def invoke_with_logging(
    llm: ChatGoogleGenerativeAI, 
    prompt: str, 
    context: str = "GEMINI"
) -> Any:
    """
    Invoca el modelo Gemini y automáticamente loggea el uso de tokens.
    
    Args:
        llm: Instancia de ChatGoogleGenerativeAI
        prompt: El prompt a enviar
        context: Identificador del contexto/nodo para los logs
        
    Returns:
        El objeto response de la invocación
    """
    print(f"[{context}] 🚀 Invocando Gemini...", flush=True)
    
    response = llm.invoke(prompt)
    log_token_usage(response, context)
    
    return response
