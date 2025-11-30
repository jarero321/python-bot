"""
Fitness Enricher - Enriquece intents de fitness y nutrición.

Integra:
- WorkoutLoggerAgent: Registra entrenamientos
- NutritionAnalyzerAgent: Analiza nutrición
"""

import logging
from typing import Any

from app.agents.enrichers.base import BaseEnricher, EnrichmentResult
from app.agents.intent_router import UserIntent
from app.agents.workout_logger import WorkoutLoggerAgent
from app.agents.nutrition_analyzer import NutritionAnalyzerAgent

logger = logging.getLogger(__name__)


class FitnessEnricher(BaseEnricher):
    """Enricher para fitness - usa WorkoutLogger y NutritionAnalyzer."""

    name = "FitnessEnricher"
    intents = [
        UserIntent.GYM_LOG,
        UserIntent.GYM_QUERY,
        UserIntent.NUTRITION_LOG,
        UserIntent.NUTRITION_QUERY,
    ]

    def __init__(self):
        super().__init__()
        self._workout_logger: WorkoutLoggerAgent | None = None
        self._nutrition_analyzer: NutritionAnalyzerAgent | None = None

    @property
    def workout_logger(self) -> WorkoutLoggerAgent:
        if self._workout_logger is None:
            self._workout_logger = WorkoutLoggerAgent()
        return self._workout_logger

    @property
    def nutrition_analyzer(self) -> NutritionAnalyzerAgent:
        if self._nutrition_analyzer is None:
            self._nutrition_analyzer = NutritionAnalyzerAgent()
        return self._nutrition_analyzer

    async def enrich(
        self,
        intent: UserIntent,
        message: str,
        entities: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> EnrichmentResult:
        """Enriquece intent de fitness."""
        result = EnrichmentResult(enricher_name=self.name)

        if intent == UserIntent.GYM_LOG:
            await self._enrich_gym_log(message, entities, result)
        elif intent == UserIntent.GYM_QUERY:
            await self._enrich_gym_query(message, entities, result)
        elif intent == UserIntent.NUTRITION_LOG:
            await self._enrich_nutrition_log(message, entities, result)
        elif intent == UserIntent.NUTRITION_QUERY:
            await self._enrich_nutrition_query(message, entities, result)

        return result

    async def _enrich_gym_log(
        self,
        message: str,
        entities: dict[str, Any],
        result: EnrichmentResult,
    ) -> None:
        """Enriquece registro de entrenamiento."""
        try:
            workout_result = await self.workout_logger.log_workout(message)

            result.workout_data = {
                "workout_type": workout_result.workout_type.value,
                "exercises": [
                    {
                        "name": ex.name,
                        "sets": [
                            {"reps": s.reps, "weight": s.weight, "rest": s.rest_seconds}
                            for s in ex.sets
                        ],
                        "notes": ex.notes,
                    }
                    for ex in workout_result.exercises
                ],
                "duration_minutes": workout_result.duration_minutes,
                "rating": workout_result.session_rating.value,
                "notes": workout_result.notes,
                "calories_burned": workout_result.calories_burned,
                "muscle_groups": workout_result.muscle_groups,
            }
            result.agents_used.append("WorkoutLogger")

        except Exception as e:
            self.logger.warning(f"Error en WorkoutLogger: {e}")
            result.workout_data = {
                "raw_input": message,
                "error": str(e),
            }

    async def _enrich_gym_query(
        self,
        message: str,
        entities: dict[str, Any],
        result: EnrichmentResult,
    ) -> None:
        """Enriquece consulta de entrenamientos."""
        result.workout_data = {
            "query_type": "history",
            "raw_query": message,
        }

    async def _enrich_nutrition_log(
        self,
        message: str,
        entities: dict[str, Any],
        result: EnrichmentResult,
    ) -> None:
        """Enriquece registro de nutrición."""
        meal_type = entities.get("meal", "comida")

        try:
            nutrition_result = await self.nutrition_analyzer.analyze_meal(
                meal_description=message,
                meal_type=meal_type,
            )

            result.nutrition_data = {
                "meal_type": meal_type,
                "calories": nutrition_result.total_calories,
                "protein": nutrition_result.protein_grams,
                "carbs": nutrition_result.carbs_grams,
                "fat": nutrition_result.fat_grams,
                "fiber": nutrition_result.fiber_grams,
                "rating": nutrition_result.rating.value,
                "feedback": nutrition_result.feedback,
                "suggestions": nutrition_result.suggestions,
                "breakdown": [
                    {
                        "food": item.food_name,
                        "portion": item.portion,
                        "calories": item.calories,
                    }
                    for item in nutrition_result.meal_breakdown
                ],
            }
            result.agents_used.append("NutritionAnalyzer")

        except Exception as e:
            self.logger.warning(f"Error en NutritionAnalyzer: {e}")
            result.nutrition_data = {
                "meal_type": meal_type,
                "raw_input": message,
                "error": str(e),
            }

    async def _enrich_nutrition_query(
        self,
        message: str,
        entities: dict[str, Any],
        result: EnrichmentResult,
    ) -> None:
        """Enriquece consulta de nutrición."""
        result.nutrition_data = {
            "query_type": "history",
            "raw_query": message,
        }
