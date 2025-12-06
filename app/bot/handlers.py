"""
Bot Handlers - Simplificados usando el Brain.

Todos los mensajes van al Brain, que decide que hacer.
Los handlers solo son wrappers que pasan mensajes al Brain.
"""

import asyncio
import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.brain import get_brain
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Configuración de seguridad
MAX_MESSAGE_LENGTH = 2000
BRAIN_TIMEOUT_SECONDS = 30

# Application singleton
_application: Application | None = None


# ==================== HELPER FUNCTIONS ====================


def _build_keyboard(keyboard_data: list[list[dict]] | None) -> InlineKeyboardMarkup | None:
    """Convierte keyboard data del Brain a InlineKeyboardMarkup."""
    if not keyboard_data:
        return None

    buttons = [
        [
            InlineKeyboardButton(
                text=btn.get("text", ""),
                callback_data=btn.get("callback_data", "")
            )
            for btn in row
        ]
        for row in keyboard_data
    ]

    return InlineKeyboardMarkup(buttons)


def _sanitize_input(text: str) -> str:
    """
    Sanitiza el input del usuario para prevenir prompt injection.

    - Limita longitud
    - Elimina caracteres de control
    - Detecta y marca patrones sospechosos
    """
    # Limitar longitud
    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[:MAX_MESSAGE_LENGTH] + "..."

    # Eliminar caracteres de control (excepto newlines)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    return text.strip()


def _detect_suspicious_patterns(text: str) -> bool:
    """Detecta patrones sospechosos de prompt injection."""
    suspicious_patterns = [
        r'ignor[ae]\s+(las\s+)?instrucciones',
        r'olvida\s+(lo|todo)\s+anterior',
        r'system\s*prompt',
        r'actua\s+como\s+(si\s+fueras|otro)',
        r'pretende\s+que\s+eres',
        r'modo\s+(desarrollador|admin|debug)',
        r'sin\s+restricciones',
        r'jailbreak',
        r'DAN\s+mode',
        r'bypass\s+(security|filter)',
    ]

    text_lower = text.lower()
    for pattern in suspicious_patterns:
        if re.search(pattern, text_lower):
            logger.warning(f"Patrón sospechoso detectado: {pattern}")
            return True

    return False


async def _get_telegram_id(update: Update) -> str:
    """Obtiene el telegram_id del mensaje."""
    return str(update.effective_chat.id)


async def _get_or_create_user_profile(telegram_id: str, name: str = "Usuario") -> str:
    """
    Obtiene o crea el perfil de usuario y retorna el UUID interno.

    Args:
        telegram_id: ID de Telegram del usuario
        name: Nombre del usuario

    Returns:
        UUID del perfil de usuario como string
    """
    from uuid import uuid4
    from sqlalchemy import select
    from app.db.database import get_session
    from app.db.models import UserProfileModel

    async with get_session() as session:
        # Buscar por telegram_id
        result = await session.execute(
            select(UserProfileModel).where(UserProfileModel.telegram_id == telegram_id)
        )
        profile = result.scalar_one_or_none()

        if profile is None:
            # Crear nuevo perfil con UUID generado
            profile = UserProfileModel(
                id=uuid4(),
                telegram_id=telegram_id,
                telegram_chat_id=telegram_id,
                name=name,
                timezone="America/Mexico_City",
                work_days=["mon", "tue", "wed", "thu", "fri"],
                gym_days=["mon", "tue", "wed", "thu", "fri"],
            )
            session.add(profile)
            await session.commit()
            logger.info(f"Perfil creado para telegram_id {telegram_id} con UUID {profile.id}")

        return str(profile.id)


