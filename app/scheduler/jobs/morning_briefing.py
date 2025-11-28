"""Morning Briefing Job - Envía el plan del día a las 6:30 AM."""

import logging
from datetime import datetime, timedelta

from app.config import get_settings
from app.services.notion import get_notion_service
from app.services.telegram import get_telegram_service

logger = logging.getLogger(__name__)
settings = get_settings()


async def morning_briefing_job() -> None:
    """
    Genera y envía el briefing de la mañana.

    Incluye:
    - Tareas pendientes de hoy
    - Tareas incompletas de ayer
    - Mensaje motivacional
    """
    logger.info("Ejecutando Morning Briefing...")

    notion = get_notion_service()
    telegram = get_telegram_service()

    try:
        # Obtener tareas de hoy
        today_tasks = await notion.get_tasks_for_today()

        # Obtener tareas pendientes generales (incluyendo atrasadas)
        pending_tasks = await notion.get_pending_tasks(limit=10)

        # Filtrar tareas de ayer no completadas
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        yesterday_incomplete = [
            task for task in pending_tasks
            if _get_task_due_date(task) == yesterday
        ]

        # Construir mensaje
        message = _build_briefing_message(
            today_tasks=today_tasks,
            yesterday_incomplete=yesterday_incomplete,
            all_pending=pending_tasks,
        )

        # Enviar mensaje
        await telegram.send_message(message)
        logger.info("Morning Briefing enviado exitosamente")

    except Exception as e:
        logger.error(f"Error en Morning Briefing: {e}")
        # Intentar enviar mensaje de error
        try:
            await telegram.send_message(
                "⚠️ Error generando el briefing de hoy. "
                "Revisa los logs para más detalles."
            )
        except Exception:
            pass


def _get_task_due_date(task: dict) -> str | None:
    """Extrae la fecha de vencimiento de una tarea."""
    due = task.get("properties", {}).get("Due", {}).get("date", {})
    return due.get("start") if due else None


def _get_task_name(task: dict) -> str:
    """Extrae el nombre de una tarea."""
    title = task.get("properties", {}).get("Name", {}).get("title", [{}])
    return title[0].get("plain_text", "Sin título") if title else "Sin título"


def _get_task_priority(task: dict) -> str:
    """Extrae la prioridad de una tarea."""
    priority = task.get("properties", {}).get("Priority", {}).get("select", {})
    return priority.get("name", "Medium") if priority else "Medium"


def _build_briefing_message(
    today_tasks: list,
    yesterday_incomplete: list,
    all_pending: list,
) -> str:
    """Construye el mensaje del briefing."""
    now = datetime.now()
    weekday_names = [
        "Lunes", "Martes", "Miércoles", "Jueves",
        "Viernes", "Sábado", "Domingo"
    ]
    weekday = weekday_names[now.weekday()]

    message = f"""
☀️ <b>Buenos días! - {weekday} {now.strftime('%d/%m')}</b>

"""

    # Tareas de ayer incompletas
    if yesterday_incomplete:
        message += "⚠️ <b>Pendientes de ayer:</b>\n"
        for task in yesterday_incomplete[:3]:
            name = _get_task_name(task)
            message += f"  • {name}\n"
        message += "\n"

    # Tareas de hoy
    if today_tasks:
        message += "📋 <b>Hoy tienes:</b>\n"
        for task in today_tasks:
            name = _get_task_name(task)
            priority = _get_task_priority(task)
            priority_emoji = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(
                priority, ""
            )
            message += f"  {priority_emoji} {name}\n"
    else:
        message += "📋 <b>No hay tareas programadas para hoy.</b>\n"
        if all_pending:
            message += "\nPodrías trabajar en alguna de estas:\n"
            for task in all_pending[:3]:
                name = _get_task_name(task)
                message += f"  • {name}\n"

    message += "\n"

    # Mensaje motivacional basado en el día
    motivational = _get_motivational_message(now.weekday())
    message += f"💪 {motivational}"

    return message.strip()


def _get_motivational_message(weekday: int) -> str:
    """Retorna un mensaje motivacional según el día."""
    messages = {
        0: "¡Inicio de semana! Enfócate en las prioridades.",
        1: "Martes de acción. Mantén el momentum.",
        2: "Mitad de semana. Ya casi llegamos al viernes.",
        3: "Jueves productivo. Un día más y es viernes.",
        4: "¡Viernes! Cierra la semana con fuerza.",
        5: "Sábado de descanso... o de ponerse al día.",
        6: "Domingo. Prepárate para la semana que viene.",
    }
    return messages.get(weekday, "¡A darle!")
