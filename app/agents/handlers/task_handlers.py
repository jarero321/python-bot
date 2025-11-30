"""
Task Handlers - CRUD de tareas.

Handlers para crear, consultar, actualizar y eliminar tareas.
"""

import logging
from typing import Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.agents.intent_router import UserIntent
from app.bot.keyboards import confirm_keyboard
from app.core.routing import (
    BaseIntentHandler,
    HandlerResponse,
    intent_handler,
)
from app.core.parsing import DSPyParser
from app.services.notion import get_notion_service, TaskEstado

logger = logging.getLogger(__name__)


@intent_handler(UserIntent.TASK_CREATE)
class TaskCreateHandler(BaseIntentHandler):
    """Handler para crear tareas."""

    name = "TaskCreateHandler"
    intents = [UserIntent.TASK_CREATE]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        entities = self.get_entities(intent_result)
        text = self.get_raw_message(intent_result)
        confidence = getattr(intent_result, "confidence", 0.5)

        # Extraer título de la tarea
        task_title = entities.get("task", text[:100])

        # Guardar en context para cuando confirme
        context.user_data["pending_task"] = task_title

        keyboard = confirm_keyboard(
            confirm_data=f"task_create:{task_title[:50]}",
            cancel_data="task_cancel",
            confirm_text="✅ Crear tarea",
            cancel_text="📥 Guardar en Inbox",
        )

        message = (
            f"📋 <b>Nueva tarea detectada</b>\n\n"
            f"<i>{task_title}</i>\n\n"
            f"Confianza: {confidence:.0%}"
        )

        return HandlerResponse(
            message=message,
            keyboard=keyboard,
        )


@intent_handler(UserIntent.TASK_QUERY)
class TaskQueryHandler(BaseIntentHandler):
    """Handler para consultar tareas."""

    name = "TaskQueryHandler"
    intents = [UserIntent.TASK_QUERY]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        notion = get_notion_service()
        tasks = await notion.get_tasks_for_today()

        if not tasks:
            return HandlerResponse(
                message=(
                    "📋 <b>Tareas de hoy</b>\n\n"
                    "No hay tareas programadas para hoy.\n\n"
                    "Usa /add [tarea] para agregar una."
                )
            )

        # Formatear tareas
        message = "📋 <b>Tareas de hoy</b>\n\n"
        for task in tasks:
            props = task.get("properties", {})
            title_prop = props.get("Tarea", {}).get("title", [])
            task_name = (
                title_prop[0].get("text", {}).get("content", "Sin título")
                if title_prop
                else "Sin título"
            )

            estado_prop = props.get("Estado", {}).get("select", {})
            estado = estado_prop.get("name", "?") if estado_prop else "?"

            status_emoji = {
                "📥 Backlog": "⬜",
                "📋 Planned": "📋",
                "🎯 Today": "🎯",
                "⚡ Doing": "🔵",
                "⏸️ Paused": "⏸️",
                "✅ Done": "✅",
                "❌ Cancelled": "❌",
            }.get(estado, "⬜")

            message += f"{status_emoji} {task_name}\n"

        return HandlerResponse(message=message)


@intent_handler(UserIntent.TASK_UPDATE)
class TaskUpdateHandler(BaseIntentHandler):
    """Handler para actualizar tareas."""

    name = "TaskUpdateHandler"
    intents = [UserIntent.TASK_UPDATE]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        entities = self.get_entities(intent_result)
        text = self.get_raw_message(intent_result)

        task_name = entities.get("task", text)
        new_status = entities.get("status", "")
        new_priority = entities.get("priority", "")

        notion = get_notion_service()
        tasks = await notion.get_pending_tasks(limit=10)

        # Buscar tarea que coincida
        matching_task = None
        for task in tasks:
            props = task.get("properties", {})
            title_prop = props.get("Tarea", {}).get("title", [])
            title = (
                title_prop[0].get("text", {}).get("content", "")
                if title_prop
                else ""
            )
            if task_name.lower() in title.lower():
                matching_task = task
                break

        if matching_task:
            task_id = matching_task.get("id", "")[:8]
            keyboard = [
                [
                    InlineKeyboardButton(
                        "⚡ En Progreso",
                        callback_data=f"task_status:doing:{task_id}",
                    ),
                    InlineKeyboardButton(
                        "✅ Completar",
                        callback_data=f"task_complete:{task_id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "⏸️ Pausar",
                        callback_data=f"task_status:paused:{task_id}",
                    ),
                    InlineKeyboardButton(
                        "📅 Reprogramar",
                        callback_data=f"task_reschedule:{task_id}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "❌ Cancelar",
                        callback_data="task_action_cancel",
                    ),
                ],
            ]

            return HandlerResponse(
                message=(
                    f"📋 <b>Actualizar tarea</b>\n\n"
                    f"<i>{title}</i>\n\n"
                    f"¿Qué deseas hacer?"
                ),
                keyboard=InlineKeyboardMarkup(keyboard),
            )

        return HandlerResponse(
            message=(
                f"🔍 No encontré tareas que coincidan con:\n"
                f"<i>{task_name[:50]}</i>\n\n"
                f"Usa /today para ver tus tareas."
            )
        )


@intent_handler(UserIntent.TASK_DELETE)
class TaskDeleteHandler(BaseIntentHandler):
    """Handler para eliminar/completar tareas."""

    name = "TaskDeleteHandler"
    intents = [UserIntent.TASK_DELETE]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        entities = self.get_entities(intent_result)
        text = self.get_raw_message(intent_result)

        task_name = entities.get("task", text)
        notion = get_notion_service()

        # Buscar tareas que coincidan
        tasks = await notion.get_pending_tasks(limit=10)
        matching_tasks = []

        for task in tasks:
            props = task.get("properties", {})
            title_prop = props.get("Tarea", {}).get("title", [])
            title = (
                title_prop[0].get("text", {}).get("content", "")
                if title_prop
                else ""
            )

            if task_name.lower() in title.lower() or title.lower() in task_name.lower():
                matching_tasks.append({
                    "id": task.get("id"),
                    "title": title,
                })

        if matching_tasks:
            keyboard = []
            for task in matching_tasks[:5]:
                short_id = task["id"][:8]
                keyboard.append([
                    InlineKeyboardButton(
                        f"✅ {task['title'][:30]}",
                        callback_data=f"task_complete:{short_id}",
                    ),
                ])
            keyboard.append([
                InlineKeyboardButton(
                    "❌ Cancelar",
                    callback_data="task_delete_cancel",
                ),
            ])

            context.user_data["pending_delete_tasks"] = matching_tasks

            return HandlerResponse(
                message=(
                    f"📋 <b>Completar/Eliminar tarea</b>\n\n"
                    f"Encontré estas tareas que coinciden con "
                    f"\"{task_name[:30]}\":\n\n"
                    f"Selecciona la que quieres marcar como completada:"
                ),
                keyboard=InlineKeyboardMarkup(keyboard),
            )

        return HandlerResponse(
            message=(
                f"🔍 No encontré tareas que coincidan con:\n"
                f"<i>{task_name[:50]}</i>\n\n"
                f"Usa /today para ver tus tareas pendientes."
            )
        )
