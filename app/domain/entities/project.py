"""
Project Entity - Representación de un proyecto del dominio.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class ProjectType(str, Enum):
    """Tipos de proyecto."""
    WORK = "work"
    FREELANCE = "freelance"
    LEARNING = "learning"
    SIDE_PROJECT = "side_project"
    PERSONAL = "personal"
    HOBBY = "hobby"
    FINANCIAL = "financial"
    SEARCH = "search"  # Job search, etc.


class ProjectStatus(str, Enum):
    """Estados de proyecto."""
    IDEA = "idea"
    PLANNING = "planning"
    ACTIVE = "active"
    WAITING = "waiting"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class Project:
    """
    Entidad de Proyecto.

    Representa un proyecto independiente del sistema de persistencia.
    """

    id: str
    name: str
    type: ProjectType = ProjectType.PERSONAL
    status: ProjectStatus = ProjectStatus.IDEA

    # Descripción
    description: str | None = None
    objective: str | None = None

    # Fechas
    start_date: date | None = None
    target_date: date | None = None
    completed_at: datetime | None = None

    # Progreso
    progress: int = 0  # 0-100
    total_tasks: int = 0
    completed_tasks: int = 0

    # Contexto
    area: str | None = None  # Área de vida (Trabajo, Personal, etc.)
    tags: list[str] = field(default_factory=list)

    # Relaciones
    parent_project_id: str | None = None
    task_ids: list[str] = field(default_factory=list)

    # URLs y recursos
    repository_url: str | None = None
    documentation_url: str | None = None

    # Metadata
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Raw data
    _raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_active(self) -> bool:
        """Verifica si el proyecto está activo."""
        return self.status in (ProjectStatus.ACTIVE, ProjectStatus.PLANNING)

    @property
    def is_completed(self) -> bool:
        """Verifica si está completado."""
        return self.status == ProjectStatus.COMPLETED

    @property
    def days_until_target(self) -> int | None:
        """Días hasta la fecha objetivo."""
        if not self.target_date:
            return None
        return (self.target_date - date.today()).days

    @property
    def is_overdue(self) -> bool:
        """Verifica si está pasado de la fecha objetivo."""
        if not self.target_date:
            return False
        if self.is_completed:
            return False
        return self.target_date < date.today()

    @property
    def completion_rate(self) -> float:
        """Tasa de completitud basada en tareas."""
        if self.total_tasks == 0:
            return 0.0
        return self.completed_tasks / self.total_tasks

    def to_dict(self) -> dict[str, Any]:
        """Convierte a diccionario para serialización."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "status": self.status.value,
            "description": self.description,
            "progress": self.progress,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "target_date": self.target_date.isoformat() if self.target_date else None,
            "is_active": self.is_active,
            "is_overdue": self.is_overdue,
            "completion_rate": self.completion_rate,
        }


@dataclass
class ProjectFilter:
    """Filtros para búsqueda de proyectos."""

    type: ProjectType | list[ProjectType] | None = None
    status: ProjectStatus | list[ProjectStatus] | None = None
    area: str | None = None
    is_active: bool | None = None
    search_text: str | None = None
    limit: int = 50
    offset: int = 0
