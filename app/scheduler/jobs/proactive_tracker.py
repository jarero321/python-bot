"""Proactive Task Tracker - Sistema de seguimiento proactivo de tareas."""

import logging
from datetime import datetime, timedelta
from typing import Any

from app.config import get_settings
from app.services.notion import get_notion_service, TaskEstado, TaskPrioridad
from app.services.telegram import get_telegram_service

logger = logging.getLogger(__name__)
settings = get_settings()


async def proactive_task_check() -> None:
    """
    Verificación proactiva de tareas.
    Se ejecuta cada hora durante horario laboral.

    Verifica:
    - Tareas vencidas sin completar
    - Tareas urgentes sin progreso
    - Tareas con deadline próximo (24-48h)
    - Tareas bloqueadas por mucho tiempo
    """
    logger.info("Ejecutando verificación proactiva de tareas...")

    try:
        from app.agents.orchestrator import get_orchestrator

        orchestrator = get_orchestrator()
        notifications = await orchestrator.check_for_notifications()

        if not notifications:
            logger.info("No hay notificaciones proactivas pendientes")
            return

        telegram = get_telegram_service()

        # Enviar notificaciones importantes
        for notification in notifications:
            if notification.priority in ["high", "urgent"]:
                message = _format_notification(notification)

                if notification.action_buttons:
                    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

                    keyboard = []
                    row = []
                    for btn in notification.action_buttons:
                        row.append(InlineKeyboardButton(
                            btn["text"],
                            callback_data=btn["callback"],
                        ))
                        if len(row) >= 2:
                            keyboard.append(row)
                            row = []
                    if row:
                        keyboard.append(row)

                    await telegram.send_message_with_keyboard(
                        message,
                        InlineKeyboardMarkup(keyboard),
                    )
                else:
                    await telegram.send_message(message)

        logger.info(f"Enviadas {len(notifications)} notificaciones proactivas")

    except Exception as e:
        logger.error(f"Error en verificación proactiva: {e}")


async def deadline_alert_check() -> None:
    """
    Verifica deadlines próximos y envía alertas.
    Se ejecuta 2 veces al día: 9 AM y 3 PM.
    """
    logger.info("Verificando deadlines próximos...")

    notion = get_notion_service()
    telegram = get_telegram_service()

    try:
        now = datetime.now()
        tomorrow = now + timedelta(days=1)

        # Obtener tareas pendientes
        pending_tasks = await notion.get_pending_tasks(limit=50)

        # Filtrar tareas con deadline próximo
        urgent_deadlines = []
        soon_deadlines = []

        for task in pending_tasks:
            props = task.get("properties", {})
            fecha_due = props.get("Fecha Due", {}).get("date")

            if not fecha_due or not fecha_due.get("start"):
                continue

            due_date = datetime.strptime(fecha_due["start"], "%Y-%m-%d")

            # Obtener nombre
            title = props.get("Tarea", {}).get("title", [])
            name = title[0].get("text", {}).get("content", "Sin título") if title else "Sin título"

            task_info = {
                "id": task.get("id"),
                "name": name,
                "due": fecha_due["start"],
                "due_date": due_date,
            }

            # Vence hoy
            if due_date.date() == now.date():
                urgent_deadlines.append(task_info)
            # Vence mañana
            elif due_date.date() == tomorrow.date():
                soon_deadlines.append(task_info)

        # Enviar alertas si hay deadlines urgentes
        if urgent_deadlines:
            message = "<b>Deadlines de HOY</b>\n\n"
            for task in urgent_deadlines:
                message += f"• {task['name']}\n"
            message += "\nEstas tareas vencen hoy."

            await telegram.send_message(message)

        if soon_deadlines:
            message = "<b>Deadlines de MAÑANA</b>\n\n"
            for task in soon_deadlines:
                message += f"• {task['name']}\n"
            message += "\nPlanifica tiempo para completarlas."

            await telegram.send_message(message)

        logger.info(
            f"Alertas de deadline: {len(urgent_deadlines)} hoy, "
            f"{len(soon_deadlines)} mañana"
        )

    except Exception as e:
        logger.error(f"Error verificando deadlines: {e}")


async def stale_tasks_check() -> None:
    """
    Verifica tareas estancadas (sin progreso por mucho tiempo).
    Se ejecuta una vez al día a las 5 PM.
    """
    logger.info("Verificando tareas estancadas...")

    notion = get_notion_service()
    telegram = get_telegram_service()

    try:
        # Obtener tareas en estado "Doing" o "Today" por más de 3 días
        today_tasks = await notion.get_tasks_by_estado(TaskEstado.TODAY, limit=20)
        doing_tasks = await notion.get_tasks_by_estado(TaskEstado.DOING, limit=20)

        stale_tasks = []
        three_days_ago = datetime.now() - timedelta(days=3)

        for task in today_tasks + doing_tasks:
            props = task.get("properties", {})

            # Verificar fecha de última modificación
            last_edited = task.get("last_edited_time", "")
            if last_edited:
                last_edit_date = datetime.fromisoformat(last_edited.replace("Z", "+00:00"))
                if last_edit_date.replace(tzinfo=None) < three_days_ago:
                    title = props.get("Tarea", {}).get("title", [])
                    name = title[0].get("text", {}).get("content", "Sin título") if title else "Sin título"

                    estado = props.get("Estado", {}).get("select", {}).get("name", "?")

                    stale_tasks.append({
                        "id": task.get("id"),
                        "name": name,
                        "estado": estado,
                        "days_stale": (datetime.now() - last_edit_date.replace(tzinfo=None)).days,
                    })

        if stale_tasks:
            message = "<b>Tareas sin progreso</b>\n\n"
            message += "Estas tareas llevan más de 3 días sin actualizarse:\n\n"

            for task in stale_tasks[:5]:
                message += f"• {task['name']} ({task['days_stale']} días)\n"

            message += "\n¿Qué hacemos con ellas?"

            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            keyboard = [
                [
                    InlineKeyboardButton(
                        "Ver todas",
                        callback_data="show_stale_tasks",
                    ),
                    InlineKeyboardButton(
                        "Ignorar",
                        callback_data="dismiss_stale",
                    ),
                ],
            ]

            await telegram.send_message_with_keyboard(
                message,
                InlineKeyboardMarkup(keyboard),
            )

            logger.info(f"Encontradas {len(stale_tasks)} tareas estancadas")
        else:
            logger.info("No hay tareas estancadas")

    except Exception as e:
        logger.error(f"Error verificando tareas estancadas: {e}")


