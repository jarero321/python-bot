"""
RAG Sync Job - Sincronización periódica del índice RAG con Notion.

Este job asegura que el índice RAG se mantenga sincronizado con
los datos de Notion, incluso si hay cambios externos.
"""

import logging
from datetime import datetime

from app.domain.services import get_task_service

logger = logging.getLogger(__name__)


async def sync_rag_index_job() -> None:
    """
    Sincroniza el índice RAG con las tareas de Notion.

    Este job se ejecuta cada 15 minutos para asegurar
    que el índice esté actualizado.
    """
    start_time = datetime.now()
    logger.info("Iniciando sincronización de RAG...")

    try:
        service = get_task_service()

        # Verificar si RAG está habilitado
        if not service._rag_enabled:
            logger.warning("RAG no está habilitado, saltando sincronización")
            return

        # Reindexar todas las tareas
        count = await service.reindex_all()

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"RAG sincronizado: {count} tareas indexadas en {elapsed:.2f}s")

    except Exception as e:
        logger.error(f"Error sincronizando RAG: {e}")


async def cleanup_stale_rag_entries_job() -> None:
    """
    Limpia entradas obsoletas del RAG.

    Este job se ejecuta diariamente para eliminar
    documentos de tareas que ya no existen.
    """
    logger.info("Limpiando entradas obsoletas del RAG...")

    try:
        from app.core.rag import get_vector_store

        store = get_vector_store()

        # Obtener estadísticas
        stats = store.get_stats()
        logger.info(f"RAG stats: {stats}")

        # El cleanup real se hace en reindex_all que reemplaza todo

    except Exception as e:
        logger.error(f"Error limpiando RAG: {e}")
