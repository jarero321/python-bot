"""Handlers del bot de Telegram."""

import logging
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.bot.keyboards import (
    main_menu_keyboard,
    task_actions_keyboard,
    task_priority_keyboard,
    confirm_keyboard,
)
from app.bot.conversations import (
    get_inbox_conversation_handler,
    get_deepwork_conversation_handler,
    get_purchase_conversation_handler,
    get_gym_conversation_handler,
    get_nutrition_conversation_handler,
)
from app.config import get_settings
from app.services.notion import get_notion_service, TaskEstado

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
        "Puedes enviarme mensajes y los procesaré automáticamente.\n\n"
        "<b>Comandos de Tareas:</b>\n"
        "/today - Ver tareas para hoy\n"
        "/add [tarea] - Agregar tarea rápida\n"
        "/doing [tarea] - Marcar en progreso\n"
        "/done - Completar tarea actual\n"
        "/block [razón] - Marcar como bloqueada\n\n"
        "<b>Otros:</b>\n"
        "/status - Estado del sistema\n"
        "/inbox - Ver inbox pendiente\n"
        "/projects - Listar proyectos\n\n"
        "<b>Tips:</b>\n"
        "• Envía cualquier texto para capturarlo en el inbox\n"
        "• Menciona un precio ($) para análisis de compra\n"
        "• Di 'gym' para registrar tu workout"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /status."""
    notion = get_notion_service()

    # Test conexión Notion
    notion_status = "✅ Conectado" if await notion.test_connection() else "❌ Error"

    await update.message.reply_html(
        "<b>Estado del Sistema</b>\n\n"
        f"<b>Entorno:</b> {settings.app_env}\n"
        f"<b>Bot:</b> ✅ Online\n"
        f"<b>Notion:</b> {notion_status}\n"
        f"<b>Hora:</b> {datetime.now().strftime('%H:%M:%S')}"
    )


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /today - muestra tareas de hoy."""
    await update.message.reply_text("Obteniendo tareas de hoy...")

    notion = get_notion_service()
    tasks = await notion.get_tasks_for_today()

    if not tasks:
        await update.message.reply_html(
            "📋 <b>Tareas de hoy</b>\n\n"
            "No hay tareas programadas para hoy.\n\n"
            "Usa /add [tarea] para agregar una."
        )
        return

    # Formatear tareas
    message = "📋 <b>Tareas de hoy</b>\n\n"
    for i, task in enumerate(tasks, 1):
        props = task.get("properties", {})
        # Campo correcto: "Tarea" (Title)
        title_prop = props.get("Tarea", {}).get("title", [])
        task_name = title_prop[0].get("text", {}).get("content", "Sin título") if title_prop else "Sin título"

        # Campo correcto: "Estado" (Select)
        estado_prop = props.get("Estado", {}).get("select", {})
        estado = estado_prop.get("name", "?") if estado_prop else "?"

        # Campo correcto: "Prioridad" (Select)
        prioridad_prop = props.get("Prioridad", {}).get("select", {})
        prioridad = prioridad_prop.get("name", "") if prioridad_prop else ""

        # Emojis según estado
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

    await update.message.reply_html(message)


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /add - agrega una tarea rápida."""
    if not context.args:
        await update.message.reply_html(
            "Uso: /add [descripción de la tarea]\n\n"
            "Ejemplo: /add Revisar emails"
        )
        return

    task_title = " ".join(context.args)
    await update.message.reply_text(f"Creando tarea: {task_title}...")

    notion = get_notion_service()
    result = await notion.create_task(
        tarea=task_title,
        estado=TaskEstado.BACKLOG,
    )

    if result:
        task_id = result.get("id", "")
        await update.message.reply_html(
            f"✅ Tarea creada: <b>{task_title}</b>\n\n"
            "¿Qué prioridad tiene?",
            reply_markup=task_priority_keyboard(task_id[:8]),
        )
    else:
        await update.message.reply_text(
            "❌ Error creando la tarea. Intenta de nuevo."
        )


async def doing_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /doing - marca tarea en progreso."""
    if context.args:
        # Si se especifica una tarea, buscarla
        task_name = " ".join(context.args)
        await update.message.reply_text(
            f"Buscando tarea: {task_name}...\n"
            "(Funcionalidad de búsqueda próximamente)"
        )
    else:
        # Mostrar tareas pendientes para seleccionar
        notion = get_notion_service()
        tasks = await notion.get_pending_tasks(limit=5)

        if not tasks:
            await update.message.reply_text(
                "No hay tareas pendientes. Usa /add para crear una."
            )
            return

        message = "Selecciona la tarea que vas a empezar:\n\n"
        for i, task in enumerate(tasks, 1):
            props = task.get("properties", {})
            title_prop = props.get("Tarea", {}).get("title", [])
            task_name = title_prop[0].get("text", {}).get("content", "Sin título") if title_prop else "Sin título"
            message += f"{i}. {task_name}\n"

        await update.message.reply_text(message)


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /done - completa la tarea actual."""
    # Por ahora, mostrar mensaje básico
    await update.message.reply_html(
        "✅ <b>Marcar como completada</b>\n\n"
        "(En desarrollo: se mostrará la tarea en progreso actual)"
    )


async def block_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /block - marca tarea como bloqueada."""
    reason = " ".join(context.args) if context.args else None

    message = "🚫 <b>Marcar como bloqueada</b>\n\n"
    if reason:
        message += f"Razón: {reason}\n\n"
    message += "(En desarrollo: se mostrará la tarea en progreso actual)"

    await update.message.reply_html(message)


