"""
Task Service - Servicio de dominio para tareas.

Combina el repositorio de tareas con el sistema RAG para:
- Detección de duplicados antes de crear
- Búsqueda semántica de tareas
- Indexación automática
"""

import logging
from dataclasses import dataclass
from typing import Any

from app.domain.entities.task import Task, TaskStatus, TaskPriority, TaskFilter
from app.domain.repositories import get_task_repository, ITaskRepository
from app.core.rag import get_retriever, RAGRetriever

logger = logging.getLogger(__name__)


@dataclass
class DuplicateCheckResult:
    """Resultado de verificación de duplicados."""

    is_duplicate: bool
    confidence: float
    similar_tasks: list[dict[str, Any]]
    suggestion: str | None = None


@dataclass
class TaskSearchResult:
    """Resultado de búsqueda de tareas."""

    tasks: list[Task]
    query: str
    used_semantic: bool
    total_found: int


class TaskService:
    """
    Servicio de dominio para tareas.

    Combina repositorio + RAG para operaciones avanzadas.

    Uso:
        service = get_task_service()

        # Crear tarea con verificación de duplicados
        result = await service.create_with_duplicate_check(task)
        if result.is_duplicate:
            # Preguntar al usuario si quiere crear de todas formas

        # Buscar tareas semánticamente
        results = await service.smart_search("emails urgentes")
    """

    _instance: "TaskService | None" = None

    def __new__(cls, *args, **kwargs) -> "TaskService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        task_repo: ITaskRepository | None = None,
        retriever: RAGRetriever | None = None,
    ):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._repo = task_repo or get_task_repository()
        self._retriever = retriever or get_retriever()
        self._rag_enabled = False

    async def initialize(self) -> None:
        """Inicializa el servicio (incluyendo RAG)."""
        try:
            await self._retriever.initialize()
            self._rag_enabled = True
            logger.info("TaskService inicializado con RAG habilitado")
        except Exception as e:
            logger.warning(f"RAG no disponible, continuando sin él: {e}")
            self._rag_enabled = False

    # ==================== CRUD con RAG ====================

    async def create(self, task: Task, check_duplicates: bool = True) -> tuple[Task, DuplicateCheckResult | None]:
        """
        Crea una tarea, opcionalmente verificando duplicados.

        Args:
            task: Tarea a crear
            check_duplicates: Si verificar duplicados con RAG

        Returns:
            Tupla de (tarea creada, resultado de duplicados o None)
        """
        duplicate_result = None

        if check_duplicates and self._rag_enabled:
            duplicate_result = await self.check_duplicate(task.title)

            if duplicate_result.is_duplicate and duplicate_result.confidence > 0.85:
                # Alta probabilidad de duplicado, no crear automáticamente
                logger.info(f"Posible duplicado detectado para: {task.title}")
                # Retornar la tarea sin crear, con el resultado de duplicado
                return task, duplicate_result

        # Crear la tarea
        created_task = await self._repo.create(task)

        # Indexar en RAG si está habilitado
        if self._rag_enabled:
            try:
                await self._retriever.index_task(created_task)
            except Exception as e:
                logger.warning(f"Error indexando tarea en RAG: {e}")

        return created_task, duplicate_result

    async def update(self, task: Task) -> Task:
        """Actualiza una tarea y re-indexa en RAG."""
        updated = await self._repo.update(task)

        if self._rag_enabled:
            try:
                await self._retriever.index_task(updated)
            except Exception as e:
                logger.warning(f"Error re-indexando tarea: {e}")

        return updated

    async def delete(self, task_id: str) -> bool:
        """Elimina una tarea y la quita del RAG."""
        success = await self._repo.delete(task_id)

        if success and self._rag_enabled:
            try:
                await self._retriever.remove_task(task_id)
            except Exception as e:
                logger.warning(f"Error eliminando tarea de RAG: {e}")

        return success

    async def complete(self, task_id: str) -> Task | None:
        """Completa una tarea y re-indexa en RAG."""
        completed = await self._repo.complete(task_id)

        # Re-indexar en RAG para mantener consistencia
        if completed and self._rag_enabled:
            try:
                await self._retriever.index_task(completed)
                logger.debug(f"Tarea {task_id} re-indexada en RAG después de completar")
            except Exception as e:
                logger.warning(f"Error re-indexando tarea completada: {e}")

        return completed

    async def get_by_id(self, task_id: str) -> Task | None:
        """Obtiene una tarea por su ID."""
        return await self._repo.get_by_id(task_id)

    # ==================== Búsqueda ====================

    async def smart_search(
        self,
        query: str,
        limit: int = 10,
        use_semantic: bool = True,
    ) -> TaskSearchResult:
        """
        Búsqueda inteligente de tareas.

        Combina búsqueda semántica (RAG) con filtros del repositorio.

        Args:
            query: Texto de búsqueda
            limit: Máximo de resultados
            use_semantic: Si usar búsqueda semántica

        Returns:
            TaskSearchResult con tareas encontradas
        """
        tasks: list[Task] = []
        used_semantic = False

        # Intentar búsqueda semántica primero
        if use_semantic and self._rag_enabled:
            try:
                rag_results = await self._retriever.search_tasks(query, limit=limit)

                if rag_results:
                    used_semantic = True
                    # Obtener tareas completas por ID
                    for result in rag_results:
                        task_id = result.document.metadata.get("task_id")
                        if task_id:
                            task = await self._repo.get_by_id(task_id)
                            if task and task.is_active:
                                tasks.append(task)
            except Exception as e:
                logger.warning(f"Error en búsqueda semántica: {e}")

        # Si no hay resultados semánticos, buscar por texto
        if not tasks:
            # Obtener tareas pendientes y filtrar por texto
            all_tasks = await self._repo.get_pending(limit=50)
            query_lower = query.lower()

            for task in all_tasks:
                if query_lower in task.title.lower():
                    tasks.append(task)
                elif task.notes and query_lower in task.notes.lower():
                    tasks.append(task)

                if len(tasks) >= limit:
                    break

        return TaskSearchResult(
            tasks=tasks[:limit],
            query=query,
            used_semantic=used_semantic,
            total_found=len(tasks),
        )

    async def find_similar(self, task: Task, limit: int = 5) -> list[Task]:
        """
        Encuentra tareas similares a una dada.

        Args:
            task: Tarea de referencia
            limit: Máximo de resultados

        Returns:
            Lista de tareas similares
        """
        if not self._rag_enabled:
            return []

        try:
            results = await self._retriever.search_tasks(
                task.title,
                limit=limit + 1,  # +1 por si incluye la misma tarea
            )

            similar = []
            for result in results:
                task_id = result.document.metadata.get("task_id")
                if task_id and task_id != task.id:
                    found_task = await self._repo.get_by_id(task_id)
                    if found_task:
                        similar.append(found_task)

            return similar[:limit]
        except Exception as e:
            logger.warning(f"Error buscando tareas similares: {e}")
            return []

    # ==================== Detección de Duplicados ====================

    async def check_duplicate(
        self,
        text: str,
        threshold: float = 0.75,
    ) -> DuplicateCheckResult:
        """
        Verifica si un texto es duplicado de una tarea existente.

        Args:
            text: Texto a verificar
            threshold: Umbral de similitud (0-1)

        Returns:
            DuplicateCheckResult con información de duplicados
        """
        if not self._rag_enabled:
            return DuplicateCheckResult(
                is_duplicate=False,
                confidence=0.0,
                similar_tasks=[],
            )

        try:
            duplicates = await self._retriever.find_duplicates(
                text,
                threshold=threshold,
                limit=3,
            )

            if not duplicates:
                return DuplicateCheckResult(
                    is_duplicate=False,
                    confidence=0.0,
                    similar_tasks=[],
                )

            # Obtener info de tareas similares
            similar_tasks = []
            max_score = 0.0

            for dup in duplicates:
                task_id = dup.document.metadata.get("task_id")
                if task_id:
                    task = await self._repo.get_by_id(task_id)
                    if task:
                        similar_tasks.append({
                            "id": task.id,
                            "title": task.title,
                            "status": task.status.value,
                            "score": dup.score,
                        })
                        max_score = max(max_score, dup.score)

            is_duplicate = max_score > threshold
            suggestion = None

            if is_duplicate and similar_tasks:
                top_match = similar_tasks[0]
                suggestion = (
                    f"Ya existe una tarea similar: '{top_match['title']}' "
                    f"(similitud: {top_match['score']:.0%})"
                )

            return DuplicateCheckResult(
                is_duplicate=is_duplicate,
                confidence=max_score,
                similar_tasks=similar_tasks,
                suggestion=suggestion,
            )

        except Exception as e:
            logger.warning(f"Error verificando duplicados: {e}")
            return DuplicateCheckResult(
                is_duplicate=False,
                confidence=0.0,
                similar_tasks=[],
            )

    # ==================== Queries del Repositorio ====================

    async def get_for_today(self) -> list[Task]:
        """Obtiene tareas de hoy."""
        return await self._repo.get_for_today()

    async def get_pending(self, limit: int = 50) -> list[Task]:
        """Obtiene tareas pendientes."""
        return await self._repo.get_pending(limit)

    async def get_overdue(self) -> list[Task]:
        """Obtiene tareas vencidas."""
        return await self._repo.get_overdue()

    async def get_by_status(self, status: TaskStatus) -> list[Task]:
        """Obtiene tareas por estado."""
        return await self._repo.get_by_status(status)

    async def get_by_priority(self, priority: TaskPriority) -> list[Task]:
        """Obtiene tareas por prioridad."""
        return await self._repo.get_by_priority(priority)

    async def get_workload_summary(self) -> dict[str, Any]:
        """Obtiene resumen de carga de trabajo."""
        return await self._repo.get_workload_summary()

    async def update_status(self, task_id: str, status: TaskStatus) -> Task | None:
        """Actualiza estado de una tarea y re-indexa en RAG."""
        updated = await self._repo.update_status(task_id, status)

        # Re-indexar en RAG para mantener consistencia
        if updated and self._rag_enabled:
            try:
                await self._retriever.index_task(updated)
                logger.debug(f"Tarea {task_id} re-indexada en RAG después de cambio de estado")
            except Exception as e:
                logger.warning(f"Error re-indexando tarea en RAG: {e}")

        return updated

    # ==================== Indexación Batch ====================

    async def reindex_all(self) -> int:
        """
        Re-indexa todas las tareas en el RAG.

        Útil para sincronizar después de cambios externos.

        Returns:
            Número de tareas indexadas
        """
        if not self._rag_enabled:
            logger.warning("RAG no habilitado, no se puede reindexar")
            return 0

        try:
            tasks = await self._repo.get_pending(limit=500)
            await self._retriever.index_tasks_batch(tasks)
            logger.info(f"Re-indexadas {len(tasks)} tareas")
            return len(tasks)
        except Exception as e:
            logger.error(f"Error reindexando tareas: {e}")
            return 0


# Singleton
_task_service: TaskService | None = None


def get_task_service() -> TaskService:
    """Obtiene la instancia del TaskService."""
    global _task_service
    if _task_service is None:
        _task_service = TaskService()
    return _task_service
