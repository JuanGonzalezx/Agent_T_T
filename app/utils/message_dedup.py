"""
Cache de deduplicación para mensajes de WhatsApp.

Evita procesar el mismo mensaje múltiples veces cuando Meta reenvía
webhooks por timeouts o problemas de red.

IMPORTANTE para Gunicorn multi-worker:
- Usa archivo compartido como fallback para sincronizar entre workers
- Thread-safe con locks
"""

import os
import time
import threading
import json
import tempfile
from typing import Dict
from pathlib import Path


class MessageDeduplicator:
    """
    Cache híbrido (memoria + archivo) para deduplicación de message_ids.
    
    Características:
    - Thread-safe con threading.Lock
    - Soporta múltiples workers de Gunicorn via archivo compartido
    - Limpieza automática de entradas expiradas
    - TTL configurable (default: 5 minutos)
    """
    
    def __init__(self, ttl_seconds: int = 300, cleanup_interval: int = 60):
        """
        Args:
            ttl_seconds: Tiempo de vida de cada entrada (default: 5 minutos)
            cleanup_interval: Intervalo de limpieza automática (default: 60s)
        """
        self._cache: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()
        
        # Archivo compartido para multi-worker (en /tmp o carpeta data)
        self._file_path = self._get_cache_file_path()
        self._file_lock = threading.Lock()
    
    def _get_cache_file_path(self) -> Path:
        """Obtiene ruta del archivo de cache compartido."""
        # Intentar usar carpeta data del proyecto, sino /tmp
        data_dir = Path(os.getcwd()) / 'data'
        if data_dir.exists():
            return data_dir / '.message_dedup_cache.json'
        return Path(tempfile.gettempdir()) / 'whatsapp_dedup_cache.json'
    
    def _load_file_cache(self) -> Dict[str, float]:
        """Carga el cache desde archivo (para multi-worker sync)."""
        try:
            if self._file_path.exists():
                with open(self._file_path, 'r') as f:
                    data = json.load(f)
                    # Filtrar expirados
                    current_time = time.time()
                    return {k: v for k, v in data.items() 
                            if current_time - v < self._ttl}
            return {}
        except (json.JSONDecodeError, IOError):
            return {}
    
    def _save_to_file(self, message_id: str, timestamp: float):
        """Guarda un entry en el archivo (atómico)."""
        try:
            with self._file_lock:
                cache = self._load_file_cache()
                cache[message_id] = timestamp
                
                # Limpiar expirados antes de guardar
                current_time = time.time()
                cache = {k: v for k, v in cache.items() 
                        if current_time - v < self._ttl}
                
                # Escribir de forma atómica
                temp_path = self._file_path.with_suffix('.tmp')
                with open(temp_path, 'w') as f:
                    json.dump(cache, f)
                temp_path.replace(self._file_path)
        except IOError:
            pass  # Silenciar errores de I/O
    
    def _is_in_file_cache(self, message_id: str) -> bool:
        """Verifica si el message_id está en el archivo de cache."""
        try:
            cache = self._load_file_cache()
            if message_id in cache:
                return time.time() - cache[message_id] < self._ttl
            return False
        except Exception:
            return False
    
    def check_and_mark(self, message_id: str) -> bool:
        """
        Atómicamente verifica y marca un message_id.
        
        Usa doble verificación: memoria + archivo para multi-worker.
        
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
            
            # 1. Verificar en memoria local
            if message_id in self._cache:
                if current_time - self._cache[message_id] < self._ttl:
                    return True  # Duplicado (en memoria)
            
            # 2. Verificar en archivo (para otros workers)
            if self._is_in_file_cache(message_id):
                # También agregarlo a memoria local
                self._cache[message_id] = current_time
                return True  # Duplicado (de otro worker)
            
            # 3. No es duplicado - marcar en ambos lugares
            self._cache[message_id] = current_time
            self._save_to_file(message_id, current_time)
            return False
    
    def is_duplicate(self, message_id: str) -> bool:
        """Verifica si es duplicado sin marcar."""
        if not message_id:
            return False
        
        current_time = time.time()
        
        with self._lock:
            # Verificar memoria
            if message_id in self._cache:
                if current_time - self._cache[message_id] < self._ttl:
                    return True
            
            # Verificar archivo
            return self._is_in_file_cache(message_id)
    
    def mark_processed(self, message_id: str) -> None:
        """Marca un message_id como procesado."""
        if not message_id:
            return
        
        current_time = time.time()
        with self._lock:
            self._cache[message_id] = current_time
            self._save_to_file(message_id, current_time)
    
    def _cleanup_expired(self, current_time: float) -> None:
        """Elimina entradas expiradas del cache en memoria."""
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
            file_entries = len(self._load_file_cache())
            return {
                "memory_entries": len(self._cache),
                "file_entries": file_entries,
                "ttl_seconds": self._ttl,
                "file_path": str(self._file_path)
            }


# Instancia global singleton
_deduplicator = None
_dedup_lock = threading.Lock()


def get_deduplicator() -> MessageDeduplicator:
    """Obtiene la instancia singleton del deduplicador (thread-safe)."""
    global _deduplicator
    if _deduplicator is None:
        with _dedup_lock:
            if _deduplicator is None:  # Double-check locking
                _deduplicator = MessageDeduplicator(ttl_seconds=300)
    return _deduplicator