async def inbox_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /inbox - muestra items del inbox."""
    notion = get_notion_service()
    items = await notion.get_inbox_items(limit=10)

    if not items:
        await update.message.reply_html(
            "📥 <b>Inbox</b>\n\n"
            "Tu inbox está vacío."
        )
        return

    message = "📥 <b>Inbox</b>\n\n"
    for item in items:
        props = item.get("properties", {})
        # Campo correcto: "Contenido" (Title)
        title_prop = props.get("Contenido", {}).get("title", [])
        item_name = title_prop[0].get("text", {}).get("content", "Sin título") if title_prop else "Sin título"
        message += f"• {item_name}\n"

    await update.message.reply_html(message)


async def projects_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /projects - lista proyectos."""
    notion = get_notion_service()
    projects = await notion.get_projects(active_only=True)

    if not projects:
        await update.message.reply_html(
            "📁 <b>Proyectos</b>\n\n"
            "No hay proyectos activos."
        )
        return

    message = "📁 <b>Proyectos Activos</b>\n\n"
    for project in projects:
        props = project.get("properties", {})
        # Campo correcto: "Proyecto" (Title)
        title_prop = props.get("Proyecto", {}).get("title", [])
        project_name = title_prop[0].get("text", {}).get("content", "Sin título") if title_prop else "Sin título"
        message += f"• {project_name}\n"

    await update.message.reply_html(message)


