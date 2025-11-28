"""Gym Reminder Jobs - Recordatorios para ir al gym."""

import logging

from app.config import get_settings
from app.services.telegram import get_telegram_service
from app.bot.keyboards import gym_confirmation_keyboard

logger = logging.getLogger(__name__)
settings = get_settings()

# Estado en memoria (en producción usar DB)
_gym_confirmed_today = False


async def gym_reminder_job(escalation_level: str = "gentle") -> None:
    """
    Envía recordatorio para ir al gym.

    Args:
        escalation_level: Nivel de insistencia (gentle, normal, insistent)
    """
    global _gym_confirmed_today

    # Si ya confirmó hoy, no molestar
    if _gym_confirmed_today:
        logger.debug("Gym ya confirmado hoy, saltando recordatorio")
        return

    logger.info(f"Ejecutando Gym Reminder ({escalation_level})...")

    telegram = get_telegram_service()

    try:
        message = _get_gym_message(escalation_level)

        await telegram.send_message_with_keyboard(
            text=message,
            reply_markup=gym_confirmation_keyboard(),
        )

        logger.info(f"Gym Reminder enviado ({escalation_level})")

    except Exception as e:
        logger.error(f"Error en Gym Reminder: {e}")


def _get_gym_message(level: str) -> str:
    """Genera el mensaje según el nivel de escalación."""
    messages = {
        "gentle": (
            "💪 <b>Buenos días!</b>\n\n"
            "¿Listo para el gym?\n"
            "Recuerda: la consistencia es más importante que la intensidad."
        ),
        "normal": (
            "🏋️ <b>Recordatorio de Gym</b>\n\n"
            "Ya son las 7:30. El gym te espera.\n"
            "¿Vas a ir hoy?"
        ),
        "insistent": (
            "⚡ <b>¡Último aviso!</b>\n\n"
            "Son las 7:45. Si no sales ahora, se te hará tarde.\n"
            "Piensa en tus objetivos. ¿Qué decides?"
        ),
    }
    return messages.get(level, messages["normal"])


async def confirm_gym() -> None:
    """Marca el gym como confirmado para hoy."""
    global _gym_confirmed_today
    _gym_confirmed_today = True
    logger.info("Gym confirmado para hoy")


async def reset_gym_confirmation() -> None:
    """Resetea la confirmación de gym (llamar a medianoche)."""
    global _gym_confirmed_today
    _gym_confirmed_today = False
    logger.info("Confirmación de gym reseteada")
