"""
Core module - Componentes centrales del sistema.

Este módulo contiene la infraestructura central:
- LLM: Proveedor multi-modelo (Flash/Pro)
- Routing: Registry de handlers y dispatcher
- Parsing: Utilidades centralizadas de parsing
"""

import logging

from app.core.llm import (
    LLMProvider,
    ModelType,
    get_llm_provider,
    ensure_llm_configured,
)
from app.core.routing import (
    IntentHandlerRegistry,
    BaseIntentHandler,
    HandlerResponse,
    get_handler_registry,
    dispatch_intent,
    handle_message_with_registry,
)
from app.core.parsing import DSPyParser

logger = logging.getLogger(__name__)

__all__ = [
    # LLM
    "LLMProvider",
    "ModelType",
    "get_llm_provider",
    "ensure_llm_configured",
    # Routing
    "IntentHandlerRegistry",
    "BaseIntentHandler",
    "HandlerResponse",
    "get_handler_registry",
    "dispatch_intent",
    "handle_message_with_registry",
    # Parsing
    "DSPyParser",
    # Setup
    "initialize_core",
]


def initialize_core() -> None:
    """
    Inicializa todos los componentes del core.

    Llamar esta función al inicio de la aplicación antes de
    procesar cualquier mensaje.

    Orden de inicialización:
    1. Configura LLMProvider (modelos Flash/Pro)
    2. Registra todos los Intent Handlers
    3. Configura fallback handler

    Uso:
        from app.core import initialize_core
        initialize_core()
    """
    logger.info("Inicializando core...")

    # 1. Configurar LLM Provider
    provider = get_llm_provider()
    provider.configure()
    logger.info(f"LLM configurado: modelo por defecto {provider.current_model.value}")

    # 2. Registrar handlers
    from app.agents.handlers import register_all_handlers
    register_all_handlers()

    logger.info("Core inicializado correctamente")
