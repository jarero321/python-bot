"""
Repository Interfaces - Contratos para la capa de persistencia.

Estas interfaces definen los métodos que cualquier implementación
de repositorio debe proveer, permitiendo cambiar de Notion a otro
backend sin modificar la lógica de negocio.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Generic, TypeVar

from app.domain.entities.task import Task, TaskFilter, TaskStatus, TaskPriority
from app.domain.entities.project import Project, ProjectFilter, ProjectStatus
from app.domain.entities.reminder import Reminder

T = TypeVar("T")


class IRepository(ABC, Generic[T]):
    """
    Interface base para repositorios.

    Define operaciones CRUD genéricas.
    """

    @abstractmethod
    async def get_by_id(self, id: str) -> T | None:
        """Obtiene una entidad por su ID."""
        pass

    @abstractmethod
    async def create(self, entity: T) -> T:
        """Crea una nueva entidad."""
        pass

    @abstractmethod
    async def update(self, entity: T) -> T:
        """Actualiza una entidad existente."""
        pass

    @abstractmethod
    async def delete(self, id: str) -> bool:
        """Elimina una entidad por su ID."""
        pass


class ITaskRepository(IRepository[Task]):
    """
    Interface para repositorio de tareas.

    Define todas las operaciones disponibles para gestionar tareas,
    independiente de la implementación (Notion, PostgreSQL, etc.).
    """

    # ==================== CRUD Básico ====================

    @abstractmethod
    async def get_by_id(self, id: str) -> Task | None:
        """Obtiene una tarea por su ID."""
        pass

    @abstractmethod
    async def create(self, task: Task) -> Task:
        """Crea una nueva tarea."""
        pass

    @abstractmethod
    async def update(self, task: Task) -> Task:
        """Actualiza una tarea existente."""
        pass

    @abstractmethod
    async def delete(self, id: str) -> bool:
        """Elimina una tarea."""
        pass

    # ==================== Queries ====================

    @abstractmethod
    async def find(self, filter: TaskFilter) -> list[Task]:
        """Busca tareas según filtros."""
        pass

    @abstractmethod
    async def get_for_today(self) -> list[Task]:
        """Obtiene tareas programadas para hoy."""
        pass

    @abstractmethod
    async def get_pending(self, limit: int = 50) -> list[Task]:
        """Obtiene tareas pendientes (no completadas/canceladas)."""
        pass

    @abstractmethod
    async def get_overdue(self) -> list[Task]:
        """Obtiene tareas vencidas."""
        pass

    @abstractmethod
    async def get_completed_today(self) -> list[Task]:
        """Obtiene tareas completadas hoy."""
        pass

    @abstractmethod
    async def get_by_project(self, project_id: str) -> list[Task]:
        """Obtiene tareas de un proyecto."""
        pass

    @abstractmethod
    async def get_by_status(self, status: TaskStatus) -> list[Task]:
        """Obtiene tareas por estado."""
        pass

    @abstractmethod
    async def get_by_priority(self, priority: TaskPriority) -> list[Task]:
        """Obtiene tareas por prioridad."""
        pass

    @abstractmethod
    async def get_scheduled_for(self, date: date) -> list[Task]:
        """Obtiene tareas programadas para una fecha."""
        pass

    @abstractmethod
    async def get_subtasks(self, parent_id: str) -> list[Task]:
        """Obtiene subtareas de una tarea."""
        pass

    # ==================== Updates Específicos ====================

    @abstractmethod
    async def update_status(self, id: str, status: TaskStatus) -> Task | None:
        """Actualiza el estado de una tarea."""
        pass

    @abstractmethod
    async def update_priority(self, id: str, priority: TaskPriority) -> Task | None:
        """Actualiza la prioridad de una tarea."""
        pass

    @abstractmethod
    async def reschedule(self, id: str, new_date: date) -> Task | None:
        """Reprograma una tarea para otra fecha."""
        pass

    @abstractmethod
    async def complete(self, id: str) -> Task | None:
        """Marca una tarea como completada."""
        pass

    # ==================== Aggregates ====================

    @abstractmethod
    async def count_by_status(self) -> dict[TaskStatus, int]:
        """Cuenta tareas por estado."""
        pass

    @abstractmethod
    async def count_by_priority(self) -> dict[TaskPriority, int]:
        """Cuenta tareas por prioridad."""
        pass

    @abstractmethod
    async def get_workload_summary(self) -> dict[str, Any]:
        """Obtiene resumen de carga de trabajo."""
        pass


class IProjectRepository(IRepository[Project]):
    """
    Interface para repositorio de proyectos.
    """

    # ==================== CRUD Básico ====================

    @abstractmethod
    async def get_by_id(self, id: str) -> Project | None:
        """Obtiene un proyecto por su ID."""
        pass

    @abstractmethod
    async def create(self, project: Project) -> Project:
        """Crea un nuevo proyecto."""
        pass

    @abstractmethod
    async def update(self, project: Project) -> Project:
        """Actualiza un proyecto existente."""
        pass

    @abstractmethod
    async def delete(self, id: str) -> bool:
        """Elimina un proyecto."""
        pass

    # ==================== Queries ====================

    @abstractmethod
    async def find(self, filter: ProjectFilter) -> list[Project]:
        """Busca proyectos según filtros."""
        pass

    @abstractmethod
    async def get_active(self) -> list[Project]:
        """Obtiene proyectos activos."""
        pass

    @abstractmethod
    async def get_by_status(self, status: ProjectStatus) -> list[Project]:
        """Obtiene proyectos por estado."""
        pass

    @abstractmethod
    async def search_by_name(self, query: str) -> list[Project]:
        """Busca proyectos por nombre."""
        pass

    # ==================== Updates Específicos ====================

    @abstractmethod
    async def update_status(self, id: str, status: ProjectStatus) -> Project | None:
        """Actualiza el estado de un proyecto."""
        pass

    @abstractmethod
    async def update_progress(self, id: str, progress: int) -> Project | None:
        """Actualiza el progreso de un proyecto."""
        pass

    @abstractmethod
    async def complete(self, id: str) -> Project | None:
        """Marca un proyecto como completado."""
        pass


class IReminderRepository(IRepository[Reminder]):
    """
    Interface para repositorio de recordatorios.
    """

    @abstractmethod
    async def get_by_id(self, id: str) -> Reminder | None:
        """Obtiene un recordatorio por su ID."""
        pass

    @abstractmethod
    async def create(self, reminder: Reminder) -> Reminder:
        """Crea un nuevo recordatorio."""
        pass

    @abstractmethod
    async def update(self, reminder: Reminder) -> Reminder:
        """Actualiza un recordatorio."""
        pass

    @abstractmethod
    async def delete(self, id: str) -> bool:
        """Elimina un recordatorio."""
        pass

    @abstractmethod
    async def get_pending_for_user(self, user_id: int) -> list[Reminder]:
        """Obtiene recordatorios pendientes de un usuario."""
        pass

    @abstractmethod
    async def get_due(self) -> list[Reminder]:
        """Obtiene recordatorios que ya vencieron."""
        pass

    @abstractmethod
    async def mark_as_sent(self, id: str) -> Reminder | None:
        """Marca un recordatorio como enviado."""
        pass

    @abstractmethod
    async def snooze(self, id: str, minutes: int) -> Reminder | None:
        """Pospone un recordatorio."""
        pass