# ==================== MESSAGE HANDLERS ====================


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para mensajes de texto."""
    text = update.message.text
    user = update.effective_user
    chat_id = update.effective_chat.id

    logger.info(f"Mensaje de {user.id}: {text[:50]}...")

    # Detectar intención básica
    text_lower = text.lower()

    # Detectar mención de precio (compra)
    if "$" in text or "pesos" in text_lower:
        await update.message.reply_html(
            f"💰 Detecté una mención de precio.\n\n"
            f"<i>{text}</i>\n\n"
            "(Análisis de compra con SpendingAnalyzer próximamente)"
        )
        return

    # Detectar gym
    if "gym" in text_lower or "entreno" in text_lower or "workout" in text_lower:
        await update.message.reply_html(
            f"💪 ¿Registrar workout?\n\n"
            f"<i>{text}</i>\n\n"
            "(Registro de gym próximamente)"
        )
        return

    # Por defecto, guardar en inbox
    from app.services.notion import InboxFuente
    notion = get_notion_service()
    result = await notion.create_inbox_item(
        contenido=text[:200],
        fuente=InboxFuente.TELEGRAM,
        notas=text[200:] if len(text) > 200 else None,
    )

    if result:
        await update.message.reply_html(
            f"📥 Guardado en Inbox:\n\n"
            f"<i>{text[:100]}{'...' if len(text) > 100 else ''}</i>\n\n"
            "(Clasificación automática próximamente)",
            reply_markup=confirm_keyboard(
                confirm_data="inbox_classify",
                cancel_data="inbox_done",
            ),
        )
    else:
        await update.message.reply_text(
            "❌ Error guardando en inbox. Intenta de nuevo."
        )


# ==================== CALLBACK HANDLERS ====================


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para callbacks de botones inline."""
    query = update.callback_query
    await query.answer()

    data = query.data
    logger.debug(f"Callback recibido: {data}")

    # Parsear callback data
    parts = data.split(":")
    action = parts[0]

    if action == "menu_today":
        # Redirigir a /today
        await query.message.reply_text("Obteniendo tareas de hoy...")
        notion = get_notion_service()
        tasks = await notion.get_tasks_for_today()
        # ... (mismo código que today_command)
        await query.message.reply_text(
            f"Encontradas {len(tasks)} tareas para hoy."
        )

    elif action == "menu_add":
        await query.message.reply_text(
            "Usa /add [tarea] para agregar una tarea.\n\n"
            "Ejemplo: /add Revisar emails"
        )

    elif action.startswith("priority_"):
        priority = action.split("_")[1]
        task_id = parts[1] if len(parts) > 1 else None
        priority_map = {"high": "High", "medium": "Medium", "low": "Low"}

        await query.edit_message_text(
            f"✅ Prioridad establecida: {priority_map.get(priority, priority)}"
        )

    elif action == "inbox_classify":
        await query.edit_message_text(
            "📋 Clasificando...\n\n"
            "(InboxProcessor Agent próximamente)"
        )

    elif action == "inbox_done":
        await query.edit_message_text("✅ Guardado en inbox.")

    elif action.startswith("confirm"):
        await query.edit_message_text("✅ Confirmado")

    elif action.startswith("cancel"):
        await query.edit_message_text("❌ Cancelado")

    else:
        await query.edit_message_text(f"Acción no implementada: {action}")


# ==================== APPLICATION SETUP ====================


def create_application() -> Application:
    """Crea y configura la aplicación de Telegram."""
    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .build()
    )

    # Command handlers básicos
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("doing", doing_command))
    application.add_handler(CommandHandler("done", done_command))
    application.add_handler(CommandHandler("block", block_command))
    application.add_handler(CommandHandler("inbox", inbox_command))
    application.add_handler(CommandHandler("projects", projects_command))

    # Conversation handlers (flujos conversacionales)
    # Orden importante: los más específicos primero

    # 1. Deep Work (/deepwork, /focus)
    application.add_handler(get_deepwork_conversation_handler())

    # 2. Gym (/gym, /workout)
    application.add_handler(get_gym_conversation_handler())

    # 3. Nutrición (/food, /nutrition, /comida)
    application.add_handler(get_nutrition_conversation_handler())

    # 4. Análisis de compras (detecta $precio o "pesos")
    application.add_handler(get_purchase_conversation_handler())

    # 5. Captura rápida (cualquier otro mensaje)
    application.add_handler(get_inbox_conversation_handler())

    # Callback handler para botones no manejados por conversaciones
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Message handler fallback (solo si no fue capturado por conversaciones)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    return application


async def get_application() -> Application:
    """Obtiene la instancia de la aplicación inicializada."""
    global _application, _initialized

    if _application is None:
        _application = create_application()

    if not _initialized:
        await _application.initialize()
        _initialized = True

    return _application
