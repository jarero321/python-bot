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
    - Tarea actual en progreso (si hay)
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

        # Buscar tarea actualmente en "Doing"
        current_task = None
        doing_tasks = await notion.get_tasks_by_estado(TaskEstado.DOING, limit=1)
        if doing_tasks:
            props = doing_tasks[0].get("properties", {})
            title = props.get("Tarea", {}).get("title", [])
            current_task = {
                "id": doing_tasks[0].get("id"),
                "name": title[0].get("text", {}).get("content", "Sin título") if title else "Sin título",
            }

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
        )

        await telegram.send_message_with_keyboard(
            text=message,
            reply_markup=keyboard,
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
) -> tuple[str, InlineKeyboardMarkup]:
    """Construye mensaje y teclado de check-in según contexto."""

    # Encabezado según hora
    header = _get_time_header(hour)

    # Cuerpo del mensaje
    message = f"{header}\n\n"

    # Estado de tarea actual
    if current_task:
        message += f"<b>En progreso:</b>\n{current_task['name']}\n\n"
        message += "¿Cómo va?"
    else:
        message += "<b>No hay tarea en progreso</b>\n\n"
        if total > completed:
            message += f"Tienes {total - completed} tareas pendientes hoy."
        else:
            message += "¿En qué estás trabajando?"

    # Progreso del día
    if total > 0:
        progress_pct = completed / total * 100
        message += f"\n\n<b>Progreso del día:</b> {completed}/{total} ({progress_pct:.0f}%)"

    # Alertas
    if overdue_count > 0:
        message += f"\n\n{overdue_count} tareas atrasadas"

    # Construir teclado según contexto
    keyboard = _build_keyboard(current_task, completed < total)

    return message, keyboard


def _build_keyboard(current_task: dict | None, has_pending: bool) -> InlineKeyboardMarkup:
    """Construye teclado contextual."""
    buttons = []

    if current_task:
        # Tarea en progreso - opciones de estado
        buttons.append([
            InlineKeyboardButton(
                "Bien, avanzando",
                callback_data="checkin_doing_well",
            ),
            InlineKeyboardButton(
                "Necesito ayuda",
                callback_data="checkin_need_help",
            ),
        ])
        buttons.append([
            InlineKeyboardButton(
                "Completar tarea",
                callback_data=f"task_complete:{current_task['id'][:8]}",
            ),
            InlineKeyboardButton(
                "Cambiar tarea",
                callback_data="checkin_switch_task",
            ),
        ])
        buttons.append([
            InlineKeyboardButton(
                "Bloqueado",
                callback_data=f"task_block:{current_task['id'][:8]}",
            ),
            InlineKeyboardButton(
                "Pausa",
                callback_data=f"task_pause:{current_task['id'][:8]}",
            ),
        ])
    else:
        # Sin tarea activa
        if has_pending:
            buttons.append([
                InlineKeyboardButton(
                    "Ver tareas pendientes",
                    callback_data="show_pending_tasks",
                ),
            ])
            buttons.append([
                InlineKeyboardButton(
                    "Estoy en algo",
                    callback_data="checkin_working",
                ),
                InlineKeyboardButton(
                    "Tomando break",
                    callback_data="checkin_break",
                ),
            ])
        else:
            buttons.append([
                InlineKeyboardButton(
                    "Agregar tarea",
                    callback_data="menu_add",
                ),
                InlineKeyboardButton(
                    "Ver backlog",
                    callback_data="show_backlog",
                ),
            ])

    buttons.append([
        InlineKeyboardButton(
            "Todo bien",
            callback_data="checkin_dismiss",
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
