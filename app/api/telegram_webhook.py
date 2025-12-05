"""Webhook endpoint para Telegram con idempotencia."""

import logging
import time
from collections import OrderedDict
from threading import Lock

from fastapi import APIRouter, Request
from telegram import Update

from app.bot.handlers import get_application

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


class UpdateIdempotencyCache:
    """
    Cache para evitar procesar updates duplicados de Telegram.

    Telegram puede reenviar webhooks si:
    - No recibe respuesta en ~60 segundos
    - Recibe un error 5xx

    Este cache guarda los update_id procesados con TTL de 5 minutos.
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self._cache: OrderedDict[int, float] = OrderedDict()
        self._lock = Lock()
        self._max_size = max_size
        self._ttl = ttl_seconds

    def is_duplicate(self, update_id: int) -> bool:
        """Verifica si el update ya fue procesado. Si no, lo registra."""
        current_time = time.time()

        with self._lock:
            # Limpiar entradas expiradas
            self._cleanup_expired(current_time)

            # Verificar si ya existe
            if update_id in self._cache:
                logger.warning(f"Update duplicado detectado: {update_id}")
                return True

            # Registrar nuevo update
            self._cache[update_id] = current_time

            # Mantener tamaño máximo
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

            return False

    def _cleanup_expired(self, current_time: float) -> None:
        """Elimina entradas expiradas del cache."""
        expired_keys = [
            k for k, v in self._cache.items()
            if current_time - v > self._ttl
        ]
        for k in expired_keys:
            del self._cache[k]


# Cache global de idempotencia
_update_cache = UpdateIdempotencyCache()


@router.post("/telegram")
async def telegram_webhook(request: Request):
    """Procesa los updates de Telegram via webhook con protección contra duplicados."""
    try:
        data = await request.json()

        # Extraer update_id para idempotencia
        update_id = data.get("update_id")

        if update_id is None:
            logger.error("Update sin update_id")
            return {"status": "error", "message": "Missing update_id"}

        # Verificar duplicado ANTES de procesar
        if _update_cache.is_duplicate(update_id):
            logger.info(f"Update {update_id} ignorado (duplicado)")
            return {"status": "ok", "message": "duplicate ignored"}

        logger.info(f"Update {update_id} recibido")

        application = get_application()

        if application is None:
            logger.error("Application no inicializada")
            return {"status": "error", "message": "Bot not initialized"}

        update = Update.de_json(data, application.bot)

        await application.process_update(update)
        logger.info(f"Update {update_id} procesado OK")

        return {"status": "ok"}
    except Exception as e:
        logger.exception(f"Error procesando webhook: {e}")
        # Retornar 200 OK para que Telegram no reintente
        # El error ya está logueado
        return {"status": "error", "message": str(e)}
