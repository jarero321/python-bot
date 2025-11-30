"""
Task Handlers - CRUD de tareas.

Handlers para crear, consultar, actualizar y eliminar tareas.
Usan el TaskService que combina repositorios + RAG para:
- Detección de duplicados
- Búsqueda semántica
- Indexación automática
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
from app.domain.services import get_task_service, TaskService
from app.domain.entities.task import Task, TaskStatus, TaskPriority

logger = logging.getLogger(__name__)


# ==================== Helpers ====================

def format_task_line(task: Task) -> str:
    """Formatea una tarea para mostrar en lista."""
    status_emoji = {
        TaskStatus.BACKLOG: "⬜",
        TaskStatus.PLANNED: "📋",
        TaskStatus.TODAY: "🎯",
        TaskStatus.DOING: "🔵",
        TaskStatus.PAUSED: "⏸️",
        TaskStatus.DONE: "✅",
        TaskStatus.CANCELLED: "❌",
    }.get(task.status, "⬜")

    priority_indicator = ""
    if task.priority == TaskPriority.URGENT:
        priority_indicator = "🔥 "
    elif task.priority == TaskPriority.HIGH:
        priority_indicator = "⚡ "

    overdue = " ⚠️" if task.is_overdue else ""

    return f"{status_emoji} {priority_indicator}{task.title}{overdue}"


def format_task_detail(task: Task) -> str:
    """Formatea detalles completos de una tarea."""
    lines = [f"<b>{task.title}</b>"]

    status_names = {
        TaskStatus.BACKLOG: "📥 Backlog",
        TaskStatus.PLANNED: "📋 Planificada",
        TaskStatus.TODAY: "🎯 Hoy",
        TaskStatus.DOING: "⚡ En Progreso",
        TaskStatus.PAUSED: "⏸️ Pausada",
        TaskStatus.DONE: "✅ Completada",
        TaskStatus.CANCELLED: "❌ Cancelada",
    }
    lines.append(f"Estado: {status_names.get(task.status, task.status.value)}")

    priority_names = {
        TaskPriority.URGENT: "🔥 Urgente",
        TaskPriority.HIGH: "⚡ Alta",
        TaskPriority.NORMAL: "🔄 Normal",
        TaskPriority.LOW: "🧊 Baja",
    }
    lines.append(f"Prioridad: {priority_names.get(task.priority, task.priority.value)}")

    if task.due_date:
        days = task.days_until_due
        if days is not None:
            if days < 0:
                lines.append(f"📅 Vencida hace {abs(days)} días")
            elif days == 0:
                lines.append("📅 Vence hoy")
            elif days == 1:
                lines.append("📅 Vence mañana")
            else:
                lines.append(f"📅 Vence en {days} días")

    if task.project_name:
        lines.append(f"📁 {task.project_name}")

    if task.context:
        lines.append(f"🏷️ {task.context}")

    return "\n".join(lines)


# ==================== Handlers ====================

@intent_handler(UserIntent.TASK_CREATE)
class TaskCreateHandler(BaseIntentHandler):
    """Handler para crear tareas con detección de duplicados."""

    name = "TaskCreateHandler"
    intents = [UserIntent.TASK_CREATE]

    def __init__(self, task_service: TaskService | None = None):
        super().__init__()
        self._service = task_service or get_task_service()

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

        # Verificar duplicados con RAG
        duplicate_check = await self._service.check_duplicate(task_title)

        # Guardar en context para cuando confirme
        context.user_data["pending_task"] = {
            "title": task_title,
            "priority": entities.get("priority", "normal"),
            "due_date": entities.get("due_date"),
        }

        # Si hay duplicado probable, mostrar advertencia
        if duplicate_check.is_duplicate and duplicate_check.confidence > 0.7:
            similar = duplicate_check.similar_tasks[0] if duplicate_check.similar_tasks else None

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "✅ Crear de todas formas",
                        callback_data="task_create_force",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🔄 Ver tarea existente",
                        callback_data=f"task_view:{similar['id']}" if similar else "task_cancel",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "❌ Cancelar",
                        callback_data="task_cancel",
                    ),
                ],
            ])

            message = (
                f"⚠️ <b>Posible duplicado detectado</b>\n\n"
                f"<b>Nueva:</b> <i>{task_title}</i>\n\n"
                f"<b>Similar existente:</b>\n"
                f"<i>{similar['title'] if similar else 'N/A'}</i>\n"
                f"Similitud: {duplicate_check.confidence:.0%}\n\n"
                f"¿Qué deseas hacer?"
            )

            return HandlerResponse(
                message=message,
                keyboard=keyboard,
            )

        # Sin duplicado, flujo normal
        keyboard = confirm_keyboard(
            confirm_data="task_create_confirm",
            cancel_data="task_create_inbox",
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
    """Handler para consultar tareas con búsqueda semántica."""

    name = "TaskQueryHandler"
    intents = [UserIntent.TASK_QUERY]

    def __init__(self, task_service: TaskService | None = None):
        super().__init__()
        self._service = task_service or get_task_service()

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        entities = self.get_entities(intent_result)
        search_query = entities.get("query", "")

        # Si hay query específica, usar búsqueda semántica
        if search_query:
            search_result = await self._service.smart_search(search_query, limit=10)

            if not search_result.tasks:
                return HandlerResponse(
                    message=(
                        f"🔍 <b>Búsqueda: {search_query}</b>\n\n"
                        f"No encontré tareas que coincidan.\n\n"
                        f"Usa /today para ver todas tus tareas de hoy."
                    )
                )

            lines = [f"🔍 <b>Resultados para: {search_query}</b>\n"]

            if search_result.used_semantic:
                lines.append("<i>(Búsqueda semántica)</i>\n")

            for task in search_result.tasks:
                lines.append(format_task_line(task))

            lines.append(f"\n📊 {search_result.total_found} tareas encontradas")

            return HandlerResponse(message="\n".join(lines))

        # Sin query, mostrar tareas de hoy
        tasks = await self._service.get_for_today()

        if not tasks:
            return HandlerResponse(
                message=(
                    "📋 <b>Tareas de hoy</b>\n\n"
                    "No hay tareas programadas para hoy.\n\n"
                    "Usa /add [tarea] para agregar una."
                )
            )

        # Formatear tareas usando entidades del dominio
        lines = ["📋 <b>Tareas de hoy</b>\n"]

        # Agrupar por estado
        doing = [t for t in tasks if t.status == TaskStatus.DOING]
        pending = [t for t in tasks if t.status in (TaskStatus.TODAY, TaskStatus.PLANNED)]
        paused = [t for t in tasks if t.status == TaskStatus.PAUSED]

        if doing:
            lines.append("\n<b>⚡ En progreso:</b>")
            for task in doing:
                lines.append(format_task_line(task))

        if pending:
            lines.append("\n<b>🎯 Pendientes:</b>")
            for task in pending:
                lines.append(format_task_line(task))

        if paused:
            lines.append("\n<b>⏸️ Pausadas:</b>")
            for task in paused:
                lines.append(format_task_line(task))

        # Resumen
        total = len(tasks)
        done_count = len([t for t in tasks if t.status == TaskStatus.DONE])
        lines.append(f"\n📊 {done_count}/{total} completadas")

        return HandlerResponse(message="\n".join(lines))


@intent_handler(UserIntent.TASK_UPDATE)
class TaskUpdateHandler(BaseIntentHandler):
    """Handler para actualizar tareas con búsqueda semántica."""

    name = "TaskUpdateHandler"
    intents = [UserIntent.TASK_UPDATE]

    def __init__(self, task_service: TaskService | None = None):
        super().__init__()
        self._service = task_service or get_task_service()

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        entities = self.get_entities(intent_result)
        text = self.get_raw_message(intent_result)

        task_name = entities.get("task", text)

        # Usar búsqueda semántica para encontrar la tarea
        search_result = await self._service.smart_search(task_name, limit=5)
        tasks = search_result.tasks

        # Buscar tarea que coincida
        matching_task = None
        for task in tasks:
            if task_name.lower() in task.title.lower():
                matching_task = task
                break

        if matching_task:
            # Guardar tarea en contexto
            context.user_data["updating_task_id"] = matching_task.id

            keyboard = [
                [
                    InlineKeyboardButton(
                        "⚡ En Progreso",
                        callback_data=f"task_status:{matching_task.id}:doing",
                    ),
                    InlineKeyboardButton(
                        "✅ Completar",
                        callback_data=f"task_status:{matching_task.id}:done",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "⏸️ Pausar",
                        callback_data=f"task_status:{matching_task.id}:paused",
                    ),
                    InlineKeyboardButton(
                        "📅 Reprogramar",
                        callback_data=f"task_reschedule:{matching_task.id}",
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
                    f"{format_task_detail(matching_task)}\n\n"
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
    """Handler para eliminar/completar tareas con búsqueda semántica."""

    name = "TaskDeleteHandler"
    intents = [UserIntent.TASK_DELETE]

    def __init__(self, task_service: TaskService | None = None):
        super().__init__()
        self._service = task_service or get_task_service()

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        entities = self.get_entities(intent_result)
        text = self.get_raw_message(intent_result)

        task_name = entities.get("task", text)

        # Usar búsqueda semántica para encontrar tareas
        search_result = await self._service.smart_search(task_name, limit=10)
        matching_tasks = search_result.tasks

        if matching_tasks:
            keyboard = []
            for task in matching_tasks[:5]:
                keyboard.append([
                    InlineKeyboardButton(
                        f"✅ {task.title[:30]}",
                        callback_data=f"task_complete:{task.id}",
                    ),
                ])
            keyboard.append([
                InlineKeyboardButton(
                    "❌ Cancelar",
                    callback_data="task_delete_cancel",
                ),
            ])

            # Guardar en contexto
            context.user_data["pending_complete_tasks"] = [
                {"id": t.id, "title": t.title} for t in matching_tasks
            ]

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


# ==================== Handlers adicionales ====================

@intent_handler(UserIntent.TASK_STATUS_CHANGE)
class TaskStatusChangeHandler(BaseIntentHandler):
    """Handler para cambios rápidos de estado con búsqueda semántica."""

    name = "TaskStatusChangeHandler"
    intents = [UserIntent.TASK_STATUS_CHANGE]

    def __init__(self, task_service: TaskService | None = None):
        super().__init__()
        self._service = task_service or get_task_service()

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        entities = self.get_entities(intent_result)

        task_name = entities.get("task", "")
        new_status = entities.get("status", "")

        # Mapear status del intent a enum
        status_map = {
            "doing": TaskStatus.DOING,
            "done": TaskStatus.DONE,
            "paused": TaskStatus.PAUSED,
            "today": TaskStatus.TODAY,
            "cancelled": TaskStatus.CANCELLED,
        }

        target_status = status_map.get(new_status.lower()) if new_status else None

        if not task_name:
            # Buscar tarea "doing" actual para completar
            doing_tasks = await self._service.get_by_status(TaskStatus.DOING)

            if doing_tasks and target_status == TaskStatus.DONE:
                task = doing_tasks[0]
                updated = await self._service.complete(task.id)

                if updated:
                    return HandlerResponse(
                        message=(
                            f"✅ <b>Tarea completada</b>\n\n"
                            f"<i>{updated.title}</i>\n\n"
                            f"¡Buen trabajo!"
                        )
                    )

            return HandlerResponse(
                message=(
                    "🔍 No encontré una tarea específica para actualizar.\n\n"
                    "Usa /today para ver tus tareas."
                )
            )

        # Usar búsqueda semántica para encontrar la tarea
        search_result = await self._service.smart_search(task_name, limit=5)
        matching = search_result.tasks[0] if search_result.tasks else None

        if matching and target_status:
            updated = await self._service.update_status(matching.id, target_status)

            if updated:
                status_msg = {
                    TaskStatus.DOING: "⚡ en progreso",
                    TaskStatus.DONE: "✅ completada",
                    TaskStatus.PAUSED: "⏸️ pausada",
                    TaskStatus.CANCELLED: "❌ cancelada",
                }.get(target_status, str(target_status.value))

                return HandlerResponse(
                    message=(
                        f"📋 <b>Tarea actualizada</b>\n\n"
                        f"<i>{updated.title}</i>\n"
                        f"Ahora está {status_msg}"
                    )
                )

        return HandlerResponse(
            message=(
                f"🔍 No pude actualizar la tarea.\n"
                f"Verifica el nombre e intenta de nuevo."
            )
        )
