"""Domain Entities - Dataclasses del dominio."""

from app.domain.entities.task import Task, TaskFilter
from app.domain.entities.project import Project, ProjectFilter
from app.domain.entities.reminder import Reminder
from app.domain.entities.inbox import InboxItem
from app.domain.entities.fitness import WorkoutEntry, NutritionEntry
from app.domain.entities.finance import Transaction, Debt

__all__ = [
    "Task",
    "TaskFilter",
    "Project",
    "ProjectFilter",
    "Reminder",
    "InboxItem",
    "WorkoutEntry",
    "NutritionEntry",
    "Transaction",
    "Debt",
]
