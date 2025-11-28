"""Hourly Check-in Job - Pregunta el estado cada hora."""

import logging
from datetime import datetime

from app.config import get_settings
from app.services.telegram import get_telegram_service
from app.bot.keyboards import checkin_status_keyboard

logger = logging.getLogger(__name__)
settings = get_settings()


async def hourly_checkin_job() -> None:
    """
    Envía un check-in cada hora durante horas laborales.

    Pregunta:
    - Si está trabajando en algo
    - Si está bloqueado
    - Si necesita cambiar de tarea
    """
    logger.info("Ejecutando Hourly Check-in...")

    telegram = get_telegram_service()
    hour = datetime.now().hour

    try:
        # Personalizar mensaje según la hora
        message = _get_checkin_message(hour)

        await telegram.send_message_with_keyboard(
            text=message,
            reply_markup=checkin_status_keyboard(),
        )

        logger.info(f"Hourly Check-in enviado ({hour}:30)")

    except Exception as e:
        logger.error(f"Error en Hourly Check-in: {e}")


def _get_checkin_message(hour: int) -> str:
    """Genera el mensaje de check-in según la hora."""
    if hour == 9:
        return (
            "🌅 <b>Check-in matutino</b>\n\n"
            "¿Ya empezaste con la primera tarea del día?\n"
            "¿Cómo va tu nivel de energía?"
        )
    elif hour == 12:
        return (
            "🌞 <b>Check-in del mediodía</b>\n\n"
            "¿Cómo va la mañana? ¿Lograste avanzar?\n"
            "Recuerda tomar un break para comer."
        )
    elif hour == 15:
        return (
            "☀️ <b>Check-in de la tarde</b>\n\n"
            "Ya pasó la mitad del día. ¿Cómo vas?\n"
            "¿Necesitas ajustar las prioridades?"
        )
    elif hour == 17:
        return (
            "🌇 <b>Check-in de cierre</b>\n\n"
            "El día está por terminar.\n"
            "¿Qué lograste hoy? ¿Quedó algo pendiente?"
        )
    else:
        return (
            f"⏰ <b>Check-in ({hour}:30)</b>\n\n"
            "¿Cómo va todo? ¿Sigues en la misma tarea?"
        )
