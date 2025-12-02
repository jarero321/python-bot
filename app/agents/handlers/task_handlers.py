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

def format_task_line(task: Task, is_subtask: bool = False) -> str:
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

    # Indentación para subtareas
    prefix = "  └─ " if is_subtask else ""

    return f"{prefix}{status_emoji} {priority_indicator}{task.title}{overdue}"


def group_tasks_with_subtasks(tasks: list[Task]) -> list[tuple[Task, list[Task]]]:
    """
    Agrupa tareas: retorna lista de (tarea_padre, [subtareas]).
    Las tareas sin padre van con lista vacía.
    Las subtareas se agrupan bajo su tarea padre.
    """
    # Separar tareas padre y subtareas
    parent_tasks = {}  # id -> task
    subtasks_by_parent = {}  # parent_id -> [subtasks]
    orphan_subtasks = []  # Subtareas cuyo padre no está en la lista

    for task in tasks:
        if task.parent_task_id:
            # Es una subtarea
            if task.parent_task_id not in subtasks_by_parent:
                subtasks_by_parent[task.parent_task_id] = []
            subtasks_by_parent[task.parent_task_id].append(task)
        else:
            # Es tarea padre o independiente
            parent_tasks[task.id] = task

    result = []
    processed_parent_ids = set()

    # Primero, agregar tareas padre con sus subtareas
    for task_id, task in parent_tasks.items():
        subtasks = subtasks_by_parent.get(task_id, [])
        result.append((task, subtasks))
        processed_parent_ids.add(task_id)

    # Agregar subtareas huérfanas (su padre no está en la lista actual)
    for parent_id, subtasks in subtasks_by_parent.items():
        if parent_id not in processed_parent_ids:
            for subtask in subtasks:
                orphan_subtasks.append(subtask)

    # Agregar subtareas huérfanas como tareas independientes con indicador
    for subtask in orphan_subtasks:
        result.append((subtask, []))

    return result


def format_task_detail(task: Task) -> str:
    """Formatea detalles completos de una tarea."""
    lines = [f"<b>{task.title}</b>"]

    # Indicar si es subtarea
    if task.parent_task_id:
        lines.append("<i>(Subtarea)</i>")

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

    # Mostrar notas/contexto si existe (especialmente útil para subtareas)
    if task.notes:
        # Mostrar solo las primeras líneas si es muy largo
        notes_preview = task.notes[:150]
        if len(task.notes) > 150:
            notes_preview += "..."
        lines.append(f"\n📝 <i>{notes_preview}</i>")

    return "\n".join(lines)


# ==================== Handlers ====================

