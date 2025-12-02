"""
Domain module - Entidades y repositorios del dominio.

Este módulo implementa el patrón Repository para desacoplar
la lógica de negocio de la persistencia (Notion).

Estructura:
    - entities/: Dataclasses que representan el dominio
    - repositories/: Interfaces y implementaciones de persistencia

NOTA: Los repositories NO se exportan aquí para evitar imports circulares.
Importar directamente de app.domain.repositories cuando se necesiten.
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
]
