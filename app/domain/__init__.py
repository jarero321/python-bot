"""
Domain module - Entidades y repositorios del dominio.

Este módulo implementa el patrón Repository para desacoplar
la lógica de negocio de la persistencia (Notion).

Estructura:
    - entities/: Dataclasses que representan el dominio
    - repositories/: Interfaces y implementaciones de persistencia
"""

from app.domain.entities import (
    Task,
    Project,
    Reminder,
    InboxItem,
    WorkoutEntry,
    NutritionEntry,
    Transaction,
    Debt,
)
from app.domain.repositories import (
    ITaskRepository,
    IProjectRepository,
    IReminderRepository,
    get_task_repository,
    get_project_repository,
)

__all__ = [
    # Entities
    "Task",
    "Project",
    "Reminder",
    "InboxItem",
    "WorkoutEntry",
    "NutritionEntry",
    "Transaction",
    "Debt",
    # Repositories
    "ITaskRepository",
    "IProjectRepository",
    "IReminderRepository",
    "get_task_repository",
    "get_project_repository",
]
