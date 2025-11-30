"""
Admin API endpoints.

Endpoints para administración del sistema:
- Reindexar RAG
- Ver estadísticas
- Forzar sincronización
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/admin", tags=["admin"])


class ReindexResponse(BaseModel):
    """Respuesta de reindexación."""
    status: str
    message: str
    tasks_indexed: int = 0
    projects_indexed: int = 0
    total_documents: int = 0
    timestamp: str


class StatsResponse(BaseModel):
    """Estadísticas del sistema."""
    rag_documents: int
    rag_enabled: bool
    timestamp: str


async def _reindex_all() -> dict:
    """Ejecuta la reindexación completa."""
    from app.domain.services import get_task_service, get_project_service
    from app.core.rag import get_vector_store, get_retriever

    task_service = get_task_service()
    project_service = get_project_service()
    retriever = get_retriever()
    vector_store = get_vector_store()

    # Reindexar tareas
    tasks_count = await task_service.reindex_all()

    # Reindexar proyectos
    projects = await project_service.get_active()
    projects_count = 0
    for project in projects:
        try:
            await retriever.index_project(project)
            projects_count += 1
        except Exception as e:
            logger.warning(f"Error indexando proyecto {project.name}: {e}")

    return {
        "tasks_indexed": tasks_count,
        "projects_indexed": projects_count,
        "total_documents": vector_store.count,
    }


@router.post("/reindex", response_model=ReindexResponse)
async def reindex_rag(background_tasks: BackgroundTasks):
    """
    Reindexa todas las tareas y proyectos en el sistema RAG.

    Este endpoint inicia la reindexación en segundo plano.
    """
    # Solo permitir en desarrollo o con autenticación apropiada
    if not settings.is_development:
        # TODO: Agregar autenticación para producción
        pass

    try:
        logger.info("Iniciando reindexación RAG...")

        result = await _reindex_all()

        logger.info(f"Reindexación completada: {result}")

        return ReindexResponse(
            status="completed",
            message="Reindexación completada exitosamente",
            tasks_indexed=result["tasks_indexed"],
            projects_indexed=result["projects_indexed"],
            total_documents=result["total_documents"],
            timestamp=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error(f"Error en reindexación: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Obtiene estadísticas del sistema RAG."""
    try:
        from app.core.rag import get_vector_store
        from app.domain.services import get_task_service

        vector_store = get_vector_store()
        task_service = get_task_service()

        return StatsResponse(
            rag_documents=vector_store.count,
            rag_enabled=task_service._rag_enabled,
            timestamp=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error(f"Error obteniendo stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync-notion")
async def sync_from_notion():
    """
    Sincroniza datos desde Notion y actualiza el índice RAG.

    Útil cuando se hacen cambios directamente en Notion.
    """
    try:
        from app.domain.services import get_task_service
        from app.core.rag import get_vector_store

        task_service = get_task_service()

        # Reindexar todo
        tasks_count = await task_service.reindex_all()
        vector_store = get_vector_store()

        return {
            "status": "synced",
            "tasks_synced": tasks_count,
            "total_documents": vector_store.count,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error sincronizando con Notion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear-index")
async def clear_rag_index():
    """
    Limpia completamente el índice RAG.

    CUIDADO: Esto elimina todos los documentos indexados.
    Requiere reindexar después.
    """
    if not settings.is_development:
        raise HTTPException(
            status_code=403,
            detail="Esta operación solo está disponible en desarrollo",
        )

    try:
        from app.core.rag import get_vector_store
        import os

        vector_store = get_vector_store()
        db_path = vector_store._db_path

        # Limpiar en memoria
        vector_store._documents.clear()

        # Eliminar archivo si existe
        if os.path.exists(db_path):
            os.remove(db_path)
            logger.info(f"Archivo de índice eliminado: {db_path}")

        return {
            "status": "cleared",
            "message": "Índice RAG limpiado. Ejecuta /admin/reindex para reconstruir.",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error limpiando índice: {e}")
        raise HTTPException(status_code=500, detail=str(e))
