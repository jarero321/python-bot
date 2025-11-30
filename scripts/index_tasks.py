#!/usr/bin/env python3
"""
Script para indexar todas las tareas existentes en el sistema RAG.

Uso:
    python scripts/index_tasks.py

Este script:
1. Conecta con Notion para obtener todas las tareas
2. Las indexa en el VectorStore para búsqueda semántica
3. Muestra estadísticas de indexación
"""

import asyncio
import logging
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.core.llm import get_llm_provider
from app.core.rag import get_embedding_provider, get_retriever, get_vector_store
from app.domain.repositories import get_task_repository, get_project_repository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger(__name__)


async def index_all_tasks() -> dict:
    """
    Indexa todas las tareas pendientes en el sistema RAG.

    Returns:
        Diccionario con estadísticas de indexación
    """
    logger.info("Iniciando indexación de tareas...")

    # Configurar LLM y embeddings
    settings = get_settings()
    logger.info(f"Entorno: {settings.app_env}")

    # Configurar embedding provider
    embedding_provider = get_embedding_provider()
    embedding_provider.configure()
    logger.info("Embedding provider configurado")

    # Inicializar retriever
    retriever = get_retriever()
    await retriever.initialize()
    logger.info("Retriever inicializado")

    # Obtener repositorio de tareas
    task_repo = get_task_repository()

    # Obtener todas las tareas pendientes
    logger.info("Obteniendo tareas de Notion...")
    tasks = await task_repo.get_pending(limit=500)
    logger.info(f"Encontradas {len(tasks)} tareas pendientes")

    # También obtener tareas completadas recientes para contexto
    # (esto ayuda a detectar duplicados incluso con tareas ya hechas)

    # Indexar en batch
    if tasks:
        logger.info("Indexando tareas...")
        await retriever.index_tasks_batch(tasks)
        logger.info(f"Indexadas {len(tasks)} tareas")

    # Estadísticas
    vector_store = get_vector_store()
    stats = {
        "tasks_found": len(tasks),
        "tasks_indexed": len(tasks),
        "total_documents": vector_store.count,
    }

    logger.info(f"Indexación completada: {stats}")
    return stats


async def index_all_projects() -> dict:
    """
    Indexa todos los proyectos activos en el sistema RAG.

    Returns:
        Diccionario con estadísticas de indexación
    """
    logger.info("Iniciando indexación de proyectos...")

    # Obtener retriever (ya inicializado)
    retriever = get_retriever()

    # Obtener repositorio de proyectos
    project_repo = get_project_repository()

    # Obtener proyectos activos
    logger.info("Obteniendo proyectos de Notion...")
    projects = await project_repo.get_active()
    logger.info(f"Encontrados {len(projects)} proyectos activos")

    # Indexar proyectos uno por uno (normalmente son menos)
    indexed = 0
    for project in projects:
        try:
            await retriever.index_project(project)
            indexed += 1
        except Exception as e:
            logger.warning(f"Error indexando proyecto {project.name}: {e}")

    logger.info(f"Indexados {indexed}/{len(projects)} proyectos")

    # Estadísticas
    vector_store = get_vector_store()
    stats = {
        "projects_found": len(projects),
        "projects_indexed": indexed,
        "total_documents": vector_store.count,
    }

    return stats


async def main():
    """Función principal del script."""
    print("=" * 60)
    print("Carlos Command - Indexación RAG")
    print("=" * 60)
    print()

    try:
        # Indexar tareas
        task_stats = await index_all_tasks()
        print(f"\n📋 Tareas:")
        print(f"   Encontradas: {task_stats['tasks_found']}")
        print(f"   Indexadas: {task_stats['tasks_indexed']}")

        # Indexar proyectos
        project_stats = await index_all_projects()
        print(f"\n📁 Proyectos:")
        print(f"   Encontrados: {project_stats['projects_found']}")
        print(f"   Indexados: {project_stats['projects_indexed']}")

        print(f"\n📊 Total documentos en índice: {project_stats['total_documents']}")
        print("\n✅ Indexación completada exitosamente!")

    except Exception as e:
        logger.error(f"Error durante indexación: {e}")
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
