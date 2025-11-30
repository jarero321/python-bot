"""
Capture Handlers - Ideas, notas y fallback.

Handlers para capturar ideas, notas, y manejar intents desconocidos.
"""

import logging
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from app.agents.intent_router import UserIntent
from app.core.routing import (
    BaseIntentHandler,
    HandlerResponse,
    intent_handler,
    get_handler_registry,
)
from app.services.notion import get_notion_service, KnowledgeTipo, InboxFuente

logger = logging.getLogger(__name__)


@intent_handler(UserIntent.IDEA)
class IdeaHandler(BaseIntentHandler):
    """Handler para capturar ideas."""

    name = "IdeaHandler"
    intents = [UserIntent.IDEA]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        text = self.get_raw_message(intent_result)

        notion = get_notion_service()
        result = await notion.create_knowledge(
            titulo=text[:100],
            contenido=text,
            tipo=KnowledgeTipo.IDEA,
        )

        if result:
            return HandlerResponse(
                message=(
                    f"💡 <b>Idea guardada</b>\n\n"
                    f"<i>{text[:100]}</i>\n\n"
                    f"Puedes verla en tu base de conocimiento."
                )
            )

        return HandlerResponse(
            message="❌ Error guardando la idea. Intenta de nuevo.",
            success=False,
        )


@intent_handler(UserIntent.NOTE)
class NoteHandler(BaseIntentHandler):
    """Handler para capturar notas."""

    name = "NoteHandler"
    intents = [UserIntent.NOTE]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        text = self.get_raw_message(intent_result)

        notion = get_notion_service()
        result = await notion.create_knowledge(
            titulo=text[:100],
            contenido=text,
            tipo=KnowledgeTipo.NOTA,
        )

        if result:
            return HandlerResponse(
                message=(
                    f"📝 <b>Nota guardada</b>\n\n"
                    f"<i>{text[:100]}</i>\n\n"
                    f"Puedes verla en tu base de conocimiento."
                )
            )

        return HandlerResponse(
            message="❌ Error guardando la nota. Intenta de nuevo.",
            success=False,
        )


@intent_handler(UserIntent.UNKNOWN)
class UnknownHandler(BaseIntentHandler):
    """Handler fallback para intents no reconocidos."""

    name = "UnknownHandler"
    intents = [UserIntent.UNKNOWN]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        text = self.get_raw_message(intent_result)
        confidence = getattr(intent_result, "confidence", 0.5)

        # Guardar en inbox como fallback
        notion = get_notion_service()
        result = await notion.create_inbox_item(
            contenido=text[:200],
            fuente=InboxFuente.TELEGRAM,
            notas=f"Intent: unknown (confidence: {confidence:.2f})",
        )

        if result:
            return HandlerResponse(
                message=(
                    f"📥 <b>Guardado en Inbox</b>\n\n"
                    f"<i>{text[:100]}</i>\n\n"
                    f"No estoy seguro qué hacer con esto, "
                    f"así que lo guardé para que lo revises."
                )
            )

        return HandlerResponse(
            message="❌ Error guardando en inbox. Intenta de nuevo.",
            success=False,
        )


class FallbackHandler(BaseIntentHandler):
    """
    Handler de respaldo cuando no hay match.

    No se registra con decorador, se establece manualmente como fallback.
    """

    name = "FallbackHandler"
    intents = []

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        text = self.get_raw_message(intent_result)
        confidence = getattr(intent_result, "confidence", 0.0)

        # Guardar en inbox
        notion = get_notion_service()
        await notion.create_inbox_item(
            contenido=text[:200],
            fuente=InboxFuente.TELEGRAM,
            notas=f"Fallback handler - confidence: {confidence:.2f}",
        )

        return HandlerResponse(
            message=(
                "🤔 No entendí completamente tu mensaje.\n\n"
                "Lo guardé en el inbox para que lo revises.\n\n"
                "Intenta ser más específico o usa /help para ver comandos."
            )
        )


def setup_fallback_handler() -> None:
    """Configura el handler de fallback en el registry."""
    registry = get_handler_registry()
    registry.set_fallback(FallbackHandler())
