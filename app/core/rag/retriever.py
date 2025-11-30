"""
RAG Retriever - Recuperación de contexto relevante.

Combina VectorStore con repositorios del dominio para
enriquecer el contexto de las consultas LLM.
"""

import logging
from dataclasses import dataclass
from typing import Any

from app.core.rag.vector_store import VectorStore, SearchResult, get_vector_store
from app.domain.entities.task import Task
from app.domain.entities.project import Project

logger = logging.getLogger(__name__)


@dataclass
class RetrievalContext:
    """Contexto recuperado para enriquecer prompts."""

    query: str
    similar_tasks: list[dict[str, Any]]
    similar_projects: list[dict[str, Any]]
    relevant_history: list[dict[str, Any]]
    summary: str

    def to_prompt_context(self) -> str:
        """Genera texto de contexto para incluir en prompts."""
        parts = []

        if self.similar_tasks:
            parts.append("**Tareas similares encontradas:**")
            for task in self.similar_tasks[:3]:
                parts.append(f"- {task['title']} (score: {task['score']:.2f})")

        if self.similar_projects:
            parts.append("\n**Proyectos relacionados:**")
            for proj in self.similar_projects[:2]:
                parts.append(f"- {proj['name']} (score: {proj['score']:.2f})")

        if self.relevant_history:
            parts.append("\n**Historial relevante:**")
            for item in self.relevant_history[:3]:
                parts.append(f"- {item['content'][:50]}...")

        return "\n".join(parts) if parts else ""


