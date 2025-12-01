"""
Handlers del bot de Telegram.

Este módulo contiene:
- Comandos básicos (/start, /help, /status, etc.)
- Manejador principal de mensajes (delega al registry)
- Callback handlers para botones inline

La lógica de negocio está en app/agents/handlers/ usando el patrón Handler Registry.
"""

import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.bot.keyboards import main_menu_keyboard
from app.bot.conversations import (
    get_inbox_conversation_handler,
    get_deepwork_conversation_handler,
    get_purchase_conversation_handler,
    get_gym_conversation_handler,
    get_nutrition_conversation_handler,
)
from app.config import get_settings
from app.services.notion import get_notion_service

logger = logging.getLogger(__name__)
settings = get_settings()

# Application singleton
_application: Application | None = None
_initialized: bool = False


# ==================== COMMAND HANDLERS ====================


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /start."""
    user = update.effective_user
    await update.message.reply_html(
        f"Hola <b>{user.first_name}</b>! Soy Carlos Command.\n\n"
        "Tu asistente personal para gestión de vida.\n\n"
        "<b>Comandos disponibles:</b>\n"
        "/today - Tareas de hoy\n"
        "/add [tarea] - Agregar tarea rápida\n"
        "/doing - Marcar tarea en progreso\n"
        "/done - Completar tarea actual\n"
        "/status - Estado del sistema\n"
        "/help - Ver ayuda completa",
        reply_markup=main_menu_keyboard(),
    )
    logger.info(f"Usuario {user.id} ejecutó /start")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /help."""
    await update.message.reply_html(
        "<b>Ayuda - Carlos Command</b>\n\n"
        "Puedes enviarme mensajes naturales y los procesaré.\n\n"
        "<b>Comandos de Tareas:</b>\n"
        "/today - Ver tareas para hoy\n"
        "/add [tarea] - Agregar tarea rápida\n"
        "/doing - Marcar tarea en progreso\n"
        "/done - Completar tarea actual\n\n"
        "<b>Otros:</b>\n"
        "/status - Estado del sistema\n"
        "/inbox - Ver inbox pendiente\n"
        "/projects - Listar proyectos\n\n"
        "<b>Tips:</b>\n"
        "• Envía cualquier mensaje para procesarlo con AI\n"
        "• 'Crear tarea revisar emails'\n"
        "• '¿Qué tengo pendiente?'\n"
        "• 'Gasté $500 en comida'"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /status."""
    notion = get_notion_service()

    # Test conexión Notion
    notion_ok = await notion.test_connection()
    notion_status = "✅ Conectado" if notion_ok else "❌ Error"

    await update.message.reply_html(
        "<b>Estado del Sistema</b>\n\n"
        f"<b>Entorno:</b> {settings.app_env}\n"
        f"<b>Bot:</b> ✅ Online\n"
        f"<b>Notion:</b> {notion_status}\n"
        f"<b>Hora:</b> {datetime.now().strftime('%H:%M:%S')}"
    )


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /today - muestra tareas de hoy."""
    from app.domain.services import get_task_service

    service = get_task_service()
    tasks = await service.get_for_today()

    if not tasks:
        await update.message.reply_html(
            "📋 <b>Tareas de hoy</b>\n\n"
            "No hay tareas programadas para hoy.\n\n"
            "Usa /add [tarea] para agregar una."
        )
        return

    from app.domain.entities.task import TaskStatus, TaskPriority

    message = "📋 <b>Tareas de hoy</b>\n\n"

    # Agrupar por estado
    doing = [t for t in tasks if t.status == TaskStatus.DOING]
    pending = [t for t in tasks if t.status in (TaskStatus.TODAY, TaskStatus.PLANNED)]
    done = [t for t in tasks if t.status == TaskStatus.DONE]

    if doing:
        message += "<b>⚡ En progreso:</b>\n"
        for task in doing:
            priority = "🔥 " if task.priority == TaskPriority.URGENT else ""
            message += f"🔵 {priority}{task.title}\n"
        message += "\n"

    if pending:
        message += "<b>🎯 Pendientes:</b>\n"
        for task in pending:
            priority = "🔥 " if task.priority == TaskPriority.URGENT else ""
            overdue = " ⚠️" if task.is_overdue else ""
            message += f"⬜ {priority}{task.title}{overdue}\n"
        message += "\n"

    if done:
        message += f"<b>✅ Completadas:</b> {len(done)}\n"

    message += f"\n📊 {len(done)}/{len(tasks)} completadas"

    await update.message.reply_html(message)


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /add - agrega una tarea rápida."""
    if not context.args:
        await update.message.reply_html(
            "Uso: /add [descripción de la tarea]\n\n"
            "Ejemplo: /add Revisar emails del trabajo"
        )
        return

    task_text = " ".join(context.args)

    from app.domain.services import get_task_service
    from app.domain.entities.task import Task, TaskStatus

    service = get_task_service()

    # Verificar duplicados
    duplicate_check = await service.check_duplicate(task_text)

    if duplicate_check.is_duplicate and duplicate_check.confidence > 0.8:
        similar = duplicate_check.similar_tasks[0] if duplicate_check.similar_tasks else None
        await update.message.reply_html(
            f"⚠️ <b>Posible duplicado</b>\n\n"
            f"Ya existe: <i>{similar['title'] if similar else 'N/A'}</i>\n"
            f"Similitud: {duplicate_check.confidence:.0%}\n\n"
            f"¿Crear de todas formas? Usa el botón o escribe la tarea con más detalle."
        )
        return

    # Crear tarea
    new_task = Task(
        id="",  # Se asignará al crear
        title=task_text,
        status=TaskStatus.TODAY,
    )

    created, _ = await service.create(new_task, check_duplicates=False)

    await update.message.reply_html(
        f"✅ <b>Tarea creada</b>\n\n"
        f"<i>{created.title}</i>\n\n"
        f"Estado: 🎯 Hoy"
    )


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /done - completa la tarea actual."""
    from app.domain.services import get_task_service
    from app.domain.entities.task import TaskStatus

    service = get_task_service()

    # Buscar tarea en progreso
    doing_tasks = await service.get_by_status(TaskStatus.DOING)

    if not doing_tasks:
        await update.message.reply_html(
            "🔍 No hay tareas en progreso.\n\n"
            "Usa /doing para marcar una tarea como en progreso."
        )
        return

    task = doing_tasks[0]
    completed = await service.complete(task.id)

    if completed:
        await update.message.reply_html(
            f"✅ <b>Tarea completada</b>\n\n"
            f"<i>{completed.title}</i>\n\n"
            f"¡Buen trabajo! 🎉"
        )
    else:
        await update.message.reply_text("❌ Error completando la tarea.")


async def doing_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /doing - marca tarea en progreso."""
    from app.domain.services import get_task_service
    from app.domain.entities.task import TaskStatus

    service = get_task_service()

    if context.args:
        # Buscar tarea por nombre
        task_name = " ".join(context.args)
        search_result = await service.smart_search(task_name, limit=1)

        if search_result.tasks:
            task = search_result.tasks[0]
            updated = await service.update_status(task.id, TaskStatus.DOING)

            if updated:
                await update.message.reply_html(
                    f"⚡ <b>Tarea en progreso</b>\n\n"
                    f"<i>{updated.title}</i>"
                )
                return

    # Mostrar tareas de hoy para seleccionar
    tasks = await service.get_for_today()
    pending = [t for t in tasks if t.status in (TaskStatus.TODAY, TaskStatus.PLANNED)]

    if not pending:
        await update.message.reply_html(
            "📋 No hay tareas pendientes para hoy.\n\n"
            "Usa /add [tarea] para agregar una."
        )
        return

    keyboard = []
    for task in pending[:5]:
        keyboard.append([
            InlineKeyboardButton(
                f"⚡ {task.title[:30]}",
                callback_data=f"task_doing:{task.id}",
            ),
        ])

    await update.message.reply_html(
        "📋 <b>Selecciona la tarea a iniciar:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def projects_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /projects."""
    from app.domain.services import get_project_service

    service = get_project_service()
    projects = await service.get_active()

    if not projects:
        await update.message.reply_html(
            "📁 <b>Proyectos</b>\n\n"
            "No tienes proyectos activos.\n\n"
            "Crea uno con: 'Nuevo proyecto [nombre]'"
        )
        return

    message = "📁 <b>Proyectos Activos</b>\n\n"

    for project in projects[:10]:
        # Barra de progreso
        filled = int(project.progress / 10)
        bar = "▓" * filled + "░" * (10 - filled)

        type_emoji = {
            "work": "💼",
            "freelance": "💰",
            "personal": "🏠",
            "learning": "📚",
            "side_project": "🚀",
        }.get(project.type.value, "📁")

        overdue = " ⚠️" if project.is_overdue else ""

        message += f"{type_emoji} <b>{project.name}</b>{overdue}\n"
        message += f"   {bar} {project.progress}%\n\n"

    await update.message.reply_html(message)


# ==================== MESSAGE HANDLER ====================


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler principal de mensajes.

    Delega al sistema de registry para procesar el mensaje con AI.
    """
    from app.core.routing import handle_message_with_registry

    await handle_message_with_registry(update, context)


# ==================== CALLBACK HANDLERS ====================


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler genérico para callbacks de botones inline."""
    query = update.callback_query
    await query.answer()

    data = query.data
    logger.debug(f"Callback recibido: {data}")

    # Parsear callback data
    parts = data.split(":")
    action = parts[0]

    try:
        # Task callbacks
        if action == "task_doing":
            await handle_task_doing_callback(query, context, parts[1] if len(parts) > 1 else None)

        elif action == "task_status":
            task_id = parts[1] if len(parts) > 1 else None
            status = parts[2] if len(parts) > 2 else None
            await handle_task_status_callback(query, context, task_id, status)

        elif action == "task_complete":
            await handle_task_complete_callback(query, context, parts[1] if len(parts) > 1 else None)

        elif action == "task_create_confirm":
            await handle_task_create_confirm(query, context)

        elif action == "task_create_force":
            await handle_task_create_confirm(query, context)

        elif action == "task_create_inbox":
            await handle_task_to_inbox(query, context)

        elif action == "task_view":
            task_id = parts[1] if len(parts) > 1 else None
            await handle_task_view(query, context, task_id)

        elif action in ("task_cancel", "task_action_cancel", "task_delete_cancel"):
            await query.edit_message_text("❌ Operación cancelada.")

        # Project callbacks
        elif action == "project_create_confirm":
            await handle_project_create_confirm(query, context)

        elif action == "project_type":
            project_type = parts[1] if len(parts) > 1 else "personal"
            await handle_project_type_select(query, context, project_type)

        # Manejar formato alternativo: project_type_freelance -> freelance
        elif action.startswith("project_type_"):
            project_type = action.replace("project_type_", "")
            # Mapear nombres en español a inglés
            type_map = {
                "trabajo": "work",
                "freelance": "freelance",
                "estudio": "learning",
                "personal": "personal",
            }
            project_type = type_map.get(project_type, project_type)
            await handle_project_type_select(query, context, project_type)

        elif action == "project_complete":
            await handle_project_complete(query, context, parts[1] if len(parts) > 1 else None)

        elif action in ("project_cancel", "project_update_cancel", "project_delete_cancel"):
            await query.edit_message_text("❌ Operación cancelada.")

        # Reminder callbacks
        elif action == "reminder_time":
            time_option = parts[1] if len(parts) > 1 else "1h"
            await handle_reminder_time(query, context, time_option)

        elif action == "reminder_cancel":
            await query.edit_message_text("❌ Recordatorio cancelado.")

        elif action == "reminder_done":
            reminder_id = int(parts[1]) if len(parts) > 1 else None
            await handle_reminder_done(query, context, reminder_id)

        elif action == "reminder_snooze":
            reminder_id = int(parts[1]) if len(parts) > 1 else None
            minutes = int(parts[2]) if len(parts) > 2 else 30
            await handle_reminder_snooze(query, context, reminder_id, minutes)

        elif action == "reminder_dismiss":
            reminder_id = int(parts[1]) if len(parts) > 1 else None
            await handle_reminder_dismiss(query, context, reminder_id)

        # Plan callbacks
        elif action == "plan_accept":
            await query.edit_message_text(
                query.message.text + "\n\n✅ Plan aceptado!",
                parse_mode="HTML",
            )

        elif action == "plan_adjust":
            await query.edit_message_text(
                "✏️ Dime qué quieres ajustar del plan.",
            )

        # Workload callbacks
        elif action == "workload_check":
            await handle_workload_check(query, context)

        elif action == "show_urgent_tasks":
            await handle_show_urgent_tasks(query, context)

        # Workout callbacks
        elif action == "workout_type":
            workout_type = parts[1] if len(parts) > 1 else "push"
            await handle_workout_type_callback(query, context, workout_type)

        elif action == "workout_cancel":
            context.user_data.pop("pending_workout", None)
            await query.edit_message_text("❌ Registro de workout cancelado.")

        # Nutrition callbacks
        elif action == "nutrition_cat":
            category = parts[1] if len(parts) > 1 else "moderado"
            await handle_nutrition_category_callback(query, context, category)

        elif action == "nutrition_cancel":
            context.user_data.pop("pending_nutrition", None)
            await query.edit_message_text("❌ Registro de comida cancelado.")

        # Default
        else:
            logger.warning(f"Callback no manejado: {data}")
            await query.edit_message_text(
                f"⚠️ Acción no reconocida: {action}"
            )

    except Exception as e:
        logger.error(f"Error en callback {data}: {e}")
        await query.edit_message_text("❌ Error procesando la acción.")


# ==================== CALLBACK IMPLEMENTATIONS ====================


async def handle_task_doing_callback(query, context, task_id: str | None) -> None:
    """Marca una tarea como en progreso."""
    if not task_id:
        await query.edit_message_text("❌ ID de tarea no válido.")
        return

    from app.domain.services import get_task_service
    from app.domain.entities.task import TaskStatus

    service = get_task_service()
    updated = await service.update_status(task_id, TaskStatus.DOING)

    if updated:
        await query.edit_message_text(
            f"⚡ <b>Tarea en progreso</b>\n\n"
            f"<i>{updated.title}</i>",
            parse_mode="HTML",
        )
    else:
        await query.edit_message_text("❌ No se pudo actualizar la tarea.")


async def handle_task_status_callback(query, context, task_id: str | None, status: str | None) -> None:
    """Cambia el estado de una tarea."""
    if not task_id or not status:
        await query.edit_message_text("❌ Parámetros no válidos.")
        return

    from app.domain.services import get_task_service
    from app.domain.entities.task import TaskStatus

    status_map = {
        "doing": TaskStatus.DOING,
        "done": TaskStatus.DONE,
        "paused": TaskStatus.PAUSED,
        "today": TaskStatus.TODAY,
    }

    target_status = status_map.get(status)
    if not target_status:
        await query.edit_message_text(f"❌ Estado no válido: {status}")
        return

    service = get_task_service()
    updated = await service.update_status(task_id, target_status)

    if updated:
        status_names = {
            TaskStatus.DOING: "⚡ En progreso",
            TaskStatus.DONE: "✅ Completada",
            TaskStatus.PAUSED: "⏸️ Pausada",
            TaskStatus.TODAY: "🎯 Hoy",
        }
        await query.edit_message_text(
            f"📋 <b>Tarea actualizada</b>\n\n"
            f"<i>{updated.title}</i>\n"
            f"Estado: {status_names.get(target_status, status)}",
            parse_mode="HTML",
        )
    else:
        await query.edit_message_text("❌ No se pudo actualizar la tarea.")


async def handle_task_complete_callback(query, context, task_id: str | None) -> None:
    """Completa una tarea."""
    if not task_id:
        await query.edit_message_text("❌ ID de tarea no válido.")
        return

    from app.domain.services import get_task_service

    service = get_task_service()
    completed = await service.complete(task_id)

    if completed:
        await query.edit_message_text(
            f"✅ <b>Tarea completada</b>\n\n"
            f"<i>{completed.title}</i>\n\n"
            f"¡Buen trabajo! 🎉",
            parse_mode="HTML",
        )
    else:
        await query.edit_message_text("❌ No se pudo completar la tarea.")


async def handle_task_create_confirm(query, context) -> None:
    """Confirma la creación de una tarea con datos enriquecidos."""
    import re
    from datetime import date

    pending = context.user_data.get("pending_task", {})
    title = pending.get("title", "")
    priority_str = pending.get("priority", "normal")

    # Si no hay pending en context, intentar extraer del mensaje original
    if not title and query.message and query.message.text:
        msg_text = query.message.text

        # Extraer prioridad del mensaje si existe (verificar antes de extraer título)
        extracted_priority = "normal"
        if "🔥" in msg_text:
            extracted_priority = "urgent"
        elif "⚡" in msg_text and ("Alta" in msg_text or "alta" in msg_text):
            extracted_priority = "high"
        elif "🧊" in msg_text:
            extracted_priority = "low"

        # El mensaje tiene varios formatos posibles:
        # 1. "📋 Nueva tarea detectada\n\n<título>\n🔥 Prioridad: Urgente\n\nConfianza..."
        # 2. "📋 Nueva tarea detectada\n\n<título>\n\nConfianza..."
        # 3. "⚠️ Posible duplicado...\nNueva: <título> 🔥\n\nSimilar..."
        # 4. "⚠️ Posible duplicado...\nNueva: <título>\n\nSimilar..."

        # Para duplicado: extraer después de "Nueva:" hasta emoji o newline con "Similar"
        match = re.search(r"Nueva:\s*(.+?)(?:\s*[🔥⚡🧊]|\n\nSimilar)", msg_text, re.DOTALL)
        if match:
            title = match.group(1).strip()
        else:
            # Para normal: después de "Nueva tarea detectada" hasta prioridad o confianza
            match = re.search(r"Nueva tarea detectada.*?\n\n(.+?)(?:\n🔥|\n⚡|\n🧊|\n\nConfianza)", msg_text, re.DOTALL)
            if match:
                title = match.group(1).strip()

        if title:
            # Limpiar emojis del título si los tiene al final
            title = re.sub(r"\s*[🔥⚡🧊]\s*$", "", title).strip()

            # Guardar para uso posterior
            context.user_data["pending_task"] = {"title": title, "priority": extracted_priority}
            priority_str = extracted_priority

    if not title:
        await query.edit_message_text("❌ No hay tarea pendiente.")
        return

    from app.domain.services import get_task_service
    from app.domain.entities.task import Task, TaskStatus, TaskPriority, TaskComplexity, TaskEnergy, TaskTimeBlock

    # Mapear prioridad
    priority_map = {
        "urgente": TaskPriority.URGENT,
        "urgent": TaskPriority.URGENT,
        "alta": TaskPriority.HIGH,
        "high": TaskPriority.HIGH,
        "normal": TaskPriority.NORMAL,
        "baja": TaskPriority.LOW,
        "low": TaskPriority.LOW,
    }
    priority = priority_map.get(priority_str.lower(), TaskPriority.NORMAL)

    # Extraer datos enriquecidos del pending_task
    complexity_data = pending.get("complexity", {})
    complexity = None
    energy = None
    time_block = None
    estimated_minutes = None
    notes = None
    scheduled_date = None
    due_date = None
    task_context = pending.get("context")

    # Mapear complejidad
    if complexity_data:
        complexity_str = complexity_data.get("level", "").lower()
        complexity_map = {
            "quick": TaskComplexity.QUICK,
            "standard": TaskComplexity.STANDARD,
            "heavy": TaskComplexity.HEAVY,
            "epic": TaskComplexity.EPIC,
        }
        complexity = complexity_map.get(complexity_str)

        # Extraer energía
        energy_str = complexity_data.get("energy", "").lower()
        energy_map = {
            "deep_work": TaskEnergy.DEEP_WORK,
            "deep work": TaskEnergy.DEEP_WORK,
            "alta": TaskEnergy.DEEP_WORK,
            "medium": TaskEnergy.MEDIUM,
            "media": TaskEnergy.MEDIUM,
            "low": TaskEnergy.LOW,
            "baja": TaskEnergy.LOW,
        }
        energy = energy_map.get(energy_str)

        # Extraer tiempo estimado
        est_minutes = complexity_data.get("estimated_minutes")
        if est_minutes:
            estimated_minutes = int(est_minutes)

        # Extraer bloque de tiempo
        block_str = complexity_data.get("best_time_block", "").lower()
        block_map = {
            "morning": TaskTimeBlock.MORNING,
            "mañana": TaskTimeBlock.MORNING,
            "afternoon": TaskTimeBlock.AFTERNOON,
            "tarde": TaskTimeBlock.AFTERNOON,
            "evening": TaskTimeBlock.EVENING,
            "noche": TaskTimeBlock.EVENING,
        }
        time_block = block_map.get(block_str)

        # Extraer notas/reasoning
        reasoning = complexity_data.get("reasoning")
        if reasoning:
            notes = reasoning

    # Extraer fechas
    fecha_do = pending.get("fecha_do")
    fecha_due = pending.get("due_date")

    if fecha_do:
        try:
            scheduled_date = date.fromisoformat(fecha_do)
        except (ValueError, TypeError):
            pass

    if fecha_due:
        try:
            due_date = date.fromisoformat(fecha_due)
        except (ValueError, TypeError):
            pass

    # Extraer proyecto relacionado del enriquecimiento
    project_match = pending.get("project_match")
    project_id = None
    project_name = None

    if project_match:
        # Si ya tenemos el ID del proyecto, usarlo directamente
        project_id = project_match.get("id")
        project_name = project_match.get("name")

        # Si solo tenemos el nombre, buscar el ID
        if not project_id and project_name:
            from app.domain.repositories import get_project_repository
            project_repo = get_project_repository()
            project = await project_repo.find_by_name(project_name)
            if project:
                project_id = project.id
                project_name = project.name

    # Crear tarea con todos los datos enriquecidos
    service = get_task_service()
    new_task = Task(
        id="",
        title=title,
        status=TaskStatus.TODAY,
        priority=priority,
        complexity=complexity,
        energy=energy,
        time_block=time_block,
        estimated_minutes=estimated_minutes,
        notes=notes,
        scheduled_date=scheduled_date,
        due_date=due_date,
        context=task_context,
        source="telegram",
        project_id=project_id,
        project_name=project_name,
    )
    created, _ = await service.create(new_task, check_duplicates=False)

    # Limpiar pending
    context.user_data.pop("pending_task", None)

    # Construir mensaje de confirmación con detalles
    msg_parts = [
        f"✅ <b>Tarea creada</b>",
        f"",
        f"<i>{created.title}</i>",
        f"",
        f"📊 Estado: 🎯 Hoy",
    ]

    priority_emoji = {
        TaskPriority.URGENT: "🔥 Urgente",
        TaskPriority.HIGH: "⚡ Alta",
        TaskPriority.NORMAL: "🔄 Normal",
        TaskPriority.LOW: "🧊 Baja",
    }.get(priority, "🔄 Normal")
    msg_parts.append(f"⭐ Prioridad: {priority_emoji}")

    if complexity:
        complexity_names = {
            TaskComplexity.QUICK: "🟢 Quick (<30m)",
            TaskComplexity.STANDARD: "🟡 Standard (30m-2h)",
            TaskComplexity.HEAVY: "🔴 Heavy (2-4h)",
            TaskComplexity.EPIC: "🟣 Epic (4h+)",
        }
        msg_parts.append(f"📐 Complejidad: {complexity_names.get(complexity, complexity.value)}")

    if energy:
        energy_names = {
            TaskEnergy.DEEP_WORK: "🧠 Deep Work",
            TaskEnergy.MEDIUM: "💪 Medium",
            TaskEnergy.LOW: "😴 Low",
        }
        msg_parts.append(f"⚡ Energía: {energy_names.get(energy, energy.value)}")

    if time_block:
        block_names = {
            TaskTimeBlock.MORNING: "🌅 Morning",
            TaskTimeBlock.AFTERNOON: "☀️ Afternoon",
            TaskTimeBlock.EVENING: "🌆 Evening",
        }
        msg_parts.append(f"🕐 Bloque: {block_names.get(time_block, time_block.value)}")

    if estimated_minutes:
        hours = estimated_minutes // 60
        mins = estimated_minutes % 60
        time_str = f"{hours}h {mins}m" if hours else f"{mins}m"
        msg_parts.append(f"⏱️ Tiempo est: {time_str}")

    if project_name:
        msg_parts.append(f"📁 Proyecto: {project_name}")

    await query.edit_message_text(
        "\n".join(msg_parts),
        parse_mode="HTML",
    )


async def handle_task_view(query, context, task_id: str | None) -> None:
    """Muestra detalles de una tarea existente."""
    if not task_id:
        await query.edit_message_text("❌ ID de tarea no válido.")
        return

    from app.domain.services import get_task_service

    service = get_task_service()

    try:
        task = await service.get_by_id(task_id)

        if not task:
            await query.edit_message_text("❌ Tarea no encontrada.")
            return

        status_names = {
            "backlog": "📥 Backlog",
            "planned": "📋 Planificada",
            "today": "🎯 Hoy",
            "doing": "⚡ En Progreso",
            "paused": "⏸️ Pausada",
            "done": "✅ Completada",
            "cancelled": "❌ Cancelada",
        }

        priority_names = {
            "urgent": "🔥 Urgente",
            "high": "⚡ Alta",
            "normal": "🔄 Normal",
            "low": "🧊 Baja",
        }

        status_str = status_names.get(task.status.value, task.status.value)
        priority_str = priority_names.get(task.priority.value, task.priority.value) if task.priority else "Sin prioridad"

        message = (
            f"<b>{task.title}</b>\n\n"
            f"Estado: {status_str}\n"
            f"Prioridad: {priority_str}"
        )

        if task.due_date:
            message += f"\n📅 Vence: {task.due_date.strftime('%d/%m/%Y')}"

        await query.edit_message_text(message, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error viendo tarea: {e}")
        await query.edit_message_text("❌ Error al cargar la tarea.")


async def handle_task_to_inbox(query, context) -> None:
    """Guarda una tarea en el inbox."""
    pending = context.user_data.get("pending_task", {})
    title = pending.get("title", "")

    if not title:
        await query.edit_message_text("❌ No hay tarea pendiente.")
        return

    from app.services.notion import get_notion_service, InboxFuente

    notion = get_notion_service()
    await notion.create_inbox_item(
        contenido=title,
        fuente=InboxFuente.TELEGRAM,
        notas="Guardado desde botón de crear tarea",
    )

    context.user_data.pop("pending_task", None)

    await query.edit_message_text(
        f"📥 <b>Guardado en Inbox</b>\n\n"
        f"<i>{title}</i>",
        parse_mode="HTML",
    )


async def handle_project_create_confirm(query, context) -> None:
    """Confirma la creación de un proyecto."""
    pending = context.user_data.get("pending_project", {})
    name = pending.get("name", "")
    type_str = pending.get("type", "personal")

    if not name:
        await query.edit_message_text("❌ No hay proyecto pendiente.")
        return

    from app.domain.services import get_project_service
    from app.domain.entities.project import Project, ProjectType

    type_map = {
        "work": ProjectType.WORK,
        "freelance": ProjectType.FREELANCE,
        "personal": ProjectType.PERSONAL,
        "learning": ProjectType.LEARNING,
        "side_project": ProjectType.SIDE_PROJECT,
    }

    service = get_project_service()
    new_project = Project(
        id="",
        name=name,
        type=type_map.get(type_str, ProjectType.PERSONAL),
    )
    created = await service.create(new_project)

    context.user_data.pop("pending_project", None)

    await query.edit_message_text(
        f"✅ <b>Proyecto creado</b>\n\n"
        f"<i>{created.name}</i>",
        parse_mode="HTML",
    )


async def handle_project_type_select(query, context, project_type: str) -> None:
    """Maneja la selección de tipo de proyecto."""
    pending = context.user_data.get("pending_project", {})
    pending["type"] = project_type
    context.user_data["pending_project"] = pending

    # Crear el proyecto
    await handle_project_create_confirm(query, context)


async def handle_project_complete(query, context, project_id: str | None) -> None:
    """Completa un proyecto."""
    if not project_id:
        await query.edit_message_text("❌ ID de proyecto no válido.")
        return

    from app.domain.services import get_project_service

    service = get_project_service()
    completed = await service.complete(project_id)

    if completed:
        await query.edit_message_text(
            f"🏁 <b>Proyecto completado</b>\n\n"
            f"<i>{completed.name}</i>\n\n"
            f"¡Felicidades! 🎉",
            parse_mode="HTML",
        )
    else:
        await query.edit_message_text("❌ No se pudo completar el proyecto.")


async def handle_reminder_time(query, context, time_option: str) -> None:
    """Maneja la selección de tiempo para recordatorio."""
    from datetime import datetime, timedelta
    import re
    from app.services.reminder_service import get_reminder_service

    pending = context.user_data.get("pending_reminder", {})
    text = pending.get("text", "")

    # Si no hay pending en context, intentar extraer del mensaje original
    if not text and query.message and query.message.text:
        # El mensaje tiene formato: "⏰ Crear Recordatorio\n\n<texto>\n\n¿Cuándo..."
        match = re.search(r"Crear Recordatorio\n\n(.+?)\n\n¿Cuándo", query.message.text, re.DOTALL)
        if match:
            text = match.group(1).strip()
            # Guardar para uso posterior
            context.user_data["pending_reminder"] = {"text": text}

    if not text:
        await query.edit_message_text("❌ No hay recordatorio pendiente.")
        return

    # Manejar opción "custom" - pedir hora específica
    if time_option == "custom":
        context.user_data["awaiting_reminder_time"] = True
        await query.edit_message_text(
            f"⏰ <b>Recordatorio personalizado</b>\n\n"
            f"<i>{text}</i>\n\n"
            f"Escribe cuándo quieres que te recuerde:\n"
            f"• \"en 2 horas\"\n"
            f"• \"mañana a las 10\"\n"
            f"• \"el viernes a las 3pm\"",
            parse_mode="HTML",
        )
        return

    # Calcular fecha/hora según opción
    now = datetime.now()
    time_deltas = {
        "30m": timedelta(minutes=30),
        "1h": timedelta(hours=1),
        "3h": timedelta(hours=3),
        "tomorrow": timedelta(days=1),
    }

    if time_option == "tomorrow":
        scheduled_at = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0)
    else:
        scheduled_at = now + time_deltas.get(time_option, timedelta(hours=1))

    time_labels = {
        "30m": "30 minutos",
        "1h": "1 hora",
        "3h": "3 horas",
        "tomorrow": "mañana a las 9 AM",
    }

    # Crear recordatorio real
    try:
        chat_id = str(query.message.chat_id)
        user_id = str(query.from_user.id)
        service = get_reminder_service()

        reminder = await service.create_reminder(
            chat_id=chat_id,
            user_id=user_id,
            title=text,
            scheduled_at=scheduled_at,
        )

        time_str = scheduled_at.strftime("%H:%M del %d/%m")
        await query.edit_message_text(
            f"✅ <b>Recordatorio creado</b>\n\n"
            f"<i>{text}</i>\n\n"
            f"⏰ Te recordaré: {time_str}",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Error creando recordatorio: {e}")
        await query.edit_message_text(
            f"⏰ <b>Recordatorio programado</b>\n\n"
            f"<i>{text}</i>\n\n"
            f"Te recordaré en {time_labels.get(time_option, time_option)}",
            parse_mode="HTML",
        )

    context.user_data.pop("pending_reminder", None)
    context.user_data.pop("awaiting_reminder_time", None)


async def handle_workload_check(query, context) -> None:
    """Muestra resumen de carga de trabajo."""
    from app.domain.services import get_task_service

    service = get_task_service()
    summary = await service.get_workload_summary()

    total = summary.get("total_pending", 0)
    overdue = summary.get("overdue", 0)
    prio = summary.get("by_priority", {})

    message = "📊 <b>Tu carga de trabajo</b>\n\n"
    message += f"📋 <b>Total pendiente:</b> {total}\n"

    if overdue > 0:
        message += f"⚠️ <b>Vencidas:</b> {overdue}\n"

    message += f"\n<b>Por prioridad:</b>\n"
    message += f"🔥 Urgente: {prio.get('urgent', 0)}\n"
    message += f"⚡ Alta: {prio.get('high', 0)}\n"
    message += f"📌 Normal: {prio.get('normal', 0)}\n"

    await query.edit_message_text(message, parse_mode="HTML")


async def handle_show_urgent_tasks(query, context) -> None:
    """Muestra tareas urgentes."""
    from app.domain.services import get_task_service
    from app.domain.entities.task import TaskPriority

    service = get_task_service()
    tasks = await service.get_by_priority(TaskPriority.URGENT)

    if not tasks:
        await query.edit_message_text("🔥 No hay tareas urgentes. ¡Bien!")
        return

    message = "🔥 <b>Tareas Urgentes</b>\n\n"
    for task in tasks[:10]:
        overdue = " ⚠️" if task.is_overdue else ""
        message += f"• {task.title}{overdue}\n"

    await query.edit_message_text(message, parse_mode="HTML")


async def handle_reminder_done(query, context, reminder_id: int | None) -> None:
    """Marca un recordatorio como completado."""
    if not reminder_id:
        await query.edit_message_text("❌ ID de recordatorio no válido.")
        return

    from app.services.reminder_service import get_reminder_service

    service = get_reminder_service()
    success = await service.mark_completed(reminder_id)

    if success:
        await query.edit_message_text(
            "✅ <b>Recordatorio completado</b>\n\n¡Buen trabajo!",
            parse_mode="HTML",
        )
    else:
        await query.edit_message_text("❌ No se pudo completar el recordatorio.")


async def handle_reminder_snooze(query, context, reminder_id: int | None, minutes: int) -> None:
    """Pospone un recordatorio."""
    if not reminder_id:
        await query.edit_message_text("❌ ID de recordatorio no válido.")
        return

    from app.services.reminder_service import get_reminder_service

    service = get_reminder_service()
    success = await service.snooze_reminder(reminder_id, minutes)

    if success:
        if minutes >= 60:
            time_str = f"{minutes // 60} hora{'s' if minutes >= 120 else ''}"
        else:
            time_str = f"{minutes} minutos"

        await query.edit_message_text(
            f"⏰ <b>Recordatorio pospuesto</b>\n\nTe recordaré en {time_str}",
            parse_mode="HTML",
        )
    else:
        await query.edit_message_text("❌ No se pudo posponer el recordatorio.")


async def handle_reminder_dismiss(query, context, reminder_id: int | None) -> None:
    """Descarta un recordatorio."""
    if not reminder_id:
        await query.edit_message_text("❌ ID de recordatorio no válido.")
        return

    from app.services.reminder_service import get_reminder_service

    service = get_reminder_service()
    success = await service.cancel_reminder(reminder_id)

    if success:
        await query.edit_message_text(
            "❌ <b>Recordatorio descartado</b>",
            parse_mode="HTML",
        )
    else:
        await query.edit_message_text("❌ No se pudo descartar el recordatorio.")


# ==================== WORKOUT CALLBACKS ====================


async def handle_workout_type_callback(query, context, workout_type: str) -> None:
    """Registra un workout con el tipo seleccionado."""
    from datetime import date
    from app.agents.workout_logger import WorkoutLoggerAgent, WorkoutType

    pending = context.user_data.get("pending_workout", "")
    if not pending:
        await query.edit_message_text("❌ No hay workout pendiente.")
        return

    # Mapear tipo
    type_map = {
        "push": WorkoutType.PUSH,
        "pull": WorkoutType.PULL,
        "legs": WorkoutType.LEGS,
        "cardio": WorkoutType.CARDIO,
    }
    wtype = type_map.get(workout_type.lower(), WorkoutType.PUSH)

    await query.edit_message_text(
        f"🏋️ <b>Registrando {wtype.value}...</b>\n\n⏳ Analizando ejercicios...",
        parse_mode="HTML",
    )

    try:
        # Usar WorkoutLogger para analizar
        logger_agent = WorkoutLoggerAgent()
        result = await logger_agent.log_workout(
            workout_description=pending,
            workout_type=wtype,
        )

        # Guardar en Notion
        notion = get_notion_service()
        fecha_hoy = date.today().strftime("%Y-%m-%d")

        # Convertir ejercicios a JSON para Notion
        ejercicios_json = logger_agent.to_notion_json(result.exercises)

        # Guardar en Notion
        await notion.log_workout(
            fecha=fecha_hoy,
            tipo=wtype.value,
            ejercicios=ejercicios_json,
            prs=", ".join(result.new_prs) if result.new_prs else None,
            notas=result.feedback,
        )

        # Formatear respuesta
        message = logger_agent.format_telegram_message(result)

        await query.edit_message_text(
            message,
            parse_mode="HTML",
        )

        # Limpiar pending
        context.user_data.pop("pending_workout", None)

    except Exception as e:
        logger.error(f"Error registrando workout: {e}")
        await query.edit_message_text(
            f"❌ Error registrando workout: {str(e)[:100]}"
        )


async def handle_nutrition_category_callback(query, context, category: str) -> None:
    """Registra una comida con la categoría seleccionada manualmente."""
    from datetime import date
    from app.services.notion import NutritionCategoria

    pending = context.user_data.get("pending_nutrition", {})
    if not pending:
        await query.edit_message_text("❌ No hay comida pendiente.")
        return

    meal = pending.get("meal", "comida")
    food = pending.get("food", "")

    # Mapear categoría
    cat_map = {
        "saludable": NutritionCategoria.SALUDABLE,
        "moderado": NutritionCategoria.MODERADO,
        "pesado": NutritionCategoria.PESADO,
    }
    cat = cat_map.get(category.lower(), NutritionCategoria.MODERADO)

    # Estimar calorías basadas en categoría
    cal_estimates = {
        NutritionCategoria.SALUDABLE: 400,
        NutritionCategoria.MODERADO: 600,
        NutritionCategoria.PESADO: 900,
    }
    calories = cal_estimates.get(cat, 500)

    try:
        # Guardar en Notion
        notion = get_notion_service()
        fecha_hoy = date.today().isoformat()

        # Mapear tipo de comida a parámetros correctos
        meal_lower = meal.lower()
        nutrition_params = {"fecha": fecha_hoy}

        if "desayuno" in meal_lower or "breakfast" in meal_lower:
            nutrition_params["desayuno"] = food
            nutrition_params["desayuno_cal"] = calories
            nutrition_params["desayuno_cat"] = cat
        elif "almuerzo" in meal_lower or "comida" in meal_lower or "lunch" in meal_lower:
            nutrition_params["comida"] = food
            nutrition_params["comida_cal"] = calories
            nutrition_params["comida_cat"] = cat
        elif "cena" in meal_lower or "dinner" in meal_lower:
            nutrition_params["cena"] = food
            nutrition_params["cena_cal"] = calories
            nutrition_params["cena_cat"] = cat
        else:
            nutrition_params["snacks"] = food
            nutrition_params["snacks_cal"] = calories

        await notion.log_nutrition(**nutrition_params)

        cat_emoji = {
            NutritionCategoria.SALUDABLE: "🟢",
            NutritionCategoria.MODERADO: "🟡",
            NutritionCategoria.PESADO: "🔴",
        }.get(cat, "🟡")

        await query.edit_message_text(
            f"✅ <b>{meal.capitalize()} registrada</b>\n\n"
            f"{cat_emoji} Categoría: {cat.value}\n"
            f"🔥 Calorías estimadas: ~{calories}",
            parse_mode="HTML",
        )

        # Limpiar pending
        context.user_data.pop("pending_nutrition", None)

    except Exception as e:
        logger.error(f"Error registrando nutrición: {e}")
        await query.edit_message_text(
            f"❌ Error registrando comida: {str(e)[:100]}"
        )


# ==================== APPLICATION SETUP ====================


def setup_handlers(application: Application) -> None:
    """Configura todos los handlers de la aplicación."""
    global _application, _initialized

    if _initialized:
        logger.warning("Handlers ya inicializados")
        return

    _application = application

    # Comandos básicos
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("done", done_command))
    application.add_handler(CommandHandler("doing", doing_command))
    application.add_handler(CommandHandler("projects", projects_command))

    # Conversation handlers
    application.add_handler(get_inbox_conversation_handler())
    application.add_handler(get_deepwork_conversation_handler())
    application.add_handler(get_purchase_conversation_handler())
    application.add_handler(get_gym_conversation_handler())
    application.add_handler(get_nutrition_conversation_handler())

    # Callback handler para botones inline
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Handler principal de mensajes (última prioridad)
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    _initialized = True
    logger.info("Handlers configurados correctamente")


def get_application() -> Application | None:
    """Obtiene la instancia de la aplicación."""
    return _application