# ==================== COMMAND HANDLERS ====================


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para /start."""
    user = update.effective_user
    telegram_id = await _get_telegram_id(update)

    # Crear/obtener user_profile (usa UUID internamente)
    await _get_or_create_user_profile(telegram_id, user.first_name)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Tareas de hoy", callback_data="cmd_today"),
            InlineKeyboardButton("📅 Planificar", callback_data="cmd_plan"),
        ],
        [
            InlineKeyboardButton("❓ Ayuda", callback_data="help"),
        ]
    ])

    await update.message.reply_html(
        f"<b>👋 Hola {user.first_name}!</b>\n\n"
        "Soy <b>Carlos Command</b>, tu asistente personal inteligente.\n\n"
        "💬 <b>Escríbeme naturalmente:</b>\n"
        "├── <i>\"Crear tarea revisar PRs\"</i>\n"
        "├── <i>\"¿Qué tengo para hoy?\"</i>\n"
        "├── <i>\"Gasté $500 en comida\"</i>\n"
        "└── <i>\"Planifica mi día\"</i>\n\n"
        "🚀 <b>¿Por dónde empezamos?</b>",
        reply_markup=keyboard
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para /help."""
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Tareas", callback_data="help_tasks"),
            InlineKeyboardButton("💰 Finanzas", callback_data="help_finance"),
        ],
        [
            InlineKeyboardButton("🏋️ Salud", callback_data="help_health"),
            InlineKeyboardButton("📅 Planificación", callback_data="help_plan"),
        ],
        [
            InlineKeyboardButton("💡 Ejemplos", callback_data="help_examples"),
        ]
    ])

    await update.message.reply_html(
        "<b>🤖 Carlos Command - Ayuda</b>\n\n"
        "Soy tu asistente personal. Puedes escribirme de forma natural.\n\n"
        "<b>Acciones rápidas:</b>\n"
        "├── /today → Ver tareas de hoy\n"
        "├── /plan → Planificar el día\n"
        "└── /status → Estado del sistema\n\n"
        "Selecciona una categoría para más info:",
        reply_markup=keyboard
    )


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para /today - Muestra tareas de hoy via Brain."""
    telegram_id = await _get_telegram_id(update)
    user_id = await _get_or_create_user_profile(telegram_id)

    brain = await get_brain(user_id)
    response = await brain.handle_message("¿Qué tareas tengo para hoy?")

    if response.message:
        await update.message.reply_html(
            response.message,
            reply_markup=_build_keyboard(response.keyboard)
        )


async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para /plan - Planifica el día via Brain."""
    telegram_id = await _get_telegram_id(update)
    user_id = await _get_or_create_user_profile(telegram_id)

    brain = await get_brain(user_id)
    response = await brain.handle_message("Planifica mi día")

    if response.message:
        await update.message.reply_html(
            response.message,
            reply_markup=_build_keyboard(response.keyboard)
        )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para /status."""
    from datetime import datetime
    from app.triggers.scheduler import get_scheduled_triggers

    triggers = get_scheduled_triggers()

    status_text = (
        "<b>Estado del Sistema</b>\n\n"
        f"<b>Entorno:</b> {settings.app_env}\n"
        f"<b>Bot:</b> ✅ Online\n"
        f"<b>Brain:</b> ✅ Activo\n"
        f"<b>Triggers:</b> {len(triggers)} programados\n"
        f"<b>Hora:</b> {datetime.now().strftime('%H:%M:%S')}"
    )

    await update.message.reply_html(status_text)


# ==================== MESSAGE HANDLER ====================


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler principal de mensajes.

    Todos los mensajes de texto van al Brain.
    Incluye sanitización, detección de prompt injection y timeout.
    """
    if not update.message or not update.message.text:
        return

    telegram_id = await _get_telegram_id(update)
    raw_text = update.message.text

    # Sanitizar input
    text = _sanitize_input(raw_text)

    if not text:
        return

    logger.info(f"Mensaje recibido de {telegram_id}: {text[:50]}...")

    # Detectar intentos de prompt injection (log pero no bloquear)
    if _detect_suspicious_patterns(text):
        logger.warning(f"Posible prompt injection de {telegram_id}: {text[:100]}")
        # El Brain tiene instrucciones para manejar esto, no bloqueamos

    try:
        # Indicador de "escribiendo"
        await update.message.chat.send_action("typing")

        # Obtener UUID del usuario
        user_id = await _get_or_create_user_profile(telegram_id)

        # Procesar con el Brain (con timeout)
        brain = await get_brain(user_id)

        try:
            response = await asyncio.wait_for(
                brain.handle_message(text),
                timeout=BRAIN_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            logger.error(f"Timeout procesando mensaje de {telegram_id}")
            await update.message.reply_html(
                "⏱️ La solicitud tardó demasiado. Intenta con algo más simple o vuelve a intentar.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Reintentar", callback_data="retry_last")
                ]])
            )
            return

        # Enviar respuesta
        if response.message:
            await update.message.reply_html(
                response.message,
                reply_markup=_build_keyboard(response.keyboard)
            )
        else:
            # El Brain decidió no responder - enviar confirmación mínima
            logger.info(f"Brain no generó respuesta para: {text[:30]}...")
            await update.message.reply_text("👍")

    except Exception as e:
        logger.exception(f"Error procesando mensaje: {e}")
        await update.message.reply_html(
            "❌ Ocurrió un error procesando tu mensaje.\n\n"
            "<i>Intenta de nuevo o usa /help para ver comandos disponibles.</i>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🆘 Ayuda", callback_data="help"),
                InlineKeyboardButton("🔄 Reintentar", callback_data="retry_last")
            ]])
        )


