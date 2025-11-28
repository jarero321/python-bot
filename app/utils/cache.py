"""Sistema de caching en memoria para Carlos Command."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, TypeVar, Generic

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """Entrada de cache con TTL."""

    value: T
    created_at: datetime = field(default_factory=datetime.now)
    ttl_seconds: int = 300  # 5 minutos por defecto
    hits: int = 0

    @property
    def is_expired(self) -> bool:
        """Verifica si la entrada ha expirado."""
        return datetime.now() > self.created_at + timedelta(seconds=self.ttl_seconds)

    def access(self) -> T:
        """Registra un acceso y retorna el valor."""
        self.hits += 1
        return self.value


class InMemoryCache:
    """
    Cache en memoria con TTL y limpieza automática.

    Uso:
        cache = InMemoryCache(default_ttl=300)
        cache.set("key", value)
        value = cache.get("key")
    """

    def __init__(
        self,
        default_ttl: int = 300,
        max_size: int = 1000,
        cleanup_interval: int = 60,
    ):
        """
        Inicializa el cache.

        Args:
            default_ttl: TTL por defecto en segundos
            max_size: Máximo número de entradas
            cleanup_interval: Intervalo de limpieza en segundos
        """
        self._cache: dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._cleanup_interval = cleanup_interval
        self._lock = asyncio.Lock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
        }

    async def get(self, key: str) -> Any | None:
        """
        Obtiene un valor del cache.

        Args:
            key: Clave del valor

        Returns:
            El valor si existe y no ha expirado, None si no
        """
        async with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats["misses"] += 1
                return None

            if entry.is_expired:
                del self._cache[key]
                self._stats["misses"] += 1
                return None

            self._stats["hits"] += 1
            return entry.access()

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """
        Guarda un valor en el cache.

        Args:
            key: Clave del valor
            value: Valor a guardar
            ttl: TTL personalizado en segundos
        """
        async with self._lock:
            # Verificar límite de tamaño
            if len(self._cache) >= self._max_size:
                await self._evict_oldest()

            self._cache[key] = CacheEntry(
                value=value,
                ttl_seconds=ttl or self._default_ttl,
            )

    async def delete(self, key: str) -> bool:
        """
        Elimina una entrada del cache.

        Args:
            key: Clave a eliminar

        Returns:
            True si existía y se eliminó
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> int:
        """
        Limpia todo el cache.

        Returns:
            Número de entradas eliminadas
        """
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    async def clear_pattern(self, pattern: str) -> int:
        """
        Elimina entradas que coincidan con un patrón.

        Args:
            pattern: Patrón de prefijo a buscar

        Returns:
            Número de entradas eliminadas
        """
        async with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(pattern)]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)

    async def cleanup(self) -> int:
        """
        Limpia entradas expiradas.

        Returns:
            Número de entradas eliminadas
        """
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items() if entry.is_expired
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)

    async def _evict_oldest(self) -> None:
        """Elimina la entrada más antigua."""
        if not self._cache:
            return

        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].created_at,
        )
        del self._cache[oldest_key]
        self._stats["evictions"] += 1

    def get_stats(self) -> dict[str, Any]:
        """Obtiene estadísticas del cache."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0

        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": f"{hit_rate:.2%}",
            "evictions": self._stats["evictions"],
        }


# Instancia global del cache
_cache: InMemoryCache | None = None


def get_cache() -> InMemoryCache:
    """Obtiene la instancia global del cache."""
    global _cache
    if _cache is None:
        _cache = InMemoryCache(
            default_ttl=300,  # 5 minutos
            max_size=500,
        )
    return _cache


def cached(
    ttl: int = 300,
    key_prefix: str = "",
    key_builder: Callable[..., str] | None = None,
):
    """
    Decorador para cachear resultados de funciones.

    Args:
        ttl: Tiempo de vida en segundos
        key_prefix: Prefijo para la clave de cache
        key_builder: Función para construir la clave

    Ejemplo:
        @cached(ttl=60, key_prefix="notion_tasks")
        async def get_tasks():
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            cache = get_cache()

            # Construir clave
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Clave por defecto basada en argumentos
                args_key = "_".join(str(a) for a in args)
                kwargs_key = "_".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = f"{key_prefix}:{func.__name__}:{args_key}:{kwargs_key}"

            # Intentar obtener del cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value

            # Ejecutar función
            result = await func(*args, **kwargs)

            # Guardar en cache
            if result is not None:
                await cache.set(cache_key, result, ttl=ttl)
                logger.debug(f"Cache set: {cache_key}")

            return result

        return wrapper

    return decorator


# Claves de cache predefinidas para Notion
class NotionCacheKeys:
    """Claves de cache para Notion."""

    TASKS_TODAY = "notion:tasks:today"
    TASKS_PENDING = "notion:tasks:pending"
    PROJECTS_ACTIVE = "notion:projects:active"
    PROJECTS_STUDY = "notion:projects:study"
    INBOX_UNPROCESSED = "notion:inbox:unprocessed"
    DEBTS_ACTIVE = "notion:debts:active"
    DEBT_SUMMARY = "notion:debts:summary"
    MONTHLY_SUMMARY = "notion:transactions:monthly"

    @staticmethod
    def task(task_id: str) -> str:
        return f"notion:task:{task_id}"

    @staticmethod
    def project(project_id: str) -> str:
        return f"notion:project:{project_id}"

    @staticmethod
    def workout_last(tipo: str) -> str:
        return f"notion:workout:last:{tipo}"
