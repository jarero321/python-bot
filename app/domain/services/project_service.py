"""
Project Service - Servicio de dominio para proyectos.

Combina el repositorio de proyectos con el sistema RAG.
"""

import logging
from dataclasses import dataclass
from typing import Any

from app.domain.entities.project import Project, ProjectStatus, ProjectType, ProjectFilter
from app.domain.repositories import get_project_repository, IProjectRepository
from app.core.rag import get_retriever, RAGRetriever

logger = logging.getLogger(__name__)


@dataclass
class ProjectSearchResult:
    """Resultado de búsqueda de proyectos."""

    projects: list[Project]
    query: str
    used_semantic: bool
    total_found: int


class ProjectService:
    """
    Servicio de dominio para proyectos.

    Combina repositorio + RAG para operaciones avanzadas.
    """

    _instance: "ProjectService | None" = None

    def __new__(cls, *args, **kwargs) -> "ProjectService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        project_repo: IProjectRepository | None = None,
        retriever: RAGRetriever | None = None,
    ):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._repo = project_repo or get_project_repository()
        self._retriever = retriever or get_retriever()
        self._rag_enabled = False

    async def initialize(self) -> None:
        """Inicializa el servicio."""
        try:
            await self._retriever.initialize()
            self._rag_enabled = True
            logger.info("ProjectService inicializado con RAG")
        except Exception as e:
            logger.warning(f"RAG no disponible para proyectos: {e}")
            self._rag_enabled = False

    # ==================== CRUD ====================

    async def create(self, project: Project) -> Project:
        """Crea un proyecto e indexa en RAG."""
        created = await self._repo.create(project)

        if self._rag_enabled:
            try:
                await self._retriever.index_project(created)
            except Exception as e:
                logger.warning(f"Error indexando proyecto: {e}")

        return created

    async def update(self, project: Project) -> Project:
        """Actualiza un proyecto."""
        updated = await self._repo.update(project)

        if self._rag_enabled:
            try:
                await self._retriever.index_project(updated)
            except Exception as e:
                logger.warning(f"Error re-indexando proyecto: {e}")

        return updated

    async def complete(self, project_id: str) -> Project | None:
        """Completa un proyecto."""
        return await self._repo.complete(project_id)

    # ==================== Búsqueda ====================

    async def smart_search(
        self,
        query: str,
        limit: int = 10,
    ) -> ProjectSearchResult:
        """
        Búsqueda inteligente de proyectos.

        Args:
            query: Texto de búsqueda
            limit: Máximo de resultados

        Returns:
            ProjectSearchResult
        """
        projects: list[Project] = []
        used_semantic = False

        # Intentar búsqueda semántica
        if self._rag_enabled:
            try:
                rag_results = await self._retriever.search_projects(query, limit=limit)

                if rag_results:
                    used_semantic = True
                    for result in rag_results:
                        project_id = result.document.metadata.get("project_id")
                        if project_id:
                            project = await self._repo.get_by_id(project_id)
                            if project and project.is_active:
                                projects.append(project)
            except Exception as e:
                logger.warning(f"Error en búsqueda semántica de proyectos: {e}")

        # Fallback a búsqueda por texto
        if not projects:
            projects = await self._repo.search_by_name(query)

        return ProjectSearchResult(
            projects=projects[:limit],
            query=query,
            used_semantic=used_semantic,
            total_found=len(projects),
        )

    # ==================== Queries ====================

    async def get_active(self) -> list[Project]:
        """Obtiene proyectos activos."""
        return await self._repo.get_active()

    async def get_by_status(self, status: ProjectStatus) -> list[Project]:
        """Obtiene proyectos por estado."""
        return await self._repo.get_by_status(status)

    async def search_by_name(self, query: str) -> list[Project]:
        """Busca proyectos por nombre."""
        return await self._repo.search_by_name(query)

    async def update_progress(self, project_id: str, progress: int) -> Project | None:
        """Actualiza el progreso de un proyecto."""
        return await self._repo.update_progress(project_id, progress)


# Singleton
_project_service: ProjectService | None = None


def get_project_service() -> ProjectService:
    """Obtiene la instancia del ProjectService."""
    global _project_service
    if _project_service is None:
        _project_service = ProjectService()
    return _project_service