@intent_handler(UserIntent.TASK_CREATE)
class TaskCreateHandler(BaseIntentHandler):
    """Handler para crear tareas con detección de duplicados y enriquecimiento."""

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

        # Obtener enriquecimiento del UnifiedOrchestrator
        complexity = entities.get("_complexity", {})
        subtasks = entities.get("_subtasks", [])
        blockers = entities.get("_blockers", [])
        suggested_context = entities.get("_context")
        suggested_dates = entities.get("_dates", {})
        reminders = entities.get("_reminders", [])

        # Verificar duplicados con RAG
        duplicate_check = await self._service.check_duplicate(task_title)

        # Obtener proyecto relacionado del enriquecimiento
        project_match = entities.get("_project")

        # Guardar en context para cuando confirme (incluir enriquecimiento)
        context.user_data["pending_task"] = {
            "title": task_title,
            "priority": entities.get("priority", "normal"),
            "due_date": entities.get("due_date") or suggested_dates.get("fecha_due"),
            "fecha_do": suggested_dates.get("fecha_do"),
            "context": suggested_context,
            "complexity": complexity,
            "subtasks": subtasks,
            "blockers": blockers,
            "reminders": reminders,
            "project_match": project_match,
        }

        # Si hay duplicado probable, mostrar advertencia CON enriquecimiento
        if duplicate_check.is_duplicate and duplicate_check.confidence > 0.7:
            similar = duplicate_check.similar_tasks[0] if duplicate_check.similar_tasks else None

            # Mostrar prioridad si no es normal
            priority_str = entities.get("priority", "normal")
            priority_display = ""
            if priority_str == "urgent":
                priority_display = " 🔥"
            elif priority_str == "high":
                priority_display = " ⚡"
            elif priority_str == "low":
                priority_display = " 🧊"

            msg_parts = [
                f"⚠️ <b>Posible duplicado detectado</b>\n",
                f"<b>Nueva:</b> <i>{task_title}</i>{priority_display}\n",
                f"<b>Similar existente:</b>",
                f"<i>{similar['title'] if similar else 'N/A'}</i>",
                f"Similitud: {duplicate_check.confidence:.0%}",
            ]

            # Mostrar análisis de complejidad (igual que sin duplicado)
            if complexity:
                level = complexity.get("level", "standard")
                minutes = complexity.get("estimated_minutes", 0)
                energy = complexity.get("energy_required", "medium")

                complexity_emoji = {"quick": "⚡", "standard": "🔄", "heavy": "🏋️", "epic": "🚀"}.get(level, "🔄")
                energy_emoji = {"deep_work": "🧠", "medium": "💪", "low": "😌"}.get(energy, "💪")

                msg_parts.append(f"\n<b>Análisis:</b>")
                msg_parts.append(f"{complexity_emoji} Complejidad: {level}")
                if minutes:
                    hours = minutes // 60
                    mins = minutes % 60
                    time_str = f"{hours}h {mins}m" if hours else f"{mins}m"
                    msg_parts.append(f"⏱️ Tiempo estimado: {time_str}")
                msg_parts.append(f"{energy_emoji} Energía: {energy}")

            # Mostrar subtareas sugeridas
            if subtasks:
                msg_parts.append(f"\n<b>Subtareas sugeridas:</b>")
                for i, sub in enumerate(subtasks[:5], 1):
                    msg_parts.append(f"  {i}. {sub}")

            # Mostrar proyecto relacionado
            if project_match:
                msg_parts.append(f"\n📁 <b>Proyecto:</b> {project_match.get('name', 'N/A')}")

            msg_parts.append(f"\n¿Qué deseas hacer?")

            # Construir keyboard con opciones
            keyboard_buttons = [
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
            ]

            # Agregar opciones de subtareas si hay
            if subtasks:
                keyboard_buttons.append([
                    InlineKeyboardButton("📝 Solo tarea principal", callback_data="task_create_no_subtasks"),
                    InlineKeyboardButton("✏️ Editar subtareas", callback_data="task_edit_subtasks"),
                ])

            keyboard_buttons.append([
                InlineKeyboardButton(
                    "❌ Cancelar",
                    callback_data="task_cancel",
                ),
            ])

            return HandlerResponse(
                message="\n".join(msg_parts),
                keyboard=InlineKeyboardMarkup(keyboard_buttons),
            )

        # Sin duplicado, construir mensaje con enriquecimiento
        msg_parts = [f"📋 <b>Nueva tarea detectada</b>\n", f"<i>{task_title}</i>"]

        # Mostrar prioridad
        priority_str = entities.get("priority", "normal")
        if priority_str == "urgent":
            msg_parts.append("\n🔥 <b>Prioridad:</b> Urgente")
        elif priority_str == "high":
            msg_parts.append("\n⚡ <b>Prioridad:</b> Alta")
        elif priority_str == "low":
            msg_parts.append("\n🧊 <b>Prioridad:</b> Baja")

        # Mostrar análisis de complejidad
        if complexity:
            level = complexity.get("level", "standard")
            minutes = complexity.get("estimated_minutes", 0)
            energy = complexity.get("energy_required", "medium")

            complexity_emoji = {"quick": "⚡", "standard": "🔄", "heavy": "🏋️", "epic": "🚀"}.get(level, "🔄")
            energy_emoji = {"deep_work": "🧠", "medium": "💪", "low": "😌"}.get(energy, "💪")

            msg_parts.append(f"\n\n<b>Análisis:</b>")
            msg_parts.append(f"{complexity_emoji} Complejidad: {level}")
            if minutes:
                hours = minutes // 60
                mins = minutes % 60
                time_str = f"{hours}h {mins}m" if hours else f"{mins}m"
                msg_parts.append(f"⏱️ Tiempo estimado: {time_str}")
            msg_parts.append(f"{energy_emoji} Energía: {energy}")

        # Mostrar subtareas sugeridas
        if subtasks:
            msg_parts.append(f"\n\n<b>Subtareas sugeridas:</b>")
            for i, sub in enumerate(subtasks[:5], 1):
                msg_parts.append(f"  {i}. {sub}")
            msg_parts.append("\n<i>Puedes modificarlas después de crear</i>")

        # Mostrar blockers
        if blockers:
            msg_parts.append(f"\n\n⚠️ <b>Posibles blockers:</b>")
            for blocker in blockers[:3]:
                msg_parts.append(f"  • {blocker}")

        # Mostrar fechas sugeridas
        if suggested_dates.get("fecha_do") or suggested_dates.get("fecha_due"):
            msg_parts.append(f"\n\n📅 <b>Fechas sugeridas:</b>")
            if suggested_dates.get("fecha_do"):
                msg_parts.append(f"  Hacer: {suggested_dates['fecha_do']}")
            if suggested_dates.get("fecha_due"):
                msg_parts.append(f"  Deadline: {suggested_dates['fecha_due']}")

        # Mostrar proyecto detectado
        if project_match:
            project_name = project_match.get("name", "")
            msg_parts.append(f"\n\n📁 <b>Proyecto:</b> {project_name}")

        msg_parts.append(f"\n\n<i>Confianza: {confidence:.0%}</i>")

        # Keyboard con opciones
        keyboard_buttons = [
            [
                InlineKeyboardButton("✅ Crear tarea", callback_data="task_create_confirm"),
                InlineKeyboardButton("📥 Inbox", callback_data="task_create_inbox"),
            ],
        ]

        # Botón para editar/cambiar proyecto
        if project_match:
            keyboard_buttons.append([
                InlineKeyboardButton("📁 Cambiar proyecto", callback_data="task_change_project"),
            ])
        else:
            keyboard_buttons.append([
                InlineKeyboardButton("📁 Asignar proyecto", callback_data="task_change_project"),
            ])

        if subtasks:
            keyboard_buttons.append([
                InlineKeyboardButton("📝 Solo tarea principal", callback_data="task_create_no_subtasks"),
                InlineKeyboardButton("✏️ Editar subtareas", callback_data="task_edit_subtasks"),
            ])

        keyboard_buttons.append([
            InlineKeyboardButton("❌ Cancelar", callback_data="task_cancel"),
        ])

        return HandlerResponse(
            message="\n".join(msg_parts),
            keyboard=InlineKeyboardMarkup(keyboard_buttons),
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
        completed_today = await self._service.get_completed_today()

        if not tasks and not completed_today:
            return HandlerResponse(
                message=(
                    "📋 <b>Tareas de hoy</b>\n\n"
                    "No hay tareas programadas para hoy.\n\n"
                    "Usa /add [tarea] para agregar una."
                )
            )

        # Formatear tareas usando entidades del dominio
        lines = ["📋 <b>Tareas de hoy</b>\n"]

        # Agrupar tareas padre con subtareas (si hay tareas pendientes)
        grouped = group_tasks_with_subtasks(tasks) if tasks else []

        # Separar por estado (solo tareas padre/independientes para la agrupación)
        def format_grouped_tasks(task_list: list[tuple[Task, list[Task]]]) -> list[str]:
            """Formatea tareas agrupadas con sus subtareas."""
            result = []
            for task, subtasks in task_list:
                result.append(format_task_line(task, is_subtask=bool(task.parent_task_id)))
                for subtask in subtasks:
                    result.append(format_task_line(subtask, is_subtask=True))
            return result

        # Filtrar por estado
        doing_grouped = [(t, subs) for t, subs in grouped if t.status == TaskStatus.DOING]
        pending_grouped = [(t, subs) for t, subs in grouped if t.status in (TaskStatus.TODAY, TaskStatus.PLANNED)]
        paused_grouped = [(t, subs) for t, subs in grouped if t.status == TaskStatus.PAUSED]

        if doing_grouped:
            lines.append("\n<b>⚡ En progreso:</b>")
            lines.extend(format_grouped_tasks(doing_grouped))

        if pending_grouped:
            lines.append("\n<b>🎯 Pendientes:</b>")
            lines.extend(format_grouped_tasks(pending_grouped))

        if paused_grouped:
            lines.append("\n<b>⏸️ Pausadas:</b>")
            lines.extend(format_grouped_tasks(paused_grouped))

        # Mostrar tareas completadas hoy
        if completed_today:
            lines.append("\n<b>✅ Completadas hoy:</b>")
            for task in completed_today[:5]:  # Mostrar máximo 5
                lines.append(f"  ✓ <s>{task.title}</s>")
            if len(completed_today) > 5:
                lines.append(f"  <i>... y {len(completed_today) - 5} más</i>")

        # Resumen con historial de completadas
        pending_count = len(tasks)
        completed_count = len(completed_today)
        total_today = pending_count + completed_count

        parent_count = len([t for t, _ in grouped if not t.parent_task_id])
        subtask_count = sum(len(subs) for _, subs in grouped)

        lines.append(f"\n📊 <b>{completed_count}/{total_today}</b> completadas hoy")
        if pending_count > 0:
            lines.append(f"🎯 {pending_count} pendientes")
        if subtask_count > 0:
            lines.append(f"<i>({parent_count} tareas principales, {subtask_count} subtareas)</i>")

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
                        "📁 Cambiar proyecto",
                        callback_data=f"task_change_project_created:{matching_task.id}",
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


def _truncate_task_title(title: str, max_length: int = 35) -> str:
    """Trunca título de tarea, permitiendo 2 líneas si es necesario."""
    if len(title) <= max_length:
        return title
    # Buscar un espacio para cortar de forma natural
    cut_point = title[:max_length].rfind(' ')
    if cut_point == -1 or cut_point < max_length // 2:
        cut_point = max_length
    return title[:cut_point] + "..."


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

        # Si es una búsqueda genérica ("algunas tareas", "tareas", etc.), mostrar tareas de hoy
        generic_terms = ["algunas tareas", "tareas", "algunas", "varias", "mis tareas"]
        is_generic = any(term in task_name.lower() for term in generic_terms)

        if is_generic:
            # Obtener tareas pendientes de hoy
            all_tasks = await self._service.get_for_today()
            # Filtrar solo las pendientes (no completadas)
            matching_tasks = [
                t for t in all_tasks
                if t.status not in (TaskStatus.DONE, TaskStatus.CANCELLED)
            ]
        else:
            # Usar búsqueda semántica para encontrar tareas específicas
            search_result = await self._service.smart_search(task_name, limit=10)
            matching_tasks = search_result.tasks

        # Eliminar duplicados por ID
        seen_ids = set()
        unique_tasks = []
        for task in matching_tasks:
            if task.id not in seen_ids:
                seen_ids.add(task.id)
                unique_tasks.append(task)
        matching_tasks = unique_tasks

        if matching_tasks:
            # Inicializar selección vacía
            context.user_data["multi_select_tasks"] = {}
            context.user_data["multi_select_available"] = [
                {"id": t.id, "title": t.title} for t in matching_tasks[:8]
            ]

            # Construir keyboard con checkboxes (todos deseleccionados inicialmente)
            keyboard = []
            for task in matching_tasks[:8]:
                # Mostrar título en 2 líneas si es largo
                display_title = _truncate_task_title(task.title, 35)
                keyboard.append([
                    InlineKeyboardButton(
                        f"☐ {display_title}",
                        # Usar últimos 8 caracteres porque los IDs de Notion comparten prefijo
                        callback_data=f"task_toggle:{task.id[-8:]}",
                    ),
                ])

            # Botones de acción
            keyboard.append([
                InlineKeyboardButton(
                    "✅ Completar seleccionadas",
                    callback_data="task_complete_selected",
                ),
            ])
            keyboard.append([
                InlineKeyboardButton(
                    "☑️ Seleccionar todas",
                    callback_data="task_select_all",
                ),
                InlineKeyboardButton(
                    "❌ Cancelar",
                    callback_data="task_delete_cancel",
                ),
            ])

            # Guardar en contexto para compatibilidad
            context.user_data["pending_complete_tasks"] = [
                {"id": t.id, "title": t.title} for t in matching_tasks
            ]

            return HandlerResponse(
                message=(
                    f"📋 <b>Completar tareas</b>\n\n"
                    f"Selecciona las tareas que quieres completar:\n"
                    f"<i>(Toca para marcar/desmarcar)</i>"
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
