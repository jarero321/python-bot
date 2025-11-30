"""Domain Repositories - Interfaces y implementaciones."""

from app.domain.repositories.base import (
    IRepository,
    ITaskRepository,
    IProjectRepository,
    IReminderRepository,
)
from app.domain.repositories.notion_task_repository import NotionTaskRepository
from app.domain.repositories.notion_project_repository import NotionProjectRepository

# Singletons
_task_repository: ITaskRepository | None = None
_project_repository: IProjectRepository | None = None


def get_task_repository() -> ITaskRepository:
    """Obtiene el repositorio de tareas (singleton)."""
    global _task_repository
    if _task_repository is None:
        _task_repository = NotionTaskRepository()
    return _task_repository


def get_project_repository() -> IProjectRepository:
    """Obtiene el repositorio de proyectos (singleton)."""
    global _project_repository
    if _project_repository is None:
        _project_repository = NotionProjectRepository()
    return _project_repository


__all__ = [
    # Interfaces
    "IRepository",
    "ITaskRepository",
    "IProjectRepository",
    "IReminderRepository",
    # Implementations
    "NotionTaskRepository",
    "NotionProjectRepository",
    # Getters
    "get_task_repository",
    "get_project_repository",
]
