import time
import threading
from collections import OrderedDict

class MessageDeduplicator:
    """
    Cache de deduplicación en MEMORIA RAM.
    Optimizado para Gunicorn con 1 Worker + Multi-Threads.
    Elimina por completo el uso de archivos (File I/O) para velocidad máxima.
    """
    
    def __init__(self, ttl_seconds: int = 300, max_entries: int = 5000):
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        # OrderedDict funciona como un cache LRU natural
        self._cache = OrderedDict()
        self._lock = threading.Lock()
    
    def check_and_mark(self, message_id: str) -> bool:
        """
        Retorna True si es duplicado, False si es nuevo.
        Si es nuevo, lo marca inmediatamente.
        """
        if not message_id:
            return False
            
        current_time = time.time()
        
        with self._lock:
            # 1. Verificar si existe
            if message_id in self._cache:
                timestamp = self._cache[message_id]
                # Si no ha expirado, es duplicado
                if current_time - timestamp < self._ttl:
                    return True
                else:
                    # Si expiró, lo actualizamos (lo tratamos como nuevo renacido)
                    # Mover al final (más reciente)
                    self._cache.move_to_end(message_id)
                    self._cache[message_id] = current_time
                    return False
            
            # 2. Si es nuevo, guardar
            self._cache[message_id] = current_time
            
            # 3. Limpieza periódica si excedemos tamaño
            if len(self._cache) > self._max_entries:
                # Eliminar el más antiguo (FIFO)
                self._cache.popitem(last=False)
                
            return False

# Singleton global
_deduplicator = None
_dedup_lock = threading.Lock()

def get_deduplicator() -> MessageDeduplicator:
    global _deduplicator
    if _deduplicator is None:
        with _dedup_lock:
            if _deduplicator is None:
                _deduplicator = MessageDeduplicator()
    return _deduplicator