"""
Intent Dispatcher - Reemplaza route_by_intent de handlers.py.

Este módulo usa el IntentHandlerRegistry para despachar intents
de manera limpia, eliminando los 30+ if/elif.
"""

import logging
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from app.core.routing.registry import (
    get_handler_registry,
    HandlerResponse,
)

logger = logging.getLogger(__name__)


async def dispatch_intent(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    intent_result: Any,
) -> None:
    """
    Despacha un intent al handler correspondiente usando el registry.

    Esta función reemplaza route_by_intent() de handlers.py.

    Args:
        update: Update de Telegram
        context: Contexto de Telegram
        intent_result: Resultado del IntentRouter con intent, entities, confidence
    """
    registry = get_handler_registry()
    intent = intent_result.intent

    logger.debug(f"Dispatching intent: {intent.value}")

    # Usar el registry para despachar
    response = await registry.dispatch(
        intent=intent,
        update=update,
        context=context,
        intent_result=intent_result,
    )

    # Si el handler ya envió el mensaje, no hacer nada más
    if response.already_sent:
        logger.debug(f"Handler already sent response for {intent.value}")
        return

    # Enviar respuesta al usuario
    await send_response(update, response)


async def send_response(update: Update, response: HandlerResponse) -> None:
    """
    Envía la respuesta del handler al usuario.

    Args:
        update: Update de Telegram
        response: Respuesta del handler
    """
    try:
        await update.message.reply_html(
            text=response.message,
            reply_markup=response.keyboard,
        )
    except Exception as e:
        logger.error(f"Error enviando respuesta: {e}")
        # Intentar sin HTML como fallback
        try:
            await update.message.reply_text(
                text=response.message,
                reply_markup=response.keyboard,
            )
        except Exception as e2:
            logger.error(f"Error en fallback de respuesta: {e2}")


async def handle_message_with_registry(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Handler principal de mensajes usando el nuevo sistema de registry.

    Esta función puede reemplazar handle_message() de handlers.py
    para usar la arquitectura modular.
    """
    try:
        text = update.message.text
        user = update.effective_user
        user_id = user.id

        logger.info(f"Mensaje de {user_id}: {text[:50]}...")

        # Intentar usar ConversationalOrchestrator primero
        try:
            from app.agents.conversational_orchestrator import (
                get_conversational_orchestrator,
            )
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            orchestrator = get_conversational_orchestrator()
            response = await orchestrator.process_message(
                user_id=user_id,
                message=text,
            )

            # Si es respuesta contextual, manejarla directamente
            if response.is_contextual or response.keyboard_options:
                keyboard = None
                if response.keyboard_options:
                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(
                                opt["text"],
                                callback_data=opt["callback"],
                            )
                            for opt in row
                        ]
                        for row in response.keyboard_options
                    ])

                await update.message.reply_html(
                    response.message,
                    reply_markup=keyboard,
                )
                return

            # Si no es contextual, usar el registry con el intent detectado
            from app.agents.intent_router import IntentResult

            intent_result = IntentResult(
                intent=response.intent,
                confidence=0.8,
                entities={},
                suggested_response=None,
                raw_message=text,
            )

            await dispatch_intent(update, context, intent_result)
            return

        except Exception as e:
            logger.warning(
                f"ConversationalOrchestrator falló, usando fallback: {e}"
            )

        # Fallback: Usar IntentRouter directamente
        from app.agents.intent_router import get_intent_router

        router = get_intent_router()

        # Obtener contexto de conversación
        conversation_context = context.user_data.get("last_messages", "")

        # Clasificar intención con AI
        try:
            intent_result = await router.execute(text, conversation_context)
        except Exception as e:
            logger.exception(f"Error en IntentRouter, usando fallback: {e}")
            intent_result = await router.get_fallback_intent(text)

        # Guardar mensaje en contexto para futuras clasificaciones
        last_messages = context.user_data.get("last_messages_list", [])
        last_messages.append(text[:100])
        if len(last_messages) > 5:
            last_messages = last_messages[-5:]
        context.user_data["last_messages_list"] = last_messages
        context.user_data["last_messages"] = " | ".join(last_messages)

        # Log de la clasificación
        logger.info(
            f"Intent: {intent_result.intent.value}, "
            f"Confidence: {intent_result.confidence:.2f}, "
            f"Entities: {intent_result.entities}"
        )

        # Despachar usando el registry
        await dispatch_intent(update, context, intent_result)

    except Exception as e:
        logger.exception(f"Error en handle_message_with_registry: {e}")
        await update.message.reply_text(
            "Ocurrió un error procesando tu mensaje. Por favor intenta de nuevo."
        )
