"""Morning Briefing Job - Envía el plan del día usando MorningPlannerAgent."""

import logging
from datetime import datetime, timedelta

from app.config import get_settings
from app.services.notion import get_notion_service, TaskEstado
from app.services.telegram import get_telegram_service

logger = logging.getLogger(__name__)
settings = get_settings()


async def morning_briefing_job() -> None:
    """
    Genera y envía el briefing de la mañana usando AI.

    Usa el AgentOrchestrator para:
    - Generar plan con MorningPlannerAgent
    - Incluir contexto de tareas y hábitos
    - Mensaje personalizado según el día

    Solo se ejecuta en horario laboral (6:00 - 18:00) de lunes a viernes.
    """
    now = datetime.now()

    # Validar día laboral (lunes=0 a viernes=4)
    if now.weekday() > 4:
        logger.info(f"Morning briefing omitido - es fin de semana ({now.strftime('%A')})")
        return

    # Validar horario (6:00 - 18:00)
    if now.hour < 6 or now.hour >= 18:
        logger.info(f"Morning briefing omitido - fuera del horario ({now.hour}:00)")
        return

    logger.info("Ejecutando Morning Briefing...")

    telegram = get_telegram_service()

    try:
        # Usar el orquestador para generar el plan
        from app.agents.orchestrator import get_orchestrator

        orchestrator = get_orchestrator()

        # Generar plan con AI
        plan = await orchestrator.generate_morning_plan()

        # Formatear mensaje con el plan
        message = orchestrator.morning_planner.format_telegram_message(plan)

        # Agregar resumen de carga de trabajo
        workload = await orchestrator.get_workload_summary()
        if workload.get("overdue", 0) > 0:
            message += f"\n\n<b>Atrasadas:</b> {workload['overdue']} tareas"

        if workload.get("deadlines_this_week"):
            message += "\n\n<b>Esta semana:</b>\n"
            for deadline in workload["deadlines_this_week"][:3]:
                message += f"• {deadline['name']} ({deadline['due']})\n"

        # Enviar mensaje
        await telegram.send_message(message)
        logger.info("Morning Briefing enviado exitosamente con MorningPlannerAgent")

    except Exception as e:
        logger.error(f"Error en Morning Briefing con AI: {e}")
        # Fallback al briefing simple
        await _fallback_morning_briefing()


async def _fallback_morning_briefing() -> None:
    """Briefing simple como fallback cuando falla el AI."""
    logger.info("Usando fallback para Morning Briefing")

    notion = get_notion_service()
    telegram = get_telegram_service()

    try:
        # Obtener tareas de hoy
        today_tasks = await notion.get_tasks_for_today()

        # Obtener tareas pendientes generales
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

        await telegram.send_message(message)
        logger.info("Morning Briefing (fallback) enviado")

    except Exception as e:
        logger.error(f"Error en fallback Morning Briefing: {e}")
        try:
            await telegram.send_message(
                "Hubo un error generando el briefing de hoy. "
                "Revisa los logs para más detalles."
            )
        except Exception:
            pass


