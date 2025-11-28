"""Nutrition Reminder Job - Pregunta sobre la alimentación del día."""

import logging
from datetime import datetime

from app.config import get_settings
from app.services.telegram import get_telegram_service
from app.bot.keyboards import nutrition_rating_keyboard

logger = logging.getLogger(__name__)
settings = get_settings()


async def nutrition_reminder_job() -> None:
    """
    Envía recordatorio para registrar la nutrición del día.

    Se ejecuta a las 9:00 PM.
    """
    logger.info("Ejecutando Nutrition Reminder...")

    telegram = get_telegram_service()

    try:
        message = _get_nutrition_message()

        await telegram.send_message_with_keyboard(
            text=message,
            reply_markup=nutrition_rating_keyboard(),
        )

        logger.info("Nutrition Reminder enviado")

    except Exception as e:
        logger.error(f"Error en Nutrition Reminder: {e}")


def _get_nutrition_message() -> str:
    """Genera el mensaje de nutrición."""
    weekday = datetime.now().weekday()

    # Mensaje base
    message = (
        "🍽️ <b>Registro de Nutrición</b>\n\n"
        "¿Cómo fue tu alimentación hoy?\n\n"
        "Cuéntame qué comiste en:\n"
        "• Desayuno\n"
        "• Almuerzo\n"
        "• Cena\n"
        "• Snacks\n\n"
    )

    # Agregar tip según el día
    tips = {
        0: "💡 Tip: El lunes es buen día para empezar con buenos hábitos.",
        1: "💡 Tip: Recuerda hidratarte bien durante el día.",
        2: "💡 Tip: La proteína ayuda a mantener la masa muscular.",
        3: "💡 Tip: Los vegetales son tus amigos.",
        4: "💡 Tip: Si vas a comer fuera el finde, planifica.",
        5: "💡 Tip: Fin de semana no significa excesos.",
        6: "💡 Tip: Prepara tus comidas para la semana.",
    }

    message += tips.get(weekday, "")
    message += "\n\nPrimero, ¿cómo calificarías tu día de nutrición?"

    return message
