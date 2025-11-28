"""Manejo centralizado de errores y excepciones."""

import logging
import traceback
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, Callable, TypeVar

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ErrorCategory(str, Enum):
    """Categorías de errores."""

    NETWORK = "network"
    API_EXTERNAL = "api_external"
    API_NOTION = "api_notion"
    API_TELEGRAM = "api_telegram"
    API_GEMINI = "api_gemini"
    DATABASE = "database"
    VALIDATION = "validation"
    AGENT = "agent"
    SCHEDULER = "scheduler"
    UNKNOWN = "unknown"


@dataclass
class ErrorContext:
    """Contexto de un error para logging y métricas."""

    category: ErrorCategory
    operation: str
    error_type: str
    message: str
    details: dict[str, Any] | None = None
    traceback_str: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convierte a diccionario para logging."""
        return {
            "category": self.category.value,
            "operation": self.operation,
            "error_type": self.error_type,
            "message": self.message,
            "details": self.details,
        }


class CarlosCommandError(Exception):
    """Excepción base para Carlos Command."""

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.details = details or {}

    def __str__(self) -> str:
        return f"[{self.category.value}] {self.message}"


class NotionAPIError(CarlosCommandError):
    """Error de la API de Notion."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, ErrorCategory.API_NOTION, details)


class TelegramAPIError(CarlosCommandError):
    """Error de la API de Telegram."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, ErrorCategory.API_TELEGRAM, details)


class GeminiAPIError(CarlosCommandError):
    """Error de la API de Gemini."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, ErrorCategory.API_GEMINI, details)


class AgentError(CarlosCommandError):
    """Error en un agente DSPy."""

    def __init__(self, agent_name: str, message: str, details: dict[str, Any] | None = None):
        details = details or {}
        details["agent_name"] = agent_name
        super().__init__(message, ErrorCategory.AGENT, details)
        self.agent_name = agent_name


class ValidationError(CarlosCommandError):
    """Error de validación de datos."""

    def __init__(self, message: str, field: str | None = None, details: dict[str, Any] | None = None):
        details = details or {}
        if field:
            details["field"] = field
        super().__init__(message, ErrorCategory.VALIDATION, details)


def log_error(
    error: Exception,
    operation: str,
    category: ErrorCategory = ErrorCategory.UNKNOWN,
    extra: dict[str, Any] | None = None,
) -> ErrorContext:
    """
    Registra un error con contexto estructurado.

    Args:
        error: La excepción capturada
        operation: Nombre de la operación que falló
        category: Categoría del error
        extra: Información adicional

    Returns:
        ErrorContext con los detalles del error
    """
    if isinstance(error, CarlosCommandError):
        category = error.category
        details = {**(error.details or {}), **(extra or {})}
    else:
        details = extra or {}

    context = ErrorContext(
        category=category,
        operation=operation,
        error_type=type(error).__name__,
        message=str(error),
        details=details,
        traceback_str=traceback.format_exc(),
    )

    logger.error(
        f"Error en {operation}: {error}",
        extra={"error_context": context.to_dict()},
    )

    return context


def with_error_handling(
    operation: str,
    category: ErrorCategory = ErrorCategory.UNKNOWN,
    default_return: Any = None,
    reraise: bool = False,
):
    """
    Decorador para manejo uniforme de errores.

    Args:
        operation: Nombre de la operación para logging
        category: Categoría de error por defecto
        default_return: Valor a retornar en caso de error
        reraise: Si debe re-lanzar la excepción después de loguear
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except CarlosCommandError:
                raise
            except Exception as e:
                log_error(e, operation, category)
                if reraise:
                    raise CarlosCommandError(str(e), category) from e
                return default_return

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except CarlosCommandError:
                raise
            except Exception as e:
                log_error(e, operation, category)
                if reraise:
                    raise CarlosCommandError(str(e), category) from e
                return default_return

        if hasattr(func, "__code__") and func.__code__.co_flags & 0x80:
            return async_wrapper
        return sync_wrapper

    return decorator


# Configuración de retry para diferentes servicios
def retry_notion():
    """Retry configurado para llamadas a Notion API."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


def retry_telegram():
    """Retry configurado para llamadas a Telegram API."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


def retry_gemini():
    """Retry configurado para llamadas a Gemini API."""
    return retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


def safe_execute(
    func: Callable[..., T],
    *args,
    default: T | None = None,
    operation: str = "unknown",
    **kwargs,
) -> T | None:
    """
    Ejecuta una función de forma segura, capturando errores.

    Args:
        func: Función a ejecutar
        *args: Argumentos posicionales
        default: Valor por defecto si hay error
        operation: Nombre de la operación para logging
        **kwargs: Argumentos con nombre

    Returns:
        Resultado de la función o el valor por defecto
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        log_error(e, operation)
        return default
