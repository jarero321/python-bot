"""
Core module - Componentes centrales del sistema.

Este módulo contiene la infraestructura central:
- LLM: Proveedor multi-modelo (Flash/Pro)
- Routing: Registry de handlers y dispatcher
- Parsing: Utilidades centralizadas de parsing
- RAG: Búsqueda semántica con embeddings
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
from app.core.rag import (
    EmbeddingProvider,
    VectorStore,
    RAGRetriever,
    get_embedding_provider,
    get_vector_store,
    get_retriever,
)

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
    # RAG
    "EmbeddingProvider",
    "VectorStore",
    "RAGRetriever",
    "get_embedding_provider",
    "get_vector_store",
    "get_retriever",
    # Setup
    "initialize_core",
]


async def initialize_core(include_rag: bool = False) -> None:
    """
    Inicializa todos los componentes del core.

    Llamar esta función al inicio de la aplicación antes de
    procesar cualquier mensaje.

    Args:
        include_rag: Si inicializar el sistema RAG (requiere más recursos)

    Orden de inicialización:
    1. Configura LLMProvider (modelos Flash/Pro)
    2. Registra todos los Intent Handlers
    3. (Opcional) Inicializa RAG con embeddings

    Uso:
        from app.core import initialize_core
        await initialize_core(include_rag=True)
    """
    logger.info("Inicializando core...")

    # 1. Configurar LLM Provider
    provider = get_llm_provider()
    provider.configure()
    logger.info(f"LLM configurado: modelo por defecto {provider.current_model.value}")

    # 2. Registrar handlers
    from app.agents.handlers import register_all_handlers
    register_all_handlers()

    # 3. (Opcional) Inicializar RAG
    if include_rag:
        logger.info("Inicializando sistema RAG...")
        embedding_provider = get_embedding_provider()
        embedding_provider.configure()

        retriever = get_retriever()
        await retriever.initialize()
        logger.info(f"RAG inicializado: {get_vector_store().count} documentos en índice")

    logger.info("Core inicializado correctamente")


def initialize_core_sync() -> None:
    """
    Versión síncrona de initialize_core (sin RAG).

    Para uso en contextos donde no hay event loop disponible.
    """
    logger.info("Inicializando core (sync)...")

    # 1. Configurar LLM Provider
    provider = get_llm_provider()
    provider.configure()
    logger.info(f"LLM configurado: modelo por defecto {provider.current_model.value}")

    # 2. Registrar handlers
    from app.agents.handlers import register_all_handlers
    register_all_handlers()

    logger.info("Core inicializado correctamente (sync)")