async def task_completion_follow_up() -> None:
    """
    Seguimiento de tareas marcadas como completadas.
    Verifica que realmente se hayan terminado.
    Se ejecuta a las 7 PM.
    """
    logger.info("Ejecutando seguimiento de tareas completadas...")

    notion = get_notion_service()
    telegram = get_telegram_service()

    try:
        # Obtener tareas de hoy
        today_tasks = await notion.get_tasks_for_today()

        completed = []
        pending = []
        doing = []

        for task in today_tasks:
            props = task.get("properties", {})
            estado = props.get("Estado", {}).get("select", {}).get("name", "")
            title = props.get("Tarea", {}).get("title", [])
            name = title[0].get("text", {}).get("content", "Sin título") if title else "Sin título"

            if estado == TaskEstado.DONE.value:
                completed.append(name)
            elif estado == TaskEstado.DOING.value:
                doing.append(name)
            else:
                pending.append(name)

        total = len(today_tasks)

        if total == 0:
            return

        completion_rate = len(completed) / total * 100 if total > 0 else 0

        message = "<b>Resumen del día</b>\n\n"
        message += f"<b>Completadas:</b> {len(completed)}/{total} ({completion_rate:.0f}%)\n"

        if completed:
            message += "\n<b>Terminadas hoy:</b>\n"
            for task in completed[:5]:
                message += f"  • {task}\n"

        if doing:
            message += "\n<b>En progreso:</b>\n"
            for task in doing[:3]:
                message += f"  • {task}\n"

        if pending:
            message += "\n<b>Sin empezar:</b>\n"
            for task in pending[:3]:
                message += f"  • {task}\n"

        # Mensaje de cierre según rendimiento
        if completion_rate >= 80:
            message += "\n Excelente día! Buen trabajo."
        elif completion_rate >= 50:
            message += "\n Buen progreso. Mañana terminamos lo pendiente."
        elif completion_rate > 0:
            message += "\n Algo de avance. Revisa tus prioridades para mañana."
        else:
            message += "\n Día difícil? Mañana es una nueva oportunidad."

        await telegram.send_message(message)
        logger.info(f"Seguimiento enviado: {len(completed)}/{total} completadas")

    except Exception as e:
        logger.error(f"Error en seguimiento de tareas: {e}")


async def blocked_tasks_reminder() -> None:
    """
    Recordatorio de tareas bloqueadas.
    Se ejecuta cada 4 horas durante horario laboral.
    """
    logger.info("Verificando tareas bloqueadas...")

    notion = get_notion_service()
    telegram = get_telegram_service()

    try:
        # Obtener tareas pendientes
        pending_tasks = await notion.get_pending_tasks(limit=50)

        blocked_tasks = []

        for task in pending_tasks:
            props = task.get("properties", {})

            # Verificar si está bloqueada
            is_blocked = props.get("Bloqueada", {}).get("checkbox", False)

            if is_blocked:
                title = props.get("Tarea", {}).get("title", [])
                name = title[0].get("text", {}).get("content", "Sin título") if title else "Sin título"

                blocker_text = props.get("Blocker", {}).get("rich_text", [])
                blocker = blocker_text[0].get("text", {}).get("content", "Sin especificar") if blocker_text else "Sin especificar"

                blocked_tasks.append({
                    "id": task.get("id"),
                    "name": name,
                    "blocker": blocker,
                })

        if blocked_tasks:
            message = "<b>Tareas bloqueadas</b>\n\n"
            message += "Estas tareas necesitan atención:\n\n"

            for task in blocked_tasks[:5]:
                message += f"• <b>{task['name']}</b>\n"
                message += f"  Bloqueado por: {task['blocker']}\n\n"

            message += "¿Puedes resolver algún blocker hoy?"

            await telegram.send_message(message)
            logger.info(f"Recordatorio de {len(blocked_tasks)} tareas bloqueadas")
        else:
            logger.info("No hay tareas bloqueadas")

    except Exception as e:
        logger.error(f"Error verificando tareas bloqueadas: {e}")


def _format_notification(notification) -> str:
    """Formatea una notificación proactiva."""
    emoji_map = {
        "deadline": "",
        "reminder": "",
        "check_in": "",
        "suggestion": "",
        "alert": "",
    }

    emoji = emoji_map.get(notification.type, "")

    message = f"{emoji} <b>{notification.title}</b>\n\n"
    message += notification.message

    return message