class RAGRetriever:
    """
    Recuperador de contexto usando RAG.

    Uso:
        retriever = get_retriever()

        # Indexar tareas
        await retriever.index_task(task)

        # Buscar contexto para una query
        context = await retriever.get_context("revisar emails urgentes")

        # Detectar duplicados
        duplicates = await retriever.find_duplicates("Nueva tarea X")
    """

    _instance: "RAGRetriever | None" = None

    def __new__(cls, *args, **kwargs) -> "RAGRetriever":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, vector_store: VectorStore | None = None):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._store = vector_store or get_vector_store()

    async def initialize(self) -> None:
        """Inicializa el retriever."""
        await self._store.initialize()

    # ==================== Indexación ====================

    async def index_task(self, task: Task) -> None:
        """
        Indexa una tarea para búsqueda semántica.

        Args:
            task: Tarea a indexar
        """
        await self._store.add(
            id=f"task_{task.id}",
            content=self._task_to_text(task),
            metadata={
                "type": "task",
                "task_id": task.id,
                "status": task.status.value,
                "priority": task.priority.value,
                "project_id": task.project_id,
            },
        )

    async def index_project(self, project: Project) -> None:
        """
        Indexa un proyecto para búsqueda semántica.

        Args:
            project: Proyecto a indexar
        """
        await self._store.add(
            id=f"project_{project.id}",
            content=self._project_to_text(project),
            metadata={
                "type": "project",
                "project_id": project.id,
                "status": project.status.value,
            },
        )

    async def index_tasks_batch(self, tasks: list[Task]) -> None:
        """Indexa múltiples tareas."""
        items = [
            (
                f"task_{task.id}",
                self._task_to_text(task),
                {
                    "type": "task",
                    "task_id": task.id,
                    "status": task.status.value,
                    "priority": task.priority.value,
                },
            )
            for task in tasks
        ]
        await self._store.add_batch(items)

    async def remove_task(self, task_id: str) -> None:
        """Elimina una tarea del índice."""
        await self._store.delete(f"task_{task_id}")

    async def remove_project(self, project_id: str) -> None:
        """Elimina un proyecto del índice."""
        await self._store.delete(f"project_{project_id}")

    # ==================== Búsqueda ====================

    async def search_tasks(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.3,
    ) -> list[SearchResult]:
        """
        Busca tareas similares a la query.

        Args:
            query: Texto de búsqueda
            limit: Número máximo de resultados
            min_score: Puntuación mínima

        Returns:
            Lista de resultados
        """
        return await self._store.search(
            query=query,
            limit=limit,
            min_score=min_score,
            filter_metadata={"type": "task"},
        )

    async def search_projects(
        self,
        query: str,
        limit: int = 3,
        min_score: float = 0.3,
    ) -> list[SearchResult]:
        """Busca proyectos similares a la query."""
        return await self._store.search(
            query=query,
            limit=limit,
            min_score=min_score,
            filter_metadata={"type": "project"},
        )

    async def search_all(
        self,
        query: str,
        limit: int = 10,
        min_score: float = 0.3,
    ) -> list[SearchResult]:
        """Busca en todos los documentos."""
        return await self._store.search(
            query=query,
            limit=limit,
            min_score=min_score,
        )

    # ==================== Detección de Duplicados ====================

    async def find_duplicates(
        self,
        text: str,
        threshold: float = 0.8,
        limit: int = 5,
    ) -> list[SearchResult]:
        """
        Encuentra posibles duplicados de un texto.

        Útil antes de crear una nueva tarea para detectar si ya existe.

        Args:
            text: Texto a verificar
            threshold: Umbral de similitud (0.8 = 80% similar)
            limit: Máximo de resultados

        Returns:
            Lista de posibles duplicados
        """
        results = await self._store.search(
            query=text,
            limit=limit,
            min_score=threshold,
        )

        return results

    async def is_duplicate(self, text: str, threshold: float = 0.85) -> bool:
        """
        Verifica si un texto es duplicado de algo existente.

        Args:
            text: Texto a verificar
            threshold: Umbral de similitud

        Returns:
            True si es probable duplicado
        """
        duplicates = await self.find_duplicates(text, threshold=threshold, limit=1)
        return len(duplicates) > 0

    # ==================== Contexto para LLM ====================

    async def get_context(
        self,
        query: str,
        include_tasks: bool = True,
        include_projects: bool = True,
        include_history: bool = True,
        limit_per_type: int = 3,
    ) -> RetrievalContext:
        """
        Obtiene contexto relevante para enriquecer prompts LLM.

        Args:
            query: Query del usuario
            include_tasks: Incluir tareas similares
            include_projects: Incluir proyectos relacionados
            include_history: Incluir historial relevante
            limit_per_type: Límite por tipo de documento

        Returns:
            RetrievalContext con toda la información relevante
        """
        similar_tasks = []
        similar_projects = []
        relevant_history = []

        if include_tasks:
            task_results = await self.search_tasks(query, limit=limit_per_type)
            similar_tasks = [
                {
                    "id": r.document.metadata.get("task_id"),
                    "title": r.document.content.split("\n")[0],
                    "score": r.score,
                }
                for r in task_results
            ]

        if include_projects:
            project_results = await self.search_projects(query, limit=limit_per_type)
            similar_projects = [
                {
                    "id": r.document.metadata.get("project_id"),
                    "name": r.document.content.split("\n")[0],
                    "score": r.score,
                }
                for r in project_results
            ]

        # Generar resumen
        summary_parts = []
        if similar_tasks:
            summary_parts.append(f"Encontradas {len(similar_tasks)} tareas similares")
        if similar_projects:
            summary_parts.append(f"Encontrados {len(similar_projects)} proyectos relacionados")

        return RetrievalContext(
            query=query,
            similar_tasks=similar_tasks,
            similar_projects=similar_projects,
            relevant_history=relevant_history,
            summary=". ".join(summary_parts) if summary_parts else "Sin contexto adicional",
        )

    # ==================== Helpers ====================

    @staticmethod
    def _task_to_text(task: Task) -> str:
        """Convierte una tarea a texto para indexar."""
        parts = [task.title]

        if task.notes:
            parts.append(task.notes)

        if task.context:
            parts.append(f"Contexto: {task.context}")

        if task.project_name:
            parts.append(f"Proyecto: {task.project_name}")

        return "\n".join(parts)

    @staticmethod
    def _project_to_text(project: Project) -> str:
        """Convierte un proyecto a texto para indexar."""
        parts = [project.name]

        if project.description:
            parts.append(project.description)

        if project.objective:
            parts.append(f"Objetivo: {project.objective}")

        return "\n".join(parts)


# Singleton
_retriever: RAGRetriever | None = None


def get_retriever() -> RAGRetriever:
    """Obtiene la instancia del RAGRetriever."""
    global _retriever
    if _retriever is None:
        _retriever = RAGRetriever()
    return _retriever
