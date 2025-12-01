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
        from app.agents.workout_logger import WorkoutType

        # Intentar detectar tipo de workout del mensaje
        message_lower = message.lower()
        workout_type = WorkoutType.PUSH  # Default

        if any(word in message_lower for word in ["pull", "espalda", "bicep", "remo", "dominada"]):
            workout_type = WorkoutType.PULL
        elif any(word in message_lower for word in ["leg", "pierna", "sentadilla", "squat"]):
            workout_type = WorkoutType.LEGS
        elif any(word in message_lower for word in ["cardio", "correr", "bici", "running"]):
            workout_type = WorkoutType.CARDIO

        # Si viene en entities, usar ese
        if "workout_type" in entities:
            type_map = {
                "push": WorkoutType.PUSH,
                "pull": WorkoutType.PULL,
                "legs": WorkoutType.LEGS,
                "cardio": WorkoutType.CARDIO,
            }
            workout_type = type_map.get(entities["workout_type"].lower(), WorkoutType.PUSH)

        try:
            workout_result = await self.workout_logger.log_workout(
                workout_description=message,
                workout_type=workout_type,
            )

            result.workout_data = {
                "workout_type": workout_type.value,
                "exercises": [
                    {
                        "name": ex.name,
                        "sets": [
                            {"reps": s.reps, "weight": s.weight}
                            for s in ex.sets
                        ],
                        "notes": ex.notes,
                        "pr": ex.pr,
                    }
                    for ex in workout_result.exercises
                ],
                "rating": workout_result.session_rating.value,
                "feedback": workout_result.feedback,
                "new_prs": workout_result.new_prs,
                "next_targets": workout_result.next_targets,
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
            # Usar quick_log para registro rápido de una comida
            meal_result = await self.nutrition_analyzer.quick_log(
                meal_type=meal_type,
                description=message,
            )

            result.nutrition_data = {
                "meal_type": meal_type,
                "description": meal_result.description,
                "calories": meal_result.calories,
                "category": meal_result.category,
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
