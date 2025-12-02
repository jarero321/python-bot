"""
Task Entity - Representación de una tarea del dominio.

Esta entidad es independiente de Notion y puede ser usada
con cualquier backend de persistencia.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    """Estados de tarea."""
    BACKLOG = "backlog"
    PLANNED = "planned"
    TODAY = "today"
    DOING = "doing"
    PAUSED = "paused"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Prioridades de tarea."""
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class TaskComplexity(str, Enum):
    """Complejidad de tarea."""
    QUICK = "quick"      # <30m
    STANDARD = "standard"  # 30m-2h
    HEAVY = "heavy"      # 2-4h
    EPIC = "epic"        # 4h+


class TaskEnergy(str, Enum):
    """Energía requerida."""
    DEEP_WORK = "deep_work"
    MEDIUM = "medium"
    LOW = "low"


class TaskTimeBlock(str, Enum):
    """Bloques de tiempo preferidos."""
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"


@dataclass
class Task:
    """
    Entidad de Tarea.

    Representa una tarea independiente del sistema de persistencia.
    Los IDs de Notion se mapean pero la entidad no depende de Notion.
    """

    id: str
    title: str
    status: TaskStatus = TaskStatus.BACKLOG
    priority: TaskPriority = TaskPriority.NORMAL
    complexity: TaskComplexity | None = None
    energy: TaskEnergy | None = None
    time_block: TaskTimeBlock | None = None

    # Fechas
    due_date: date | None = None
    scheduled_date: date | None = None
    completed_at: datetime | None = None

    # Relaciones
    project_id: str | None = None
    project_name: str | None = None
    parent_task_id: str | None = None
    subtask_ids: list[str] = field(default_factory=list)

    # Dependencias (bloqueada por otra tarea)
    blocked_by_id: str | None = None  # ID de la tarea que bloquea esta
    blocked_by_name: str | None = None  # Nombre para mostrar
    blocker_reason: str | None = None  # Razón del bloqueo

    # Contexto
    context: str | None = None  # PayCash, Freelance, Personal, etc.
    tags: list[str] = field(default_factory=list)
    notes: str | None = None

    # Estimación
    estimated_minutes: int | None = None
    actual_minutes: int | None = None

    # Metadata
    created_at: datetime | None = None
    updated_at: datetime | None = None
    source: str = "manual"  # manual, telegram, api

    # Raw data para debugging
    _raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_overdue(self) -> bool:
        """Verifica si la tarea está vencida."""
        if not self.due_date:
            return False
        if self.status in (TaskStatus.DONE, TaskStatus.CANCELLED):
            return False
        return self.due_date < date.today()

    @property
    def is_active(self) -> bool:
        """Verifica si la tarea está activa (no completada/cancelada)."""
        return self.status not in (TaskStatus.DONE, TaskStatus.CANCELLED)

    @property
    def is_urgent(self) -> bool:
        """Verifica si es urgente."""
        return self.priority == TaskPriority.URGENT

    @property
    def is_blocked(self) -> bool:
        """Verifica si la tarea está bloqueada por otra."""
        return self.blocked_by_id is not None

    @property
    def days_until_due(self) -> int | None:
        """Días hasta el deadline."""
        if not self.due_date:
            return None
        return (self.due_date - date.today()).days

    def to_dict(self) -> dict[str, Any]:
        """Convierte a diccionario para serialización."""
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status.value,
            "priority": self.priority.value,
            "complexity": self.complexity.value if self.complexity else None,
            "energy": self.energy.value if self.energy else None,
            "time_block": self.time_block.value if self.time_block else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "scheduled_date": self.scheduled_date.isoformat() if self.scheduled_date else None,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "context": self.context,
            "tags": self.tags,
            "notes": self.notes,
            "estimated_minutes": self.estimated_minutes,
            "is_overdue": self.is_overdue,
            "is_blocked": self.is_blocked,
            "blocked_by_id": self.blocked_by_id,
            "blocked_by_name": self.blocked_by_name,
            "blocker_reason": self.blocker_reason,
            "days_until_due": self.days_until_due,
        }


@dataclass
class TaskFilter:
    """Filtros para búsqueda de tareas."""

    status: TaskStatus | list[TaskStatus] | None = None
    priority: TaskPriority | list[TaskPriority] | None = None
    project_id: str | None = None
    context: str | None = None
    due_before: date | None = None
    due_after: date | None = None
    scheduled_for: date | None = None
    is_overdue: bool | None = None
    search_text: str | None = None
    limit: int = 50
    offset: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convierte a dict para logging/debugging."""
        return {
            k: v for k, v in {
                "status": self.status,
                "priority": self.priority,
                "project_id": self.project_id,
                "context": self.context,
                "due_before": self.due_before,
                "due_after": self.due_after,
                "scheduled_for": self.scheduled_for,
                "is_overdue": self.is_overdue,
                "search_text": self.search_text,
                "limit": self.limit,
            }.items() if v is not None
        }
