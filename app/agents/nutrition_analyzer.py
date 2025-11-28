"""NutritionAnalyzer Agent - Analiza las comidas del día."""

import logging
from dataclasses import dataclass
from enum import Enum

import dspy

from app.agents.base import get_dspy_lm, AnalyzeNutrition

logger = logging.getLogger(__name__)


class NutritionGoal(str, Enum):
    """Objetivos de nutrición."""

    PERDER_PESO = "perder_peso"
    MANTENER = "mantener"
    GANAR_MUSCULO = "ganar_musculo"


class ActivityLevel(str, Enum):
    """Nivel de actividad del día."""

    GYM_DAY = "gym_day"
    REST_DAY = "rest_day"
    ACTIVE = "active"


class NutritionRating(str, Enum):
    """Evaluación del día de nutrición."""

    EXCELLENT = "excellent"
    GOOD = "good"
    MODERATE = "moderate"
    POOR = "poor"


class ProteinStatus(str, Enum):
    """Estado de proteína."""

    SUFFICIENT = "sufficient"
    LOW = "low"
    HIGH = "high"


@dataclass
class MealBreakdown:
    """Desglose de una comida."""

    name: str
    description: str
    calories: int
    category: str  # saludable, moderado, pesado


@dataclass
class NutritionResult:
    """Resultado del análisis de nutrición."""

    meals_breakdown: list[MealBreakdown]
    total_calories: int
    protein_status: ProteinStatus
    vegetables_count: int
    overall_rating: NutritionRating
    specific_feedback: str
    pattern_detected: str
    tomorrow_suggestion: str


