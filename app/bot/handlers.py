"""
Bot Handlers - Simplificados usando el Brain.

Todos los mensajes van al Brain, que decide que hacer.
Los handlers solo son wrappers que pasan mensajes al Brain.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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


async def _get_user_id(update: Update) -> str:
    """Obtiene el user_id del mensaje."""
    return str(update.effective_chat.id)


async def _ensure_user_profile(user_id: str, name: str) -> None:
    """Crea el perfil de usuario si no existe."""
    from sqlalchemy import select
    from app.db.database import get_session
    from app.db.models import UserProfileModel

    async with get_session() as session:
        result = await session.execute(
            select(UserProfileModel).where(UserProfileModel.user_id == user_id)
        )
        if result.scalar_one_or_none() is None:
            profile = UserProfileModel(
                user_id=user_id,
                name=name,
                telegram_chat_id=user_id,
                timezone="America/Mexico_City",
                work_days=["mon", "tue", "wed", "thu", "fri"],
                gym_days=["mon", "tue", "wed", "thu", "fri"],
            )
            session.add(profile)
            await session.commit()
            logger.info(f"Perfil creado para usuario {user_id}")


# ==================== COMMAND HANDLERS ====================


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para /start."""
    user = update.effective_user
    user_id = await _get_user_id(update)

    # Crear user_profile si no existe
    await _ensure_user_profile(user_id, user.first_name)

    await update.message.reply_html(
        f"Hola <b>{user.first_name}</b>! Soy Carlos Command.\n\n"
        "Tu asistente personal inteligente.\n\n"
        "Puedes escribirme cualquier cosa:\n"
        "• <i>Crear tarea revisar emails</i>\n"
        "• <i>¿Qué tengo para hoy?</i>\n"
        "• <i>Gasté $500 en comida</i>\n"
        "• <i>Planifica mi día</i>\n\n"
        "Comandos rápidos:\n"
        "/today - Tareas de hoy\n"
        "/plan - Planificar día\n"
        "/status - Estado del sistema"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para /help."""
    await update.message.reply_html(
        "<b>Ayuda - Carlos Command</b>\n\n"
        "Puedes escribirme de forma natural y entenderé.\n\n"
        "<b>Ejemplos:</b>\n"
        "• 'Crear tarea urgente revisar PRs'\n"
        "• '¿Qué tengo pendiente?'\n"
        "• 'Completé la tarea del reporte'\n"
        "• 'Gasté $200 en uber'\n"
        "• 'Fui al gym, hice push'\n"
        "• 'Planifica mi semana'\n\n"
        "<b>Comandos:</b>\n"
        "/today - Tareas de hoy\n"
        "/plan - Planificar día\n"
        "/status - Estado\n"
        "/help - Esta ayuda"
    )


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para /today - Muestra tareas de hoy via Brain."""
    user_id = await _get_user_id(update)

    brain = await get_brain(user_id)
    response = await brain.handle_message("¿Qué tareas tengo para hoy?")

    if response.message:
        await update.message.reply_html(
            response.message,
            reply_markup=_build_keyboard(response.keyboard)
        )


async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para /plan - Planifica el día via Brain."""
    user_id = await _get_user_id(update)

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
    """
    if not update.message or not update.message.text:
        return

    user_id = await _get_user_id(update)
    text = update.message.text

    logger.info(f"Mensaje recibido de {user_id}: {text[:50]}...")

    try:
        # Indicador de "escribiendo"
        await update.message.chat.send_action("typing")

        # Procesar con el Brain
        brain = await get_brain(user_id)
        response = await brain.handle_message(text)

        # Enviar respuesta
        if response.message:
            await update.message.reply_html(
                response.message,
                reply_markup=_build_keyboard(response.keyboard)
            )
        else:
            # El Brain decidió no responder (raro pero posible)
            logger.info(f"Brain no generó respuesta para: {text[:30]}...")

    except Exception as e:
        logger.exception(f"Error procesando mensaje: {e}")
        await update.message.reply_text(
            "Lo siento, ocurrió un error. ¿Puedes intentar de nuevo?"
        )


# ==================== CALLBACK HANDLER ====================


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler de callbacks (botones inline).

    Los callbacks van al Brain.
    """
    query = update.callback_query
    await query.answer()

    user_id = await _get_user_id(update)
    callback_data = query.data

    logger.info(f"Callback de {user_id}: {callback_data}")

    try:
        # Procesar con el Brain
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
    logger.info("Bot de Telegram inicializado")
    return app


async def shutdown_bot() -> None:
    """Detiene el bot de Telegram."""
    global _application
    if _application:
        await _application.stop()
        await _application.shutdown()
        logger.info("Bot de Telegram detenido")
