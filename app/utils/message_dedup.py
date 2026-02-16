"""
Cache de deduplicación para mensajes de WhatsApp.

Evita procesar el mismo mensaje múltiples veces cuando Meta reenvía
webhooks por timeouts o problemas de red.
"""

import time
import threading
from typing import Dict, Tuple


class MessageDeduplicator:
    """
    Cache en memoria con TTL para deduplicación de message_ids.
    
    Thread-safe y eficiente, sin dependencias externas.
    Limpieza automática de entradas expiradas.
    """
    
    def __init__(self, ttl_seconds: int = 300, cleanup_interval: int = 60):
        """
        Args:
            ttl_seconds: Tiempo de vida de cada entrada (default: 5 minutos)
            cleanup_interval: Intervalo de limpieza automática (default: 60s)
        """
        self._cache: Dict[str, float] = {}  # message_id -> timestamp
        self._lock = threading.Lock()
        self._ttl = ttl_seconds
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()
    
    def is_duplicate(self, message_id: str) -> bool:
        """
        Verifica si un message_id ya fue procesado.
        
        Args:
            message_id: El wamid del mensaje de WhatsApp
            
        Returns:
            True si es duplicado (ya existe en cache), False si es nuevo
        """
        if not message_id:
            return False
        
        current_time = time.time()
        
        with self._lock:
            # Limpieza periódica (lazy cleanup)
            if current_time - self._last_cleanup > self._cleanup_interval:
                self._cleanup_expired(current_time)
            
            # Verificar si existe y no ha expirado
            if message_id in self._cache:
                entry_time = self._cache[message_id]
                if current_time - entry_time < self._ttl:
                    return True  # Es duplicado
                # Expiró, lo removemos
                del self._cache[message_id]
            
            return False
    
    def mark_processed(self, message_id: str) -> None:
        """
        Marca un message_id como procesado.
        
        Args:
            message_id: El wamid del mensaje de WhatsApp
        """
        if not message_id:
            return
        
        with self._lock:
            self._cache[message_id] = time.time()
    
    def check_and_mark(self, message_id: str) -> bool:
        """
        Atómicamente verifica y marca un message_id.
        
        Args:
            message_id: El wamid del mensaje de WhatsApp
            
        Returns:
            True si es duplicado, False si es nuevo (y fue marcado)
        """
        if not message_id:
            return False
        
        current_time = time.time()
        
        with self._lock:
            # Limpieza periódica
            if current_time - self._last_cleanup > self._cleanup_interval:
                self._cleanup_expired(current_time)
            
            # Verificar si existe y no ha expirado
            if message_id in self._cache:
                entry_time = self._cache[message_id]
                if current_time - entry_time < self._ttl:
                    return True  # Es duplicado
            
            # Marcar como procesado
            self._cache[message_id] = current_time
            return False
    
    def _cleanup_expired(self, current_time: float) -> None:
        """Elimina entradas expiradas del cache."""
        expired_keys = [
            key for key, timestamp in self._cache.items()
            if current_time - timestamp >= self._ttl
        ]
        for key in expired_keys:
            del self._cache[key]
        self._last_cleanup = current_time
    
    def stats(self) -> dict:
        """Retorna estadísticas del cache."""
        with self._lock:
            return {
                "entries": len(self._cache),
                "ttl_seconds": self._ttl
            }


# Instancia global singleton
_deduplicator = None


def get_deduplicator() -> MessageDeduplicator:
    """Obtiene la instancia singleton del deduplicador."""
    global _deduplicator
    if _deduplicator is None:
        _deduplicator = MessageDeduplicator(ttl_seconds=300)  # 5 minutos
    return _deduplicator
