"""
Fitness Entities - Workout y Nutrition.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


# ==================== WORKOUT ====================


class WorkoutType(str, Enum):
    """Tipos de entrenamiento."""
    PUSH = "push"
    PULL = "pull"
    LEGS = "legs"
    CARDIO = "cardio"
    REST = "rest"
    FULL_BODY = "full_body"


class WorkoutFeeling(str, Enum):
    """Sensación del entrenamiento."""
    STRONG = "strong"
    NORMAL = "normal"
    HEAVY = "heavy"
    PAIN = "pain"


@dataclass
class Exercise:
    """Un ejercicio dentro del workout."""
    name: str
    sets: int | None = None
    reps: int | None = None
    weight: float | None = None  # kg
    notes: str | None = None
    is_pr: bool = False  # Personal Record


@dataclass
class WorkoutEntry:
    """
    Entidad de Workout.

    Representa una sesión de entrenamiento.
    """

    id: str
    date: date
    type: WorkoutType
    feeling: WorkoutFeeling = WorkoutFeeling.NORMAL

    # Ejercicios
    exercises: list[Exercise] = field(default_factory=list)
    prs: list[str] = field(default_factory=list)  # Lista de PRs del día

    # Duración
    duration_minutes: int | None = None

    # Notas
    notes: str | None = None

    # Metadata
    created_at: datetime | None = None

    # Raw data
    _raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def total_volume(self) -> float:
        """Volumen total (sets * reps * weight)."""
        total = 0.0
        for ex in self.exercises:
            if ex.sets and ex.reps and ex.weight:
                total += ex.sets * ex.reps * ex.weight
        return total

    @property
    def has_prs(self) -> bool:
        """Verifica si hubo PRs."""
        return len(self.prs) > 0 or any(ex.is_pr for ex in self.exercises)

    def to_dict(self) -> dict[str, Any]:
        """Convierte a diccionario."""
        return {
            "id": self.id,
            "date": self.date.isoformat(),
            "type": self.type.value,
            "feeling": self.feeling.value,
            "exercises": [
                {
                    "name": ex.name,
                    "sets": ex.sets,
                    "reps": ex.reps,
                    "weight": ex.weight,
                    "is_pr": ex.is_pr,
                }
                for ex in self.exercises
            ],
            "prs": self.prs,
            "duration_minutes": self.duration_minutes,
            "total_volume": self.total_volume,
        }


# ==================== NUTRITION ====================


class NutritionCategory(str, Enum):
    """Categoría de comida."""
    HEALTHY = "healthy"
    MODERATE = "moderate"
    HEAVY = "heavy"


class MealType(str, Enum):
    """Tipo de comida."""
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


@dataclass
class NutritionEntry:
    """
    Entidad de Nutrición.

    Representa una entrada de comida.
    """

    id: str
    date: date
    meal_type: MealType
    description: str
    category: NutritionCategory = NutritionCategory.MODERATE

    # Macros (estimados)
    calories: int | None = None
    protein: int | None = None  # gramos
    carbs: int | None = None
    fat: int | None = None

    # Evaluación
    notes: str | None = None
    ai_feedback: str | None = None

    # Metadata
    created_at: datetime | None = None

    # Raw data
    _raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Convierte a diccionario."""
        return {
            "id": self.id,
            "date": self.date.isoformat(),
            "meal_type": self.meal_type.value,
            "description": self.description,
            "category": self.category.value,
            "calories": self.calories,
            "protein": self.protein,
            "carbs": self.carbs,
            "fat": self.fat,
        }
