"""Hourly Check-in Job - Check-in con estado real de tareas usando Orchestrator."""

import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import get_settings
from app.services.telegram import get_telegram_service
from app.services.notion import get_notion_service, TaskEstado

logger = logging.getLogger(__name__)
settings = get_settings()


async def hourly_checkin_job() -> None:
    """
    Envía un check-in cada hora con información real de tareas.

    Incluye:
    - Tarea actual en progreso (Doing O Today como trabajo activo)
    - Progreso de tareas del día
    - Opciones contextuales según estado
    """
    logger.info("Ejecutando Hourly Check-in...")

    telegram = get_telegram_service()
    notion = get_notion_service()
    hour = datetime.now().hour

    try:
        # Obtener contexto real de tareas
        from app.agents.orchestrator import get_orchestrator

        orchestrator = get_orchestrator()
        context = await orchestrator.get_context(force_refresh=True)

        # Buscar tarea actualmente en "Doing" O "Today" (ambos cuentan como trabajo activo)
        current_task = None
        working_status = None

        # Primero buscar en Doing (prioridad)
        doing_tasks = await notion.get_tasks_by_estado(TaskEstado.DOING, limit=1)
        if doing_tasks:
            props = doing_tasks[0].get("properties", {})
            title = props.get("Tarea", {}).get("title", [])
            current_task = {
                "id": doing_tasks[0].get("id"),
                "name": title[0].get("text", {}).get("content", "Sin título") if title else "Sin título",
            }
            working_status = "doing"
        else:
            # Si no hay Doing, buscar en Today (trabajo planificado)
            today_tasks = await notion.get_tasks_by_estado(TaskEstado.TODAY, limit=1)
            if today_tasks:
                props = today_tasks[0].get("properties", {})
                title = props.get("Tarea", {}).get("title", [])
                current_task = {
                    "id": today_tasks[0].get("id"),
                    "name": title[0].get("text", {}).get("content", "Sin título") if title else "Sin título",
                    "is_today": True,  # Flag para saber que viene de Today
                }
                working_status = "today"

        # Calcular progreso del día
        today_tasks = context.tasks_today
        completed_today = sum(
            1 for t in today_tasks
            if t.get("properties", {}).get("Estado", {}).get("select", {}).get("name") == TaskEstado.DONE.value
        )
        total_today = len(today_tasks)

        # Generar mensaje y teclado según contexto
        message, keyboard = _build_checkin(
            hour=hour,
            current_task=current_task,
            completed=completed_today,
            total=total_today,
            overdue_count=len(context.tasks_overdue),
            working_status=working_status,
        )

        result = await telegram.send_message_with_keyboard(
            text=message,
            reply_markup=keyboard,
        )

        # Registrar interacción para seguimiento si no responde
        if result and result.message_id:
            from app.services.interaction_tracker import get_interaction_tracker

            tracker = get_interaction_tracker()
            await tracker.register_interaction(
                chat_id=str(settings.telegram_chat_id),
                message_id=result.message_id,
                interaction_type="checkin",
                context={
                    "hour": hour,
                    "has_task": current_task is not None,
                    "task_name": current_task["name"] if current_task else None,
                },
            )

        logger.info(
            f"Hourly Check-in enviado ({hour}:30) - "
            f"Tarea actual: {current_task['name'] if current_task else 'ninguna'}"
        )

    except Exception as e:
        logger.error(f"Error en Hourly Check-in: {e}")
        # Fallback a mensaje simple
        await _simple_checkin(hour)


async def _simple_checkin(hour: int) -> None:
    """Envía un check-in simple como fallback."""
    telegram = get_telegram_service()

    message = _get_fallback_message(hour)
    keyboard = _get_fallback_keyboard()

    await telegram.send_message_with_keyboard(
        text=message,
        reply_markup=keyboard,
    )


def _build_checkin(
    hour: int,
    current_task: dict | None,
    completed: int,
    total: int,
    overdue_count: int,
    working_status: str | None = None,
) -> tuple[str, InlineKeyboardMarkup]:
    """Construye mensaje y teclado de check-in según contexto."""

    # Encabezado según hora (más casual)
    header = _get_time_header(hour)

    # Cuerpo del mensaje
    message = f"{header}\n\n"

    # Progress bar visual
    if total > 0:
        progress_pct = completed / total * 100
        filled = int(progress_pct / 10)
        bar = "█" * filled + "░" * (10 - filled)
        message += f"[{bar}] {progress_pct:.0f}%\n"
        message += f"{completed} de {total} tareas\n\n"

    # Estado de tarea actual - TONO COLABORATIVO
    if current_task:
        is_today = current_task.get("is_today", False)
        if is_today:
            message += f"📋 <b>Siguiente en la lista:</b>\n{current_task['name']}\n\n"
            message += "¿Ya empezaste con esto?"
        else:
            message += f"⚡ <b>Trabajando en:</b>\n{current_task['name']}\n\n"
            message += "¿Cómo va?"
    else:
        # Sin tarea - preguntar primero, no asumir
        message += "¿En qué andas?\n"

    # Alertas (menos agresivas)
    if overdue_count > 0:
        message += f"\n\n⚠️ {overdue_count} pendientes de días anteriores"

    # Construir teclado según contexto
    keyboard = _build_keyboard(current_task, completed < total, working_status)

    return message, keyboard