class NutritionAnalyzerAgent:
    """Agente para analizar nutrición del día."""

    def __init__(self):
        self.lm = get_dspy_lm()
        dspy.configure(lm=self.lm)
        self.analyzer = dspy.ChainOfThought(AnalyzeNutrition)

        # Objetivos de Carlos (de Documentacion.MD)
        self.user_goals = NutritionGoal.PERDER_PESO
        self.target_calories = 2000  # Aproximado para pérdida de peso

    async def analyze_meals(
        self,
        meals_description: str,
        activity_today: ActivityLevel = ActivityLevel.REST_DAY,
        recent_history: list[dict] | None = None,
    ) -> NutritionResult:
        """
        Analiza las comidas del día.

        Args:
            meals_description: Descripción de lo que comió
            activity_today: Si fue día de gym, descanso, etc.
            recent_history: Historial de nutrición reciente

        Returns:
            NutritionResult con el análisis completo
        """
        try:
            # Formatear historial
            history_str = ""
            if recent_history:
                history_items = []
                for day in recent_history[:7]:
                    date = day.get("fecha", "?")
                    rating = day.get("evaluacion", "?")
                    cals = day.get("total_cal", "?")
                    history_items.append(f"- {date}: {rating} ({cals} cal)")
                history_str = "\n".join(history_items)
            else:
                history_str = "Sin historial disponible"

            # Ejecutar análisis
            result = self.analyzer(
                meals_description=meals_description,
                user_goals=self.user_goals.value,
                activity_today=activity_today.value,
                recent_nutrition_history=history_str,
            )

            # Parsear meals breakdown
            meals = self._parse_meals_breakdown(result.meals_breakdown)

            # Parsear calorías
            try:
                total_cals = int(result.total_calories)
            except (ValueError, TypeError):
                total_cals = sum(m.calories for m in meals)

            # Parsear protein status
            protein_map = {
                "sufficient": ProteinStatus.SUFFICIENT,
                "low": ProteinStatus.LOW,
                "high": ProteinStatus.HIGH,
            }
            protein = protein_map.get(
                str(result.protein_status).lower(), ProteinStatus.LOW
            )

            # Parsear vegetables count
            try:
                veggies = int(result.vegetables_count)
            except (ValueError, TypeError):
                veggies = 0

            # Parsear rating
            rating_map = {
                "excellent": NutritionRating.EXCELLENT,
                "good": NutritionRating.GOOD,
                "moderate": NutritionRating.MODERATE,
                "poor": NutritionRating.POOR,
            }
            rating = rating_map.get(
                str(result.overall_rating).lower(), NutritionRating.MODERATE
            )

            return NutritionResult(
                meals_breakdown=meals,
                total_calories=total_cals,
                protein_status=protein,
                vegetables_count=veggies,
                overall_rating=rating,
                specific_feedback=str(result.specific_feedback),
                pattern_detected=str(result.pattern_detected),
                tomorrow_suggestion=str(result.tomorrow_suggestion),
            )

        except Exception as e:
            logger.error(f"Error analizando nutrición: {e}")
            return self._create_fallback_result(meals_description)

    def _parse_meals_breakdown(self, breakdown_str: str | list) -> list[MealBreakdown]:
        """Parsea el desglose de comidas."""
        meals = []

        if isinstance(breakdown_str, list):
            for item in breakdown_str:
                if isinstance(item, dict):
                    meals.append(MealBreakdown(
                        name=item.get("name", "Comida"),
                        description=item.get("description", ""),
                        calories=item.get("calories", 0),
                        category=item.get("category", "moderado"),
                    ))
        else:
            # Intentar parsear string
            # Formato esperado: "Desayuno: huevos, 300 cal, saludable; Almuerzo: ..."
            parts = str(breakdown_str).split(";")
            for part in parts:
                part = part.strip()
                if ":" in part:
                    name, rest = part.split(":", 1)
                    meals.append(MealBreakdown(
                        name=name.strip(),
                        description=rest.strip(),
                        calories=self._extract_calories(rest),
                        category=self._detect_category(rest),
                    ))

        # Si no se pudo parsear, crear comidas básicas
        if not meals:
            meals = [
                MealBreakdown("Comida registrada", str(breakdown_str), 0, "moderado")
            ]

        return meals

    def _extract_calories(self, text: str) -> int:
        """Extrae calorías de un texto."""
        import re

        match = re.search(r"(\d+)\s*(?:cal|kcal|calorias)", text.lower())
        if match:
            return int(match.group(1))
        return 0

    def _detect_category(self, text: str) -> str:
        """Detecta categoría de una comida."""
        text_lower = text.lower()

        if any(word in text_lower for word in ["saludable", "healthy", "verde"]):
            return "saludable"
        elif any(word in text_lower for word in ["pesado", "heavy", "frito", "grasa"]):
            return "pesado"
        else:
            return "moderado"

    def _create_fallback_result(self, meals_description: str) -> NutritionResult:
        """Crea resultado de fallback."""
        return NutritionResult(
            meals_breakdown=[
                MealBreakdown(
                    name="Registro del día",
                    description=meals_description[:200],
                    calories=0,
                    category="moderado",
                )
            ],
            total_calories=0,
            protein_status=ProteinStatus.LOW,
            vegetables_count=0,
            overall_rating=NutritionRating.MODERATE,
            specific_feedback="No se pudo analizar en detalle. Revisa las comidas manualmente.",
            pattern_detected="Sin datos suficientes para detectar patrones.",
            tomorrow_suggestion="Intenta incluir más vegetales y proteína.",
        )

    def get_rating_emoji(self, rating: NutritionRating) -> str:
        """Obtiene emoji para rating."""
        emoji_map = {
            NutritionRating.EXCELLENT: "🌟",
            NutritionRating.GOOD: "✅",
            NutritionRating.MODERATE: "😐",
            NutritionRating.POOR: "⚠️",
        }
        return emoji_map.get(rating, "😐")

    def get_category_emoji(self, category: str) -> str:
        """Obtiene emoji para categoría de comida."""
        emoji_map = {
            "saludable": "🟢",
            "moderado": "🟡",
            "pesado": "🔴",
        }
        return emoji_map.get(category.lower(), "🟡")

    def format_telegram_message(self, result: NutritionResult) -> str:
        """Formatea resultado como mensaje de Telegram."""
        rating_emoji = self.get_rating_emoji(result.overall_rating)

        message = f"🍽️ <b>Análisis de Nutrición</b> {rating_emoji}\n\n"

        # Desglose de comidas
        message += "<b>📋 Comidas del día:</b>\n"
        for meal in result.meals_breakdown:
            cat_emoji = self.get_category_emoji(meal.category)
            cal_str = f" ({meal.calories} cal)" if meal.calories > 0 else ""
            message += f"{cat_emoji} <b>{meal.name}:</b> {meal.description}{cal_str}\n"

        message += "\n"

        # Resumen
        message += "<b>📊 Resumen:</b>\n"
        if result.total_calories > 0:
            cal_diff = result.total_calories - self.target_calories
            cal_status = "📈" if cal_diff > 0 else "📉" if cal_diff < 0 else "✅"
            message += f"{cal_status} Calorías: ~{result.total_calories} cal "
            message += f"(meta: {self.target_calories})\n"

        protein_emoji = "✅" if result.protein_status == ProteinStatus.SUFFICIENT else "⚠️"
        message += f"{protein_emoji} Proteína: {result.protein_status.value}\n"

        veggie_emoji = "✅" if result.vegetables_count >= 2 else "⚠️"
        message += f"{veggie_emoji} Vegetales: {result.vegetables_count} comidas\n"

        # Evaluación
        message += f"\n<b>📈 Evaluación:</b> {result.overall_rating.value.title()}\n"

        # Feedback
        message += f"\n<b>💡 Feedback:</b>\n{result.specific_feedback}\n"

        # Patrón detectado
        if result.pattern_detected and result.pattern_detected != "Sin datos":
            message += f"\n<b>🔍 Patrón:</b> {result.pattern_detected}\n"

        # Sugerencia para mañana
        message += f"\n<b>🎯 Mañana:</b> {result.tomorrow_suggestion}"

        return message

    async def quick_log(
        self,
        meal_type: str,
        description: str,
    ) -> MealBreakdown:
        """
        Hace un registro rápido de una comida individual.

        Args:
            meal_type: Tipo de comida (desayuno, almuerzo, cena, snack)
            description: Descripción de la comida

        Returns:
            MealBreakdown con la comida analizada
        """
        # Análisis simple basado en palabras clave
        description_lower = description.lower()

        # Detectar categoría
        healthy_words = ["ensalada", "pollo", "pescado", "vegetales", "fruta", "yogurt"]
        heavy_words = ["frito", "pizza", "hamburguesa", "tacos", "churros", "refresco"]

        if any(word in description_lower for word in healthy_words):
            category = "saludable"
        elif any(word in description_lower for word in heavy_words):
            category = "pesado"
        else:
            category = "moderado"

        # Estimar calorías (muy aproximado)
        cal_estimates = {
            "saludable": 400,
            "moderado": 600,
            "pesado": 900,
        }
        calories = cal_estimates.get(category, 500)

        return MealBreakdown(
            name=meal_type.title(),
            description=description,
            calories=calories,
            category=category,
        )
