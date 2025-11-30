"""
IntentHandlerRegistry - Sistema de registro y dispatch de handlers por intent.

Reemplaza los 30+ if/elif en handlers.py con un patrón Registry/Strategy.

Uso:
    # Definir un handler
    @intent_handler(UserIntent.TASK_CREATE)
    class TaskCreateHandler(BaseIntentHandler):
        async def handle(self, update, context, intent_result):
            # Lógica específica para crear tarea
            return HandlerResponse(message="Tarea creada")

    # En el código principal
    registry = get_handler_registry()
    response = await registry.dispatch(intent, update, context, intent_result)
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Type

from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


@dataclass
class HandlerResponse:
    """Respuesta estandarizada de un handler."""

    message: str
    parse_mode: str = "HTML"
    keyboard: InlineKeyboardMarkup | None = None
    success: bool = True
    data: dict = field(default_factory=dict)
    # Si True, el dispatcher no envía mensaje (el handler ya lo hizo)
    already_sent: bool = False


class BaseIntentHandler(ABC):
    """
    Clase base para todos los handlers de intents.

    Cada intent tiene su propio handler que implementa la lógica específica.
    """

    # Nombre descriptivo del handler
    name: str = "BaseHandler"

    # Intent(s) que maneja este handler (puede ser uno o varios)
    intents: list = []

    # Confianza mínima requerida para ejecutar (0.0-1.0)
    min_confidence: float = 0.0

    # Si requiere confirmación antes de ejecutar acción
    requires_confirmation: bool = False

    def __init__(self):
        self.logger = logging.getLogger(f"handlers.{self.name}")

    @abstractmethod
    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        """
        Procesa el intent y retorna una respuesta.

        Args:
            update: Update de Telegram
            context: Contexto de Telegram
            intent_result: Resultado del IntentRouter con entities y confidence

        Returns:
            HandlerResponse con mensaje y opciones
        """
        pass

    async def validate(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> tuple[bool, str | None]:
        """
        Valida si el handler puede procesar este request.

        Returns:
            (is_valid, error_message)
        """
        # Validar confianza mínima
        if hasattr(intent_result, "confidence"):
            if intent_result.confidence < self.min_confidence:
                return False, f"Confianza muy baja ({intent_result.confidence:.0%})"

        return True, None

    async def pre_handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> None:
        """Hook ejecutado antes de handle(). Override para logging, métricas, etc."""
        self.logger.debug(f"Pre-handle: {self.name}")

    async def post_handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
        response: HandlerResponse,
    ) -> None:
        """Hook ejecutado después de handle(). Override para cleanup, métricas, etc."""
        self.logger.debug(f"Post-handle: {self.name} - success={response.success}")

    def get_entities(self, intent_result: Any) -> dict:
        """Extrae entities del intent result de forma segura."""
        if hasattr(intent_result, "entities"):
            return intent_result.entities or {}
        return {}

    def get_raw_message(self, intent_result: Any) -> str:
        """Extrae el mensaje original del intent result."""
        if hasattr(intent_result, "raw_message"):
            return intent_result.raw_message or ""
        return ""


class IntentHandlerRegistry:
    """
    Registry central de handlers de intents.

    Gestiona el registro y dispatch de handlers según el intent detectado.
    """

    _instance: "IntentHandlerRegistry | None" = None

    def __new__(cls) -> "IntentHandlerRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._handlers: dict[Enum, BaseIntentHandler] = {}
        self._fallback_handler: BaseIntentHandler | None = None
        self.logger = logging.getLogger("routing.registry")

    def register(
        self,
        intent: Enum,
        handler: BaseIntentHandler,
    ) -> None:
        """
        Registra un handler para un intent específico.

        Args:
            intent: El intent (UserIntent enum)
            handler: Instancia del handler
        """
        if intent in self._handlers:
            self.logger.warning(
                f"Handler para {intent} ya existe, será reemplazado por {handler.name}"
            )
        self._handlers[intent] = handler
        self.logger.debug(f"Handler registrado: {intent} -> {handler.name}")

    def register_multiple(
        self,
        intents: list[Enum],
        handler: BaseIntentHandler,
    ) -> None:
        """Registra el mismo handler para múltiples intents."""
        for intent in intents:
            self.register(intent, handler)

    def set_fallback(self, handler: BaseIntentHandler) -> None:
        """Establece el handler por defecto cuando no hay match."""
        self._fallback_handler = handler
        self.logger.info(f"Fallback handler establecido: {handler.name}")

    def get_handler(self, intent: Enum) -> BaseIntentHandler | None:
        """Obtiene el handler para un intent específico."""
        return self._handlers.get(intent, self._fallback_handler)

    def has_handler(self, intent: Enum) -> bool:
        """Verifica si existe un handler para el intent."""
        return intent in self._handlers

    async def dispatch(
        self,
        intent: Enum,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        """
        Despacha el request al handler correspondiente.

        Args:
            intent: El intent detectado
            update: Update de Telegram
            context: Contexto de Telegram
            intent_result: Resultado completo del IntentRouter

        Returns:
            HandlerResponse del handler ejecutado
        """
        handler = self.get_handler(intent)

        if handler is None:
            self.logger.warning(f"No hay handler para intent: {intent}")
            return HandlerResponse(
                message="No entendí tu mensaje. ¿Puedes reformularlo?",
                success=False,
            )

        try:
            # Validar
            is_valid, error_msg = await handler.validate(update, context, intent_result)
            if not is_valid:
                self.logger.info(f"Validación fallida para {intent}: {error_msg}")
                return HandlerResponse(
                    message=error_msg or "No pude procesar tu solicitud",
                    success=False,
                )

            # Pre-handle hook
            await handler.pre_handle(update, context, intent_result)

            # Ejecutar handler
            response = await handler.handle(update, context, intent_result)

            # Post-handle hook
            await handler.post_handle(update, context, intent_result, response)

            return response

        except Exception as e:
            self.logger.exception(f"Error en handler {handler.name}: {e}")
            return HandlerResponse(
                message="Ocurrió un error procesando tu solicitud.",
                success=False,
            )

    def list_handlers(self) -> dict[str, str]:
        """Lista todos los handlers registrados."""
        return {
            str(intent): handler.name
            for intent, handler in self._handlers.items()
        }

    @property
    def handler_count(self) -> int:
        """Número de handlers registrados."""
        return len(self._handlers)


# Singleton accessor
_registry: IntentHandlerRegistry | None = None


def get_handler_registry() -> IntentHandlerRegistry:
    """Obtiene la instancia del registry."""
    global _registry
    if _registry is None:
        _registry = IntentHandlerRegistry()
    return _registry


def register_handler(intent: Enum) -> Callable:
    """
    Decorador para registrar un handler automáticamente.

    Uso:
        @register_handler(UserIntent.TASK_CREATE)
        class TaskCreateHandler(BaseIntentHandler):
            ...
    """
    def decorator(cls: Type[BaseIntentHandler]) -> Type[BaseIntentHandler]:
        registry = get_handler_registry()
        handler_instance = cls()
        registry.register(intent, handler_instance)
        return cls
    return decorator


def intent_handler(*intents: Enum) -> Callable:
    """
    Decorador para registrar un handler para uno o más intents.

    Uso:
        @intent_handler(UserIntent.GREETING, UserIntent.HELP)
        class GeneralHandler(BaseIntentHandler):
            ...
    """
    def decorator(cls: Type[BaseIntentHandler]) -> Type[BaseIntentHandler]:
        registry = get_handler_registry()
        handler_instance = cls()
        for intent in intents:
            registry.register(intent, handler_instance)
        return cls
    return decorator