def _build_keyboard(
    current_task: dict | None,
    has_pending: bool,
    working_status: str | None = None,
) -> InlineKeyboardMarkup:
    """Construye teclado contextual - opciones colaborativas."""
    buttons = []

    if current_task:
        is_today = current_task.get("is_today", False)

        if is_today:
            # Tarea de Today - preguntar si ya empezó
            buttons.append([
                InlineKeyboardButton(
                    "▶️ Empezar ahora",
                    callback_data=f"task_start:{current_task['id'][:8]}",
                ),
                InlineKeyboardButton(
                    "🔄 Otra tarea",
                    callback_data="checkin_switch_task",
                ),
            ])
        else:
            # Tarea en Doing - opciones de progreso
            buttons.append([
                InlineKeyboardButton(
                    "👍 Avanzando",
                    callback_data="checkin_doing_well",
                ),
                InlineKeyboardButton(
                    "✅ Terminé",
                    callback_data=f"task_complete:{current_task['id'][:8]}",
                ),
            ])
            buttons.append([
                InlineKeyboardButton(
                    "🔄 Cambiar",
                    callback_data="checkin_switch_task",
                ),
                InlineKeyboardButton(
                    "🚧 Bloqueado",
                    callback_data=f"task_block:{current_task['id'][:8]}",
                ),
            ])
    else:
        # Sin tarea activa - preguntar, no asumir
        if has_pending:
            buttons.append([
                InlineKeyboardButton(
                    "📋 Ver opciones",
                    callback_data="show_pending_tasks",
                ),
                InlineKeyboardButton(
                    "🎲 Sorpréndeme",
                    callback_data="checkin_random_task",
                ),
            ])
            buttons.append([
                InlineKeyboardButton(
                    "💼 En algo fuera del bot",
                    callback_data="checkin_working_external",
                ),
            ])
        else:
            buttons.append([
                InlineKeyboardButton(
                    "➕ Agregar tarea",
                    callback_data="menu_add",
                ),
                InlineKeyboardButton(
                    "📚 Ver backlog",
                    callback_data="show_backlog",
                ),
            ])

    # Opción de "Hoy no" - SIEMPRE disponible
    buttons.append([
        InlineKeyboardButton(
            "☕ Break",
            callback_data="checkin_break",
        ),
        InlineKeyboardButton(
            "🛑 Hoy no es mi día",
            callback_data="checkin_bad_day",
        ),
    ])

    return InlineKeyboardMarkup(buttons)


def _get_time_header(hour: int) -> str:
    """Genera encabezado según la hora."""
    if hour == 9:
        return "<b>Check-in matutino</b>"
    elif hour == 10:
        return "<b>Check-in 10:30</b>"
    elif hour == 11:
        return "<b>Check-in pre-almuerzo</b>"
    elif hour == 12:
        return "<b>Check-in del mediodía</b>"
    elif hour == 13:
        return "<b>Check-in post-almuerzo</b>"
    elif hour == 14:
        return "<b>Check-in 14:30</b>"
    elif hour == 15:
        return "<b>Check-in de la tarde</b>"
    elif hour == 16:
        return "<b>Check-in 16:30</b>"
    elif hour == 17:
        return "<b>Check-in pre-cierre</b>"
    elif hour == 18:
        return "<b>Check-in de cierre</b>"
    else:
        return f"<b>Check-in ({hour}:30)</b>"


def _get_fallback_message(hour: int) -> str:
    """Mensaje de fallback si falla el contexto."""
    if hour == 9:
        return (
            "<b>Check-in matutino</b>\n\n"
            "¿Ya empezaste con la primera tarea del día?\n"
            "¿Cómo va tu nivel de energía?"
        )
    elif hour == 12:
        return (
            "<b>Check-in del mediodía</b>\n\n"
            "¿Cómo va la mañana? ¿Lograste avanzar?\n"
            "Recuerda tomar un break para comer."
        )
    elif hour == 15:
        return (
            "<b>Check-in de la tarde</b>\n\n"
            "Ya pasó la mitad del día. ¿Cómo vas?\n"
            "¿Necesitas ajustar las prioridades?"
        )
    elif hour == 17:
        return (
            "<b>Check-in de cierre</b>\n\n"
            "El día está por terminar.\n"
            "¿Qué lograste hoy? ¿Quedó algo pendiente?"
        )
    else:
        return (
            f"<b>Check-in ({hour}:30)</b>\n\n"
            "¿Cómo va todo? ¿Sigues en la misma tarea?"
        )


def _get_fallback_keyboard() -> InlineKeyboardMarkup:
    """Teclado de fallback."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Avanzando bien", callback_data="checkin_doing_well"),
            InlineKeyboardButton("Bloqueado", callback_data="checkin_blocked"),
        ],
        [
            InlineKeyboardButton("Cambiando tarea", callback_data="checkin_switch_task"),
            InlineKeyboardButton("Break", callback_data="checkin_break"),
        ],
        [
            InlineKeyboardButton("Todo bien", callback_data="checkin_dismiss"),
        ],
    ])
