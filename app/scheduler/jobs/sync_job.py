"""
Sync Job - Job de sincronización periódica SQLite <-> Notion.
"""

import logging
from datetime import datetime

from app.services.sync_service import get_sync_service

logger = logging.getLogger(__name__)


async def run_full_sync() -> None:
    """
    Ejecuta sincronización completa.
    Programado cada 15 minutos.
    """
    logger.info("Iniciando sync job...")

    try:
        sync_service = get_sync_service()
        result = await sync_service.sync_all()

        logger.info(
            f"Sync completado: "
            f"{result['tasks_synced']} tareas, "
            f"{result['reminders_synced']} recordatorios, "
            f"{result['daily_logs_synced']} logs"
        )

        if result["errors"]:
            logger.warning(f"Sync con errores: {result['errors']}")

    except Exception as e:
        logger.error(f"Error en sync job: {e}")


async def sync_tasks_only() -> None:
    """
    Sincroniza solo tareas de Notion -> SQLite cache.
    Programado cada 5 minutos.
    """
    logger.info("Sincronizando tareas...")

    try:
        sync_service = get_sync_service()
        result = await sync_service.sync_tasks_from_notion()

        logger.info(f"Tareas sincronizadas: {result['synced']}")

    except Exception as e:
        logger.error(f"Error sincronizando tareas: {e}")


async def mark_cache_stale() -> None:
    """
    Marca cache como stale para forzar refresh.
    Ejecutar si se detectan inconsistencias.
    """
    logger.info("Marcando cache como stale...")

    try:
        sync_service = get_sync_service()
        await sync_service.mark_cache_stale()
        logger.info("Cache marcado como stale")

    except Exception as e:
        logger.error(f"Error marcando cache: {e}")