async def monday_workload_alert() -> None:
    """
    Alerta especial del lunes con resumen de carga de trabajo.
    Se ejecuta los lunes a las 7:00 AM.
    """
    logger.info("Ejecutando alerta de carga de trabajo del lunes...")

    telegram = get_telegram_service()

    try:
        from app.agents.orchestrator import get_orchestrator

        orchestrator = get_orchestrator()
        workload = await orchestrator.get_workload_summary()

        message = "<b>Resumen de la semana</b>\n\n"

        message += f"<b>Tareas pendientes:</b> {workload.get('total_pending', 0)}\n"
        message += f"<b>Tareas atrasadas:</b> {workload.get('overdue', 0)}\n\n"

        # Por prioridad
        by_priority = workload.get("by_priority", {})
        if by_priority:
            message += "<b>Por prioridad:</b>\n"
            if by_priority.get("urgente", 0) > 0:
                message += f"  Urgente: {by_priority['urgente']}\n"
            if by_priority.get("alta", 0) > 0:
                message += f"  Alta: {by_priority['alta']}\n"
            message += f"  Normal: {by_priority.get('normal', 0)}\n"
            message += f"  Baja: {by_priority.get('baja', 0)}\n\n"

        # Por contexto
        by_context = workload.get("by_context", {})
        if by_context:
            message += "<b>Por contexto:</b>\n"
            for ctx, count in by_context.items():
                message += f"  {ctx}: {count}\n"
            message += "\n"

        # Deadlines de la semana
        deadlines = workload.get("deadlines_this_week", [])
        if deadlines:
            message += "<b>Deadlines esta semana:</b>\n"
            for dl in deadlines[:5]:
                message += f"  • {dl['name']} ({dl['due']})\n"
        else:
            message += "Sin deadlines urgentes esta semana.\n"

        # Agregar total de deuda si es significativa
        total_debt = workload.get("total_debt", 0)
        if total_debt > 10000:
            message += f"\n<b>Deuda total:</b> ${total_debt:,.0f}"

        await telegram.send_message(message)
        logger.info("Alerta de carga de lunes enviada")

    except Exception as e:
        logger.error(f"Error en alerta de lunes: {e}")


def _get_task_due_date(task: dict) -> str | None:
    """Extrae la fecha de vencimiento de una tarea."""
    # Usar el campo correcto: "Fecha Due"
    due = task.get("properties", {}).get("Fecha Due", {}).get("date", {})
    return due.get("start") if due else None


def _get_task_name(task: dict) -> str:
    """Extrae el nombre de una tarea."""
    # Usar el campo correcto: "Tarea"
    title = task.get("properties", {}).get("Tarea", {}).get("title", [{}])
    return title[0].get("text", {}).get("content", "Sin título") if title else "Sin título"


def _get_task_priority(task: dict) -> str:
    """Extrae la prioridad de una tarea."""
    # Usar el campo correcto: "Prioridad"
    priority = task.get("properties", {}).get("Prioridad", {}).get("select", {})
    return priority.get("name", "Normal") if priority else "Normal"


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

    message = f"<b>Buenos días! - {weekday} {now.strftime('%d/%m')}</b>\n\n"

    # Tareas de ayer incompletas
    if yesterday_incomplete:
        message += "<b>Pendientes de ayer:</b>\n"
        for task in yesterday_incomplete[:3]:
            name = _get_task_name(task)
            message += f"  • {name}\n"
        message += "\n"

    # Tareas de hoy
    if today_tasks:
        message += "<b>Hoy tienes:</b>\n"
        for task in today_tasks:
            name = _get_task_name(task)
            priority = _get_task_priority(task)
            priority_emoji = {
                "Urgente": "",
                "Alta": "",
                "Normal": "",
                "Baja": "",
            }.get(priority, "")
            message += f"  {priority_emoji} {name}\n"
    else:
        message += "<b>No hay tareas programadas para hoy.</b>\n"
        if all_pending:
            message += "\nPodrías trabajar en alguna de estas:\n"
            for task in all_pending[:3]:
                name = _get_task_name(task)
                message += f"  • {name}\n"

    message += "\n"

    # Mensaje motivacional basado en el día
    motivational = _get_motivational_message(now.weekday())
    message += f"{motivational}"

    return message.strip()


def _get_motivational_message(weekday: int) -> str:
    """Retorna un mensaje motivacional según el día."""
    messages = {
        0: "Inicio de semana! Enfócate en las prioridades.",
        1: "Martes de acción. Mantén el momentum.",
        2: "Mitad de semana. Ya casi llegamos al viernes.",
        3: "Jueves productivo. Un día más y es viernes.",
        4: "Viernes! Cierra la semana con fuerza.",
        5: "Sábado de descanso... o de ponerse al día.",
        6: "Domingo. Prepárate para la semana que viene.",
    }
    return messages.get(weekday, "A darle!")
