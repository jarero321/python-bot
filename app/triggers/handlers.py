"""
Trigger Handlers - Funciones que disparan el Brain.

Cada handler es simple: obtiene el Brain y llama a run_trigger().
La lógica de qué hacer está en el Brain, no aquí.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select, and_
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from app.brain import get_brain
from app.brain.core import BrainResponse
from app.config import get_settings
from app.db.database import get_session

logger = logging.getLogger(__name__)
settings = get_settings()


async def _send_telegram_message(response: BrainResponse) -> bool:
    """
    Envía un mensaje de BrainResponse a Telegram.

    Returns True si se envió, False si no había mensaje.
    """
    if not response.message:
        return False

    try:
        bot = Bot(token=settings.telegram_bot_token)

        # Construir keyboard si hay
        reply_markup = None
        if response.keyboard:
            buttons = [
                [
                    InlineKeyboardButton(
                        text=btn.get("text", ""),
                        callback_data=btn.get("callback_data", "")
                    )
                    for btn in row
                ]
                for row in response.keyboard
            ]
            reply_markup = InlineKeyboardMarkup(buttons)

        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=response.message,
            parse_mode="HTML",
            reply_markup=reply_markup
        )

        return True

    except Exception as e:
        logger.exception(f"Error enviando mensaje a Telegram: {e}")
        return False


async def _get_default_user_id() -> str | None:
    """
    Obtiene el UUID del usuario por defecto (para triggers automáticos).

    Busca el perfil de usuario usando el telegram_chat_id de la config
    y retorna su UUID interno.
    """
    from app.db.models import UserProfileModel

    telegram_id = settings.telegram_chat_id
    if not telegram_id:
        return None

    async with get_session() as session:
        result = await session.execute(
            select(UserProfileModel).where(UserProfileModel.telegram_id == telegram_id)
        )
        profile = result.scalar_one_or_none()

        if profile:
            return str(profile.id)

        logger.warning(f"No se encontró perfil para telegram_id {telegram_id}")
        return None


async def trigger_morning_briefing() -> None:
    """Trigger del morning briefing - 6:30 AM."""
    user_id = await _get_default_user_id()
    if not user_id:
        logger.warning("No hay user_id configurado para morning_briefing")
        return

    try:
        brain = await get_brain(user_id)
        response = await brain.run_trigger("morning_briefing")

        if await _send_telegram_message(response):
            logger.info(f"Morning briefing enviado: {response.action_taken}")
        else:
            logger.info("Morning briefing: sin mensaje que enviar")

    except Exception as e:
        logger.exception(f"Error en morning_briefing: {e}")


async def trigger_gym_check(escalation_level: int = 1) -> None:
    """Trigger del gym check - 7:15, 7:30, 7:45 AM."""
    user_id = await _get_default_user_id()
    if not user_id:
        return

    try:
        brain = await get_brain(user_id)
        response = await brain.run_trigger(
            "gym_check",
            context={"escalation_level": escalation_level}
        )

        if await _send_telegram_message(response):
            logger.info(f"Gym check (level {escalation_level}) enviado")
        else:
            logger.debug(f"Gym check (level {escalation_level}): sin mensaje")

    except Exception as e:
        logger.exception(f"Error en gym_check: {e}")


async def trigger_hourly_pulse() -> None:
    """Trigger del hourly pulse - cada hora 9-18 L-V."""
    user_id = await _get_default_user_id()
    if not user_id:
        return

    try:
        brain = await get_brain(user_id)
        response = await brain.run_trigger("hourly_pulse")

        # hourly_pulse generalmente NO envía mensaje a menos que haya algo relevante
        if await _send_telegram_message(response):
            logger.info(f"Hourly pulse: mensaje enviado - {response.action_taken}")
        else:
            logger.debug("Hourly pulse: nada relevante")

    except Exception as e:
        logger.exception(f"Error en hourly_pulse: {e}")


async def trigger_evening_reflection() -> None:
    """Trigger de reflexión de la noche - 9 PM."""
    user_id = await _get_default_user_id()
    if not user_id:
        return

    try:
        brain = await get_brain(user_id)
        response = await brain.run_trigger("evening_reflection")

        if await _send_telegram_message(response):
            logger.info("Evening reflection enviada")

    except Exception as e:
        logger.exception(f"Error en evening_reflection: {e}")


async def trigger_weekly_review() -> None:
    """Trigger de revisión semanal - Domingo 10 AM."""
    user_id = await _get_default_user_id()
    if not user_id:
        return

    try:
        brain = await get_brain(user_id)
        response = await brain.run_trigger("weekly_review")

        if await _send_telegram_message(response):
            logger.info("Weekly review enviada")

    except Exception as e:
        logger.exception(f"Error en weekly_review: {e}")


async def trigger_reminder_check() -> None:
    """
    Check de reminders pendientes - cada 2 minutos.

    Busca reminders que deban enviarse y los pasa al Brain.
    """
    from app.db.models import ReminderModel

    try:
        async with get_session() as session:
            now = datetime.now()

            # Buscar reminders pendientes que ya deban enviarse
            result = await session.execute(
                select(ReminderModel)
                .where(ReminderModel.status == "pending")
                .where(ReminderModel.scheduled_at <= now)
            )
            reminders = result.scalars().all()

            if not reminders:
                return

            logger.info(f"Procesando {len(reminders)} reminders")

            for reminder in reminders:
                user_id = str(reminder.user_id)

                brain = await get_brain(user_id)
                response = await brain.run_trigger(
                    "reminder_due",
                    context={
                        "reminder_id": str(reminder.id),
                        "message": reminder.message,
                        "task_id": str(reminder.task_id) if reminder.task_id else None,
                    }
                )

                # Enviar mensaje a Telegram
                if await _send_telegram_message(response):
                    logger.info(f"Reminder {reminder.id} enviado")

                # Marcar como enviado
                reminder.status = "sent"
                reminder.sent_at = now

            await session.commit()

    except Exception as e:
        logger.exception(f"Error en reminder_check: {e}")


async def trigger_deadline_check() -> None:
    """
    Check de deadlines próximos - 9 AM y 3 PM.

    Busca tareas que venzan en las próximas 24h.
    """
    from app.db.models import TaskModel
    from datetime import date

    try:
        async with get_session() as session:
            tomorrow = date.today() + timedelta(days=1)

            # Tareas que vencen hoy o mañana
            result = await session.execute(
                select(TaskModel)
                .where(TaskModel.due_date <= tomorrow)
                .where(TaskModel.due_date >= date.today())
                .where(TaskModel.status.notin_(["done", "cancelled"]))
            )
            tasks = result.scalars().all()

            if not tasks:
                logger.debug("deadline_check: sin tareas próximas a vencer")
                return

            # Agrupar por usuario
            tasks_by_user: dict[str, list] = {}
            for task in tasks:
                user_key = str(task.user_id)
                if user_key not in tasks_by_user:
                    tasks_by_user[user_key] = []
                tasks_by_user[user_key].append({
                    "id": str(task.id),
                    "title": task.title,
                    "due_date": task.due_date.isoformat(),
                    "priority": task.priority,
                })

            for user_id, user_tasks in tasks_by_user.items():
                brain = await get_brain(user_id)
                response = await brain.run_trigger(
                    "deadline_approaching",
                    context={"tasks": user_tasks}
                )
                await _send_telegram_message(response)

            logger.info(f"deadline_check: procesadas {len(tasks)} tareas")

    except Exception as e:
        logger.exception(f"Error en deadline_check: {e}")


async def trigger_stuck_tasks_check() -> None:
    """
    Check de tareas estancadas - 5 PM diario.

    Busca tareas en "doing" por más de 3 días.
    """
    from app.db.models import TaskModel

    try:
        async with get_session() as session:
            three_days_ago = datetime.now() - timedelta(days=3)

            # Tareas en "doing" que no se han actualizado en 3+ días
            result = await session.execute(
                select(TaskModel)
                .where(TaskModel.status == "doing")
                .where(TaskModel.updated_at < three_days_ago)
            )
            tasks = result.scalars().all()

            if not tasks:
                logger.debug("stuck_tasks_check: sin tareas estancadas")
                return

            # Agrupar por usuario
            tasks_by_user: dict[str, list] = {}
            for task in tasks:
                user_key = str(task.user_id)
                if user_key not in tasks_by_user:
                    tasks_by_user[user_key] = []
                days_stuck = (datetime.now() - task.updated_at).days
                tasks_by_user[user_key].append({
                    "id": str(task.id),
                    "title": task.title,
                    "days_stuck": days_stuck,
                })

            for user_id, user_tasks in tasks_by_user.items():
                brain = await get_brain(user_id)
                response = await brain.run_trigger(
                    "task_stuck",
                    context={"tasks": user_tasks}
                )
                await _send_telegram_message(response)

            logger.info(f"stuck_tasks_check: procesadas {len(tasks)} tareas")

    except Exception as e:
        logger.exception(f"Error en stuck_tasks_check: {e}")


async def trigger_payday_alert(is_pre: bool = True) -> None:
    """
    Alerta de quincena - pre (días 13, 14, 28, 29) y post (15, 30).
    """
    user_id = await _get_default_user_id()
    if not user_id:
        return

    try:
        brain = await get_brain(user_id)
        response = await brain.run_trigger(
            "payday_alert",
            context={
                "is_pre": is_pre,
                "day": datetime.now().day,
            }
        )

        if await _send_telegram_message(response):
            alert_type = "pre" if is_pre else "post"
            logger.info(f"Payday {alert_type}-alert enviado")

    except Exception as e:
        logger.exception(f"Error en payday_alert: {e}")


async def trigger_meal_reminder(meal_type: str = "lunch") -> None:
    """
    Recordatorio de comida - desayuno, almuerzo, cena.

    Pregunta qué comió y ofrece registrarlo.
    """
    user_id = await _get_default_user_id()
    if not user_id:
        return

    try:
        brain = await get_brain(user_id)
        response = await brain.run_trigger(
            "meal_reminder",
            context={
                "meal_type": meal_type,
                "hour": datetime.now().hour,
            }
        )

        if await _send_telegram_message(response):
            logger.info(f"Meal reminder ({meal_type}) enviado")

    except Exception as e:
        logger.exception(f"Error en meal_reminder: {e}")


async def trigger_proactive_checkin(period: str = "morning") -> None:
    """
    Check-in proactivo - pregunta cómo va el día y las tareas.

    Diferente del hourly_pulse que es silencioso.
    """
    user_id = await _get_default_user_id()
    if not user_id:
        return

    try:
        brain = await get_brain(user_id)
        response = await brain.run_trigger(
            "proactive_checkin",
            context={
                "period": period,
                "hour": datetime.now().hour,
            }
        )

        if await _send_telegram_message(response):
            logger.info(f"Proactive checkin ({period}) enviado")

    except Exception as e:
        logger.exception(f"Error en proactive_checkin: {e}")


async def trigger_study_reminder() -> None:
    """
    Recordatorio de estudio - 5:30 PM diario.

    Sugiere qué estudiar basándose en balance y progreso.
    """
    user_id = await _get_default_user_id()
    if not user_id:
        return

    try:
        brain = await get_brain(user_id)
        response = await brain.run_trigger("study_reminder")

        if await _send_telegram_message(response):
            logger.info("Study reminder enviado")

    except Exception as e:
        logger.exception(f"Error en study_reminder: {e}")


# ==================== Trigger para reminders dinámicos ====================

async def trigger_single_reminder(reminder_id: str) -> None:
    """
    Trigger para un reminder específico (programado dinámicamente).
    """
    from app.db.models import ReminderModel

    try:
        async with get_session() as session:
            result = await session.execute(
                select(ReminderModel)
                .where(ReminderModel.id == reminder_id)
            )
            reminder = result.scalar_one_or_none()

            if not reminder:
                logger.warning(f"Reminder {reminder_id} no encontrado")
                return

            if reminder.status != "pending":
                logger.debug(f"Reminder {reminder_id} ya no está pendiente")
                return

            brain = await get_brain(str(reminder.user_id))
            response = await brain.run_trigger(
                "reminder_due",
                context={
                    "reminder_id": str(reminder.id),
                    "message": reminder.message,
                    "task_id": str(reminder.task_id) if reminder.task_id else None,
                }
            )

            # Enviar mensaje a Telegram
            if await _send_telegram_message(response):
                logger.info(f"Reminder {reminder_id} enviado")

            # Marcar como enviado
            reminder.status = "sent"
            reminder.sent_at = datetime.now()
            await session.commit()

    except Exception as e:
        logger.exception(f"Error en single_reminder {reminder_id}: {e}")
