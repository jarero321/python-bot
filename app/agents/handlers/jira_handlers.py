"""
Jira Handlers - Maneja callbacks de recordatorios de Jira.

Flujo:
1. Usuario recibe recordatorio de tareas PayCash completadas
2. Si dice que no registró → muestra lista para seleccionar
3. Para cada tarea → ayuda a crear contexto de HU
4. Genera HU formateada lista para copiar a Jira
"""

import logging
import json
from typing import Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.config import get_settings
from app.agents.jira_hu_builder import get_hu_builder

logger = logging.getLogger(__name__)
settings = get_settings()


async def handle_jira_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Maneja callbacks relacionados con Jira.
    """
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "jira_done_all":
        await handle_jira_done_all(update, context)

    elif data == "jira_need_help":
        await handle_jira_need_help(update, context)

    elif data == "jira_partial":
        await handle_jira_partial(update, context)

    elif data.startswith("jira_select:"):
        task_id = data.split(":")[1]
        await handle_jira_select_task(update, context, task_id)

    elif data.startswith("jira_template:"):
        task_id = data.split(":")[1]
        await handle_jira_template(update, context, task_id)

    elif data.startswith("jira_skip:"):
        task_id = data.split(":")[1]
        await handle_jira_skip(update, context, task_id)

    elif data == "jira_finish":
        await handle_jira_finish(update, context)


async def handle_jira_done_all(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Usuario confirmó que registró todas las tareas."""
    await update.callback_query.edit_message_text(
        "Excelente, buen trabajo hoy.\n\n"
        "Recuerda actualizar el estado en Jira también."
    )