# ==================== CALLBACK HANDLER ====================

# Respuestas predefinidas para callbacks de ayuda
HELP_RESPONSES = {
    "help": (
        "<b>🤖 Carlos Command - Ayuda</b>\n\n"
        "Soy tu asistente personal. Escríbeme naturalmente.\n\n"
        "<b>Categorías:</b>",
        [
            [{"text": "📋 Tareas", "callback_data": "help_tasks"},
             {"text": "💰 Finanzas", "callback_data": "help_finance"}],
            [{"text": "🏋️ Salud", "callback_data": "help_health"},
             {"text": "📅 Planificación", "callback_data": "help_plan"}],
            [{"text": "💡 Ejemplos", "callback_data": "help_examples"}],
        ]
    ),
    "help_tasks": (
        "<b>📋 Gestión de Tareas</b>\n\n"
        "<b>Crear tareas:</b>\n"
        "├── <i>\"Crear tarea revisar PRs\"</i>\n"
        "├── <i>\"Nueva tarea urgente: deploy\"</i>\n"
        "└── <i>\"Agregar: llamar al cliente\"</i>\n\n"
        "<b>Consultar:</b>\n"
        "├── <i>\"¿Qué tengo para hoy?\"</i>\n"
        "├── <i>\"Tareas pendientes\"</i>\n"
        "└── <i>\"¿Qué está bloqueado?\"</i>\n\n"
        "<b>Actualizar:</b>\n"
        "├── <i>\"Completé la tarea del reporte\"</i>\n"
        "└── <i>\"Empezar tarea de API\"</i>",
        [[{"text": "◀️ Volver", "callback_data": "help"}]]
    ),
    "help_finance": (
        "<b>💰 Finanzas</b>\n\n"
        "<b>Registrar gastos:</b>\n"
        "├── <i>\"Gasté $500 en comida\"</i>\n"
        "├── <i>\"$200 uber\"</i>\n"
        "└── <i>\"Pagué $1500 de renta\"</i>\n\n"
        "<b>Consultar:</b>\n"
        "├── <i>\"¿Cuánto he gastado este mes?\"</i>\n"
        "├── <i>\"Resumen de gastos\"</i>\n"
        "└── <i>\"¿Cómo voy con el presupuesto?\"</i>",
        [[{"text": "◀️ Volver", "callback_data": "help"}]]
    ),
    "help_health": (
        "<b>🏋️ Salud y Gym</b>\n\n"
        "<b>Registrar workout:</b>\n"
        "├── <i>\"Fui al gym, hice push\"</i>\n"
        "├── <i>\"Entrené pierna hoy\"</i>\n"
        "└── <i>\"Hice cardio 30 min\"</i>\n\n"
        "<b>Consultar:</b>\n"
        "├── <i>\"¿Hoy es día de gym?\"</i>\n"
        "├── <i>\"¿Cuándo fui al gym?\"</i>\n"
        "└── <i>\"Mi racha de gym\"</i>",
        [[{"text": "◀️ Volver", "callback_data": "help"}]]
    ),
    "help_plan": (
        "<b>📅 Planificación</b>\n\n"
        "<b>Comandos:</b>\n"
        "├── /today → Ver tareas de hoy\n"
        "├── /plan → Planificar el día\n"
        "└── /status → Estado del sistema\n\n"
        "<b>Natural:</b>\n"
        "├── <i>\"Planifica mi día\"</i>\n"
        "├── <i>\"¿Qué tengo mañana?\"</i>\n"
        "└── <i>\"Organiza mi semana\"</i>",
        [[{"text": "◀️ Volver", "callback_data": "help"}]]
    ),
    "help_examples": (
        "<b>💡 Ejemplos de Uso</b>\n\n"
        "🗣️ <b>Solo escríbeme:</b>\n\n"
        "├── <i>\"Crear tarea urgente para mañana\"</i>\n"
        "├── <i>\"Gasté $300 en Amazon\"</i>\n"
        "├── <i>\"Hoy entrené push day\"</i>\n"
        "├── <i>\"¿Qué tareas tengo bloqueadas?\"</i>\n"
        "├── <i>\"Recuérdame llamar a las 3pm\"</i>\n"
        "└── <i>\"¿Cómo voy con mis finanzas?\"</i>\n\n"
        "💡 No necesitas comandos especiales, solo háblame natural.",
        [[{"text": "◀️ Volver", "callback_data": "help"}]]
    ),
}


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler de callbacks (botones inline).

    Maneja callbacks especiales (help, comandos) y envía el resto al Brain.
    """
    query = update.callback_query
    await query.answer()

    telegram_id = await _get_telegram_id(update)
    callback_data = query.data

    logger.info(f"Callback de {telegram_id}: {callback_data}")

    try:
        # Manejar callbacks especiales de ayuda
        if callback_data in HELP_RESPONSES:
            text, keyboard_data = HELP_RESPONSES[callback_data]
            await query.edit_message_text(
                text,
                parse_mode="HTML",
                reply_markup=_build_keyboard(keyboard_data)
            )
            return

        # Manejar comandos rápidos
        if callback_data == "cmd_today":
            user_id = await _get_or_create_user_profile(telegram_id)
            brain = await get_brain(user_id)
            response = await brain.handle_message("¿Qué tareas tengo para hoy?")
            await query.message.reply_html(
                response.message,
                reply_markup=_build_keyboard(response.keyboard)
            )
            return

        if callback_data == "cmd_plan":
            user_id = await _get_or_create_user_profile(telegram_id)
            brain = await get_brain(user_id)
            response = await brain.handle_message("Planifica mi día")
            await query.message.reply_html(
                response.message,
                reply_markup=_build_keyboard(response.keyboard)
            )
            return

        if callback_data == "retry_last":
            await query.message.reply_text(
                "Por favor, escribe tu mensaje de nuevo."
            )
            return

        # Para otros callbacks, enviar al Brain
        user_id = await _get_or_create_user_profile(telegram_id)
        brain = await get_brain(user_id)
        response = await brain.handle_callback(callback_data)

        # Actualizar mensaje o enviar nuevo
        if response.message:
            try:
                await query.edit_message_text(
                    response.message,
                    parse_mode="HTML",
                    reply_markup=_build_keyboard(response.keyboard)
                )
            except Exception:
                # Si no se puede editar, enviar nuevo mensaje
                await query.message.reply_html(
                    response.message,
                    reply_markup=_build_keyboard(response.keyboard)
                )

    except Exception as e:
        logger.exception(f"Error procesando callback: {e}")
        await query.message.reply_text("Error procesando acción. Intenta de nuevo.")


# ==================== SETUP ====================


def setup_handlers(app: Application) -> None:
    """Configura todos los handlers del bot."""

    # Comandos
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("today", today_command))
    app.add_handler(CommandHandler("plan", plan_command))
    app.add_handler(CommandHandler("status", status_command))

    # Callbacks
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Mensajes de texto (catch-all)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Handlers V2 configurados")


async def get_application() -> Application:
    """Obtiene o crea la aplicación de Telegram."""
    global _application

    if _application is None:
        _application = (
            Application.builder()
            .token(settings.telegram_bot_token)
            .build()
        )
        setup_handlers(_application)

    return _application


async def initialize_bot() -> Application:
    """Inicializa el bot de Telegram."""
    app = await get_application()
    await app.initialize()
    await app.start()

    # Configurar menú de comandos moderno
    commands = [
        BotCommand("start", "🚀 Iniciar el bot"),
        BotCommand("today", "📋 Ver tareas de hoy"),
        BotCommand("plan", "📅 Planificar mi día"),
        BotCommand("status", "📊 Estado del sistema"),
        BotCommand("help", "❓ Ayuda y comandos"),
    ]
    await app.bot.set_my_commands(commands)

    logger.info("Bot de Telegram inicializado con menú de comandos")
    return app


async def shutdown_bot() -> None:
    """Detiene el bot de Telegram."""
    global _application
    if _application:
        await _application.stop()
        await _application.shutdown()
        logger.info("Bot de Telegram detenido")
