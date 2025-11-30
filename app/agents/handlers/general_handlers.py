"""
General Handlers - Greeting, Help, Status.

Handlers para intents generales del sistema.
"""

import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from app.agents.intent_router import UserIntent
from app.config import get_settings
from app.core.routing import (
    BaseIntentHandler,
    HandlerResponse,
    intent_handler,
)
from app.services.notion import get_notion_service

logger = logging.getLogger(__name__)
settings = get_settings()


@intent_handler(UserIntent.GREETING)
class GreetingHandler(BaseIntentHandler):
    """Handler para saludos."""

    name = "GreetingHandler"
    intents = [UserIntent.GREETING]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result,
    ) -> HandlerResponse:
        user = update.effective_user
        hour = datetime.now().hour

        if hour < 12:
            greeting = "Buenos días"
        elif hour < 19:
            greeting = "Buenas tardes"
        else:
            greeting = "Buenas noches"

        message = (
            f"{greeting}, <b>{user.first_name}</b>! "
            "¿En qué te puedo ayudar?\n\n"
            "Puedes pedirme:\n"
            "• Crear/ver tareas\n"
            "• Planificar tu día\n"
            "• Registrar gastos\n"
            "• Guardar ideas"
        )

        return HandlerResponse(message=message)


@intent_handler(UserIntent.HELP)
class HelpHandler(BaseIntentHandler):
    """Handler para solicitudes de ayuda."""

    name = "HelpHandler"
    intents = [UserIntent.HELP]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result,
    ) -> HandlerResponse:
        message = (
            "<b>Ayuda - Carlos Command</b>\n\n"
            "Puedes enviarme mensajes naturales y los procesaré.\n\n"
            "<b>Tareas:</b>\n"
            "• 'Agregar tarea revisar emails'\n"
            "• '¿Qué tareas tengo hoy?'\n"
            "• 'Completar tarea X'\n\n"
            "<b>Planificación:</b>\n"
            "• '¿Qué hago mañana?'\n"
            "• 'Ayúdame a priorizar'\n"
            "• 'Ver mi semana'\n\n"
            "<b>Finanzas:</b>\n"
            "• 'Gasté $500 en comida'\n"
            "• '¿Vale la pena comprar X?'\n"
            "• '¿Cómo van mis deudas?'\n\n"
            "<b>Fitness:</b>\n"
            "• 'Hoy hice pecho y bícep'\n"
            "• 'Comí una ensalada'\n\n"
            "<b>Captura:</b>\n"
            "• 'Idea: app para X'\n"
            "• 'Nota: recordar Y'"
        )

        return HandlerResponse(message=message)


@intent_handler(UserIntent.STATUS)
class StatusHandler(BaseIntentHandler):
    """Handler para consulta de estado del sistema."""

    name = "StatusHandler"
    intents = [UserIntent.STATUS]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result,
    ) -> HandlerResponse:
        notion = get_notion_service()

        # Test conexión Notion
        notion_ok = await notion.test_connection()
        notion_status = "✅ Conectado" if notion_ok else "❌ Error"

        message = (
            "<b>Estado del Sistema</b>\n\n"
            f"<b>Entorno:</b> {settings.app_env}\n"
            f"<b>Bot:</b> ✅ Online\n"
            f"<b>Notion:</b> {notion_status}\n"
            f"<b>Hora:</b> {datetime.now().strftime('%H:%M:%S')}"
        )

        return HandlerResponse(message=message)
