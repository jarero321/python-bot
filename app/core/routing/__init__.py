"""Routing module - Sistema de enrutamiento de intents."""

from app.core.routing.registry import (
    IntentHandlerRegistry,
    BaseIntentHandler,
    HandlerResponse,
    get_handler_registry,
    register_handler,
    intent_handler,
)
from app.core.routing.dispatcher import (
    dispatch_intent,
    send_response,
    handle_message_with_registry,
)

__all__ = [
    # Registry
    "IntentHandlerRegistry",
    "BaseIntentHandler",
    "HandlerResponse",
    "get_handler_registry",
    "register_handler",
    "intent_handler",
    # Dispatcher
    "dispatch_intent",
    "send_response",
    "handle_message_with_registry",
]
