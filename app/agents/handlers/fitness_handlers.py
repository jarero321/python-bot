"""
Fitness Handlers - Gym y nutrición.

Handlers para registrar workouts, consultar historial y loguear comidas.
"""

import json
import logging
from typing import Any

import dspy
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.agents.intent_router import UserIntent
from app.agents.base import EstimateMealCalories
from app.core.routing import (
    BaseIntentHandler,
    HandlerResponse,
    intent_handler,
)
from app.core.llm import get_llm_provider, ModelType
from app.core.parsing import DSPyParser
from app.services.notion import get_notion_service, NutritionCategoria

logger = logging.getLogger(__name__)


def workout_type_keyboard() -> InlineKeyboardMarkup:
    """Teclado para seleccionar tipo de workout."""
    keyboard = [
        [
            InlineKeyboardButton("💪 Push", callback_data="workout_type:push"),
            InlineKeyboardButton("🏋️ Pull", callback_data="workout_type:pull"),
        ],
        [
            InlineKeyboardButton("🦵 Legs", callback_data="workout_type:legs"),
            InlineKeyboardButton("🏃 Cardio", callback_data="workout_type:cardio"),
        ],
        [
            InlineKeyboardButton("❌ Cancelar", callback_data="workout_cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def nutrition_category_keyboard() -> InlineKeyboardMarkup:
    """Teclado para seleccionar categoría de comida."""
    keyboard = [
        [
            InlineKeyboardButton("🟢 Saludable", callback_data="nutrition_cat:saludable"),
            InlineKeyboardButton("🟡 Moderado", callback_data="nutrition_cat:moderado"),
        ],
        [
            InlineKeyboardButton("🔴 Pesado", callback_data="nutrition_cat:pesado"),
            InlineKeyboardButton("❌ Cancelar", callback_data="nutrition_cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


@intent_handler(UserIntent.GYM_LOG)
class GymLogHandler(BaseIntentHandler):
    """Handler para registrar workouts."""

    name = "GymLogHandler"
    intents = [UserIntent.GYM_LOG]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        text = self.get_raw_message(intent_result)

        # Guardar en context para cuando seleccione tipo
        context.user_data["pending_workout"] = text

        message = (
            f"💪 <b>Registrar workout</b>\n\n"
            f"<i>{text}</i>\n\n"
            "¿Qué tipo de entrenamiento hiciste?"
        )

        return HandlerResponse(
            message=message,
            keyboard=workout_type_keyboard(),
        )


@intent_handler(UserIntent.GYM_QUERY)
class GymQueryHandler(BaseIntentHandler):
    """Handler para consultar historial de workouts."""

    name = "GymQueryHandler"
    intents = [UserIntent.GYM_QUERY]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        notion = get_notion_service()
        history = await notion.get_workout_history(weeks=2)

        if not history:
            return HandlerResponse(
                message="🏋️ No hay workouts registrados aún."
            )

        msg = "🏋️ <b>Últimos workouts</b>\n\n"

        for w in history[:7]:
            props = w.get("properties", {})
            fecha = (
                props.get("Fecha", {})
                .get("title", [{}])[0]
                .get("text", {})
                .get("content", "?")
            )
            tipo = props.get("Tipo", {}).get("select", {}).get("name", "?")

            # Obtener ejercicios
            ejercicios_raw = props.get("Ejercicios", {}).get("rich_text", [])
            ejercicios_text = (
                ejercicios_raw[0].get("text", {}).get("content", "")
                if ejercicios_raw
                else ""
            )

            # Obtener PRs
            prs_raw = props.get("PRs", {}).get("rich_text", [])
            prs_text = (
                prs_raw[0].get("text", {}).get("content", "")
                if prs_raw
                else ""
            )

            msg += f"<b>{fecha}</b> - {tipo}\n"

            # Parsear ejercicios si es JSON
            if ejercicios_text:
                ejercicios_data = DSPyParser.parse_json(ejercicios_text, {})
                if isinstance(ejercicios_data, dict):
                    exercises = ejercicios_data.get("exercises", [])
                    for ex in exercises[:3]:
                        ex_name = ex.get("name", ex.get("exercise", "?"))
                        ex_weight = ex.get("weight", ex.get("peso", ""))
                        ex_reps = ex.get("reps", "")
                        ex_sets = ex.get("sets", ex.get("series", ""))

                        detail = f"  • {ex_name}"
                        if ex_weight:
                            detail += f" - {ex_weight}kg"
                        if ex_sets and ex_reps:
                            detail += f" ({ex_sets}x{ex_reps})"
                        msg += f"{detail}\n"
                else:
                    msg += f"  {ejercicios_text[:50]}\n"

            if prs_text:
                msg += f"  🏆 PRs: {prs_text}\n"

            msg += "\n"

        return HandlerResponse(message=msg)


@intent_handler(UserIntent.NUTRITION_LOG)
class NutritionLogHandler(BaseIntentHandler):
    """Handler para registrar comidas con análisis AI."""

    name = "NutritionLogHandler"
    intents = [UserIntent.NUTRITION_LOG]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        entities = self.get_entities(intent_result)
        text = self.get_raw_message(intent_result)

        meal = entities.get("meal", "comida")
        food = entities.get("food", text)

        # Enviar mensaje de procesamiento
        await update.message.reply_html(
            f"🍽️ <b>Analizando {meal}...</b>\n\n"
            f"<i>{food}</i>\n\n"
            "⏳ Estimando calorías con AI..."
        )

        try:
            # Usar modelo PRO para análisis nutricional
            provider = get_llm_provider()
            provider.ensure_configured()

            with provider.for_task("nutrition_analysis"):
                estimator = dspy.ChainOfThought(EstimateMealCalories)
                result = estimator(
                    meal_description=food,
                    meal_type=meal,
                )

            # Parsear resultados
            calories = DSPyParser.parse_int(result.calories, 500, min_val=0)
            protein = DSPyParser.parse_int(result.protein_grams, 0, min_val=0)
            category_str = DSPyParser.parse_string(result.category, "moderado").lower()
            feedback = DSPyParser.parse_string(result.feedback, "")

            # Mapear categoría
            category_map = {
                "saludable": NutritionCategoria.SALUDABLE,
                "moderado": NutritionCategoria.MODERADO,
                "pesado": NutritionCategoria.PESADO,
            }
            category = category_map.get(category_str, NutritionCategoria.MODERADO)
            category_emoji = {
                NutritionCategoria.SALUDABLE: "🟢",
                NutritionCategoria.MODERADO: "🟡",
                NutritionCategoria.PESADO: "🔴",
            }.get(category, "🟡")

            # Guardar en Notion
            from datetime import date
            notion = get_notion_service()
            fecha_hoy = date.today().isoformat()

            # Mapear tipo de comida a parámetros correctos
            meal_lower = meal.lower()
            nutrition_params = {"fecha": fecha_hoy}

            if "desayuno" in meal_lower or "breakfast" in meal_lower:
                nutrition_params["desayuno"] = food
                nutrition_params["desayuno_cal"] = calories
                nutrition_params["desayuno_cat"] = category
            elif "almuerzo" in meal_lower or "comida" in meal_lower or "lunch" in meal_lower:
                nutrition_params["comida"] = food
                nutrition_params["comida_cal"] = calories
                nutrition_params["comida_cat"] = category
            elif "cena" in meal_lower or "dinner" in meal_lower:
                nutrition_params["cena"] = food
                nutrition_params["cena_cal"] = calories
                nutrition_params["cena_cat"] = category
            else:
                # Snacks o cualquier otro
                nutrition_params["snacks"] = food
                nutrition_params["snacks_cal"] = calories

            # Indicar si tuvo suficiente proteína
            nutrition_params["proteina_ok"] = protein >= 20

            await notion.log_nutrition(**nutrition_params)

            message = (
                f"✅ <b>{meal.capitalize()} registrada</b>\n\n"
                f"{category_emoji} Categoría: {category.value}\n"
                f"🔥 Calorías: ~{calories}\n"
                f"💪 Proteína: ~{protein}g\n\n"
            )

            if feedback:
                message += f"💡 <i>{feedback}</i>"

            return HandlerResponse(message=message, already_sent=True)

        except Exception as e:
            logger.error(f"Error analizando nutrición: {e}")

            # Fallback: guardar sin análisis
            context.user_data["pending_nutrition"] = {
                "meal": meal,
                "food": food,
            }

            return HandlerResponse(
                message=(
                    f"⚠️ No pude analizar automáticamente.\n\n"
                    f"<i>{food}</i>\n\n"
                    f"Selecciona la categoría manualmente:"
                ),
                keyboard=nutrition_category_keyboard(),
                already_sent=True,
            )


@intent_handler(UserIntent.NUTRITION_QUERY)
class NutritionQueryHandler(BaseIntentHandler):
    """Handler para consultar historial de nutrición."""

    name = "NutritionQueryHandler"
    intents = [UserIntent.NUTRITION_QUERY]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        notion = get_notion_service()
        history = await notion.get_nutrition_history(days=3)

        if not history:
            return HandlerResponse(
                message="🍽️ No hay comidas registradas recientemente."
            )

        msg = "🍽️ <b>Historial de comidas</b>\n\n"
        total_calories = 0
        total_protein = 0

        for entry in history[:10]:
            props = entry.get("properties", {})

            tipo = props.get("Tipo", {}).get("select", {}).get("name", "?")
            desc_raw = props.get("Descripción", {}).get("rich_text", [])
            desc = (
                desc_raw[0].get("text", {}).get("content", "?")[:30]
                if desc_raw
                else "?"
            )
            cals = props.get("Calorías", {}).get("number", 0) or 0
            prot = props.get("Proteínas", {}).get("number", 0) or 0
            cat = props.get("Categoría", {}).get("select", {}).get("name", "")

            cat_emoji = {"Saludable": "🟢", "Moderado": "🟡", "Pesado": "🔴"}.get(
                cat, "⚪"
            )

            msg += f"{cat_emoji} <b>{tipo}</b>: {desc}\n"
            msg += f"   🔥 {cals} cal | 💪 {prot}g proteína\n\n"

            total_calories += cals
            total_protein += prot

        msg += f"<b>Total hoy:</b> {total_calories} cal, {total_protein}g proteína"

        return HandlerResponse(message=msg)
