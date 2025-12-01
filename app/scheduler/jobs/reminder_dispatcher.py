"""Job para despachar recordatorios pendientes."""

import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.reminder_service import get_reminder_service
from app.services.telegram import get_telegram_service
from app.db.models import ReminderPriority

logger = logging.getLogger(__name__)


async def dispatch_pending_reminders():
    """
    Job que revisa y envía recordatorios pendientes.

    Se ejecuta cada 2 minutos para enviar recordatorios a tiempo.
    """
    reminder_service = get_reminder_service()
    telegram_service = get_telegram_service()

    try:
        logger.debug("Ejecutando dispatch_pending_reminders...")

        # Obtener recordatorios que deben enviarse
        due_reminders = await reminder_service.get_due_reminders()

        if not due_reminders:
            logger.debug("No hay recordatorios pendientes para enviar")
            return

        logger.info(f"Despachando {len(due_reminders)} recordatorios")

        for reminder in due_reminders:
            try:
                # Construir mensaje según prioridad
                priority_emoji = {
                    ReminderPriority.URGENT: "🔴",
                    ReminderPriority.HIGH: "🟠",
                    ReminderPriority.NORMAL: "🔵",
                    ReminderPriority.LOW: "⚪",
                }
                emoji = priority_emoji.get(reminder.priority, "🔵")

                message = f"{emoji} <b>{reminder.title}</b>"
                if reminder.description:
                    message += f"\n\n{reminder.description}"

                # Botones de acción
                buttons = []

                # Fila 1: Completar y Snooze
                row1 = [
                    InlineKeyboardButton(
                        "✅ Hecho",
                        callback_data=f"reminder_done:{reminder.id}"
                    ),
                    InlineKeyboardButton(
                        "⏰ +30min",
                        callback_data=f"reminder_snooze:{reminder.id}:30"
                    ),
                ]
                buttons.append(row1)

                # Fila 2: Más opciones de snooze
                row2 = [
                    InlineKeyboardButton(
                        "⏰ +1h",
                        callback_data=f"reminder_snooze:{reminder.id}:60"
                    ),
                    InlineKeyboardButton(
                        "⏰ +3h",
                        callback_data=f"reminder_snooze:{reminder.id}:180"
                    ),
                ]
                buttons.append(row2)

                # Si tiene tarea de Notion asociada
                if reminder.notion_page_id:
                    row3 = [
                        InlineKeyboardButton(
                            "📋 Ver tarea",
                            callback_data=f"task_view:{reminder.notion_page_id}"
                        ),
                        InlineKeyboardButton(
                            "❌ Descartar",
                            callback_data=f"reminder_dismiss:{reminder.id}"
                        ),
                    ]
                    buttons.append(row3)
                else:
                    row3 = [
                        InlineKeyboardButton(
                            "❌ Descartar",
                            callback_data=f"reminder_dismiss:{reminder.id}"
                        ),
                    ]
                    buttons.append(row3)

                keyboard = InlineKeyboardMarkup(buttons)

                # Enviar mensaje con keyboard
                await telegram_service.send_message_with_keyboard(
                    chat_id=int(reminder.chat_id),
                    text=message,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )

                # Marcar como reconocido para evitar re-envío
                await reminder_service.mark_acknowledged(reminder.id)

                logger.info(f"Recordatorio {reminder.id} enviado a chat {reminder.chat_id}")

            except Exception as e:
                logger.error(f"Error enviando recordatorio {reminder.id}: {e}")

    except Exception as e:
        logger.error(f"Error en dispatch_pending_reminders: {e}")


async def cleanup_old_reminders():
    """
    Job para limpiar recordatorios antiguos.

    Se ejecuta una vez al día.
    """
    reminder_service = get_reminder_service()

    try:
        deleted = await reminder_service.cleanup_old_reminders(days=30)
        logger.info(f"Limpiados {deleted} recordatorios antiguos")
    except Exception as e:
        logger.error(f"Error limpiando recordatorios: {e}")


async def send_evening_planning_prompt():
    """
    Job que envía prompt de planificación nocturna.

    Se ejecuta a las 9 PM para preguntar si quiere planificar mañana.
    """
    from app.config import get_settings

    telegram_service = get_telegram_service()
    settings = get_settings()

    try:
        chat_id = settings.telegram_chat_id

        message = (
            "🌙 <b>Planificación del día siguiente</b>\n\n"
            "¿Quieres que te ayude a planificar mañana?\n"
            "Puedo revisar tus tareas pendientes y sugerirte un plan."
        )

        buttons = [
            [
                InlineKeyboardButton(
                    "📋 Planificar mañana",
                    callback_data="planning_tomorrow"
                ),
            ],
            [
                InlineKeyboardButton(
                    "📊 Ver mi semana",
                    callback_data="planning_week"
                ),
                InlineKeyboardButton(
                    "⏭️ Saltar",
                    callback_data="planning_skip"
                ),
            ],
        ]

        keyboard = InlineKeyboardMarkup(buttons)

        await telegram_service.send_message_with_keyboard(
            chat_id=chat_id,
            text=message,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        logger.info("Prompt de planificación nocturna enviado")

    except Exception as e:
        logger.error(f"Error enviando prompt de planificación: {e}")


async def send_morning_plan_reminder():
    """
    Job que envía recordatorio del plan del día.

    Se ejecuta a las 7:30 AM si hay un plan creado.
    """
    from app.config import get_settings
    from app.services.notion import get_notion_service

    telegram_service = get_telegram_service()
    notion = get_notion_service()
    settings = get_settings()

    try:
        chat_id = settings.telegram_chat_id

        # Obtener tareas para hoy
        tasks_today = await notion.get_tasks_for_today()

        if not tasks_today:
            message = (
                "🌅 <b>Buenos días!</b>\n\n"
                "No tienes tareas programadas para hoy.\n"
                "¿Quieres que te sugiera algunas?"
            )
            buttons = [
                [
                    InlineKeyboardButton(
                        "📋 Sugerir tareas",
                        callback_data="planning_suggest_today"
                    ),
                ],
            ]
        else:
            # Formatear tareas
            task_lines = []
            for i, task in enumerate(tasks_today[:5], 1):
                props = task.get("properties", {})
                name = ""
                title = props.get("Tarea", {}).get("title", [])
                if title:
                    name = title[0].get("text", {}).get("content", "")[:50]
                prioridad = props.get("Prioridad", {}).get("select", {}).get("name", "")
                task_lines.append(f"{i}. {name} [{prioridad}]")

            message = (
                f"🌅 <b>Buenos días! Tu plan para hoy:</b>\n\n"
                + "\n".join(task_lines)
            )

            if len(tasks_today) > 5:
                message += f"\n\n<i>+{len(tasks_today) - 5} tareas más</i>"

            buttons = [
                [
                    InlineKeyboardButton(
                        "👍 A trabajar",
                        callback_data="morning_ack"
                    ),
                    InlineKeyboardButton(
                        "🔄 Ajustar",
                        callback_data="planning_adjust_today"
                    ),
                ],
            ]

        keyboard = InlineKeyboardMarkup(buttons)

        await telegram_service.send_message_with_keyboard(
            chat_id=chat_id,
            text=message,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        logger.info("Recordatorio de plan matutino enviado")

    except Exception as e:
        logger.error(f"Error enviando plan matutino: {e}")