async def handle_jira_need_help(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Usuario necesita ayuda para registrar en Jira."""
    # Obtener tareas pendientes del contexto
    pending_tasks = context.user_data.get("pending_jira_tasks", [])

    if not pending_tasks:
        # Intentar obtener del flow_data
        from app.db.database import async_session_factory
        from app.db.models import ConversationState
        from sqlalchemy import select

        async with async_session_factory() as session:
            stmt = select(ConversationState).where(
                ConversationState.chat_id == str(update.effective_chat.id)
            )
            result = await session.execute(stmt)
            state = result.scalar_one_or_none()

            if state and state.flow_data:
                try:
                    data = json.loads(state.flow_data)
                    pending_tasks = data.get("pending_jira_tasks", [])
                except json.JSONDecodeError:
                    pass

    if not pending_tasks:
        await update.callback_query.edit_message_text(
            "No encontré tareas pendientes.\n"
            "Puedes decirme qué tarea quieres registrar en Jira."
        )
        return

    # Guardar en user_data para uso posterior
    context.user_data["pending_jira_tasks"] = pending_tasks
    context.user_data["current_jira_index"] = 0

    # Empezar con la primera tarea
    await start_hu_builder(update, context, pending_tasks[0])


async def handle_jira_partial(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Usuario registró algunas pero no todas."""
    pending_tasks = context.user_data.get("pending_jira_tasks", [])

    if not pending_tasks:
        await update.callback_query.edit_message_text(
            "Selecciona las tareas que NO registraste:\n\n"
            "<i>No encontré tareas. Dime cuáles te faltan.</i>",
            parse_mode="HTML",
        )
        return

    # Mostrar lista para seleccionar
    keyboard = []
    for task in pending_tasks:
        keyboard.append([
            InlineKeyboardButton(
                f"📋 {task['title'][:40]}",
                callback_data=f"jira_select:{task['id'][:20]}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton("✅ Listo", callback_data="jira_finish"),
    ])

    await update.callback_query.edit_message_text(
        "<b>Selecciona las tareas que NO registraste:</b>\n\n"
        "<i>Te ayudaré a crear la HU para cada una.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_jira_select_task(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    task_id: str,
) -> None:
    """Usuario seleccionó una tarea para crear HU."""
    pending_tasks = context.user_data.get("pending_jira_tasks", [])

    # Buscar la tarea
    task = next((t for t in pending_tasks if t["id"].startswith(task_id)), None)

    if not task:
        await update.callback_query.edit_message_text(
            "No encontré esa tarea. Intenta de nuevo."
        )
        return

    await start_hu_builder(update, context, task)


async def start_hu_builder(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    task: dict,
) -> None:
    """Inicia el flujo de construcción de HU."""
    context.user_data["current_jira_task"] = task
    context.user_data["awaiting_jira_context"] = True

    message = (
        f"<b>Crear HU para:</b> {task['title']}\n\n"
        "Dame el contexto de la tarea:\n\n"
        "• ¿Qué problema resolviste?\n"
        "• ¿Qué cambios hiciste?\n"
        "• ¿Hay criterios de aceptación específicos?\n\n"
        "<i>Escribe libremente, yo lo estructuro.</i>"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "📋 Ver plantilla",
                callback_data=f"jira_template:{task['id'][:20]}",
            ),
            InlineKeyboardButton(
                "⏭️ Saltar",
                callback_data=f"jira_skip:{task['id'][:20]}",
            ),
        ],
    ]

    if update.callback_query:
        await update.callback_query.edit_message_text(
            message,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        from app.services.telegram import get_telegram_service
        telegram = get_telegram_service()
        await telegram.send_message(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


async def handle_jira_template(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    task_id: str,
) -> None:
    """Muestra plantilla para llenar."""
    hu_builder = get_hu_builder()

    await update.callback_query.edit_message_text(
        hu_builder.get_template_message(),
        parse_mode="HTML",
    )

    # Mantener estado de espera
    context.user_data["awaiting_jira_context"] = True


async def handle_jira_skip(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    task_id: str,
) -> None:
    """Salta la tarea actual."""
    pending_tasks = context.user_data.get("pending_jira_tasks", [])
    current_index = context.user_data.get("current_jira_index", 0)

    # Pasar a la siguiente
    next_index = current_index + 1

    if next_index < len(pending_tasks):
        context.user_data["current_jira_index"] = next_index
        await start_hu_builder(update, context, pending_tasks[next_index])
    else:
        await handle_jira_finish(update, context)


async def handle_jira_finish(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Finaliza el flujo de Jira."""
    context.user_data.pop("pending_jira_tasks", None)
    context.user_data.pop("current_jira_index", None)
    context.user_data.pop("current_jira_task", None)
    context.user_data.pop("awaiting_jira_context", None)

    await update.callback_query.edit_message_text(
        "Listo! Recuerda registrar las HUs pendientes en Jira mañana.\n\n"
        "Buen descanso."
    )


async def process_jira_context(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_message: str,
) -> bool:
    """
    Procesa el contexto del usuario para crear HU.

    Returns:
        True si procesó el mensaje, False si no estaba en flujo Jira
    """
    if not context.user_data.get("awaiting_jira_context"):
        return False

    current_task = context.user_data.get("current_jira_task")
    if not current_task:
        return False

    # Construir HU con el agente
    hu_builder = get_hu_builder()

    try:
        hu_result = await hu_builder.execute(
            task_title=current_task["title"],
            user_context=user_message,
        )

        # Enviar resultado formateado
        from app.services.telegram import get_telegram_service
        telegram = get_telegram_service()

        await telegram.send_message(
            f"<b>HU Lista para Jira:</b>\n\n{hu_result.to_telegram()}\n\n"
            "<i>Copia el contenido a Jira.</i>",
        )

        # Limpiar estado
        context.user_data["awaiting_jira_context"] = False

        # Verificar si hay más tareas
        pending_tasks = context.user_data.get("pending_jira_tasks", [])
        current_index = context.user_data.get("current_jira_index", 0)
        next_index = current_index + 1

        if next_index < len(pending_tasks):
            context.user_data["current_jira_index"] = next_index

            keyboard = [
                [
                    InlineKeyboardButton(
                        "➡️ Siguiente tarea",
                        callback_data="jira_next",
                    ),
                    InlineKeyboardButton(
                        "✅ Terminar",
                        callback_data="jira_finish",
                    ),
                ],
            ]

            await telegram.send_message(
                f"Quedan {len(pending_tasks) - next_index} tarea(s) más.",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            await telegram.send_message(
                "Listo, esas eran todas las tareas.\n"
                "Buen trabajo hoy."
            )
            # Limpiar todo
            context.user_data.pop("pending_jira_tasks", None)
            context.user_data.pop("current_jira_index", None)
            context.user_data.pop("current_jira_task", None)

        return True

    except Exception as e:
        logger.error(f"Error procesando contexto Jira: {e}")
        from app.services.telegram import get_telegram_service
        telegram = get_telegram_service()

        await telegram.send_message(
            "Hubo un error procesando el contexto.\n"
            "Intenta de nuevo o escribe /skip para saltar."
        )
        return True
