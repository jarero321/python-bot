"""Persistent Reminders Job - Verifica y envía recordatorios pendientes."""

import logging
from datetime import datetime

from app.config import get_settings
from app.db.database import get_session
from app.db.repositories.reminders import RemindersRepository
from app.db.models import ReminderPriority
from app.services.telegram import get_telegram_service
from app.bot.keyboards import reminder_actions_keyboard

logger = logging.getLogger(__name__)
settings = get_settings()


async def check_persistent_reminders_job() -> None:
    """
    Verifica recordatorios pendientes y envía los que correspondan.

    Se ejecuta cada 30 minutos.
    """
    logger.info("Verificando recordatorios pendientes...")

    telegram = get_telegram_service()

    try:
        async with get_session() as session:
            repo = RemindersRepository(session)

            # Obtener recordatorios que deben enviarse
            due_reminders = await repo.get_due_reminders()

            if not due_reminders:
                logger.debug("No hay recordatorios pendientes")
                return

            logger.info(f"Encontrados {len(due_reminders)} recordatorios pendientes")

            for reminder in due_reminders:
                # Verificar horarios de no molestar
                if _is_quiet_hours():
                    logger.debug(f"Horario de silencio, posponiendo: {reminder.title}")
                    continue

                # Enviar recordatorio
                message = _format_reminder_message(reminder)
                await telegram.send_message_with_keyboard(
                    text=message,
                    reply_markup=reminder_actions_keyboard(reminder.id),
                )

                # Marcar como enviado
                await repo.mark_as_reminded(reminder.id)

                logger.info(f"Recordatorio enviado: {reminder.title}")

    except Exception as e:
        logger.error(f"Error en Persistent Reminders: {e}")


def _is_quiet_hours() -> bool:
    """Verifica si es horario de silencio (no molestar)."""
    hour = datetime.now().hour

    # No molestar entre 22:00 y 7:00
    if hour >= 22 or hour < 7:
        return True

    # No molestar durante comidas (12:30-14:00)
    if hour == 13 or (hour == 12 and datetime.now().minute >= 30):
        return True

    return False


def _format_reminder_message(reminder) -> str:
    """Formatea el mensaje de un recordatorio."""
    priority_emoji = {
        ReminderPriority.LOW: "🔵",
        ReminderPriority.NORMAL: "🟡",
        ReminderPriority.HIGH: "🟠",
        ReminderPriority.URGENT: "🔴",
    }

    emoji = priority_emoji.get(reminder.priority, "⏰")

    message = f"{emoji} <b>Recordatorio</b>\n\n"
    message += f"<b>{reminder.title}</b>\n"

    if reminder.description:
        message += f"\n{reminder.description}\n"

    # Mostrar escalación si es repetido
    if reminder.escalation_count > 0:
        message += f"\n⚠️ <i>Recordatorio #{reminder.escalation_count + 1}</i>"

    return message
