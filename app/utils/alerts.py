"""Sistema de alertas para errores críticos via Telegram."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any
from collections import defaultdict

from app.config import get_settings
from app.utils.errors import ErrorCategory, ErrorContext

logger = logging.getLogger(__name__)
settings = get_settings()

# Rate limiting para evitar spam de alertas
_alert_counts: dict[str, list[datetime]] = defaultdict(list)
_RATE_LIMIT_WINDOW = timedelta(minutes=5)
_MAX_ALERTS_PER_WINDOW = 3


class AlertLevel:
    """Niveles de alerta."""

    CRITICAL = "critical"  # Errores que rompen funcionalidad
    WARNING = "warning"    # Errores recuperables pero importantes
    INFO = "info"          # Información relevante


# Categorías que disparan alertas críticas
CRITICAL_CATEGORIES = {
    ErrorCategory.API_NOTION,
    ErrorCategory.API_TELEGRAM,
    ErrorCategory.API_GEMINI,
    ErrorCategory.DATABASE,
    ErrorCategory.SCHEDULER,
}


def _is_rate_limited(error_key: str) -> bool:
    """Verifica si una alerta está limitada por rate limit."""
    now = datetime.now()
    cutoff = now - _RATE_LIMIT_WINDOW

    # Limpiar alertas antiguas
    _alert_counts[error_key] = [
        ts for ts in _alert_counts[error_key] if ts > cutoff
    ]

    # Verificar límite
    if len(_alert_counts[error_key]) >= _MAX_ALERTS_PER_WINDOW:
        return True

    # Registrar esta alerta
    _alert_counts[error_key].append(now)
    return False


def _format_alert_message(
    context: ErrorContext,
    level: str = AlertLevel.CRITICAL,
) -> str:
    """Formatea un mensaje de alerta para Telegram."""
    emoji_map = {
        AlertLevel.CRITICAL: "🚨",
        AlertLevel.WARNING: "⚠️",
        AlertLevel.INFO: "ℹ️",
    }

    emoji = emoji_map.get(level, "🔔")

    message_parts = [
        f"{emoji} <b>ALERTA {level.upper()}</b> {emoji}",
        "",
        f"<b>Categoría:</b> {context.category.value}",
        f"<b>Operación:</b> {context.operation}",
        f"<b>Error:</b> {context.error_type}",
        "",
        f"<b>Mensaje:</b>",
        f"<code>{context.message[:500]}</code>",
    ]

    if context.details:
        message_parts.extend([
            "",
            "<b>Detalles:</b>",
        ])
        for key, value in list(context.details.items())[:5]:
            message_parts.append(f"• {key}: {str(value)[:100]}")

    message_parts.extend([
        "",
        f"<i>Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>",
    ])

    return "\n".join(message_parts)


async def send_alert(
    context: ErrorContext,
    level: str = AlertLevel.CRITICAL,
    force: bool = False,
) -> bool:
    """
    Envía una alerta a Telegram.

    Args:
        context: Contexto del error
        level: Nivel de alerta
        force: Si True, ignora rate limiting

    Returns:
        True si se envió la alerta
    """
    # Importar aquí para evitar circular imports
    from app.services.telegram import get_telegram_service

    # Generar clave única para rate limiting
    error_key = f"{context.category.value}:{context.operation}:{context.error_type}"

    # Verificar rate limit
    if not force and _is_rate_limited(error_key):
        logger.debug(f"Alerta rate-limited: {error_key}")
        return False

    try:
        telegram = get_telegram_service()
        message = _format_alert_message(context, level)

        success = await telegram.send_message(message)

        if success:
            logger.info(f"Alerta enviada: {error_key}")
        else:
            logger.error(f"Fallo al enviar alerta: {error_key}")

        return success

    except Exception as e:
        logger.error(f"Error enviando alerta: {e}")
        return False


async def alert_critical_error(
    error: Exception,
    operation: str,
    category: ErrorCategory,
    extra: dict[str, Any] | None = None,
) -> ErrorContext:
    """
    Registra un error crítico y envía alerta.

    Args:
        error: La excepción
        operation: Operación que falló
        category: Categoría del error
        extra: Información adicional

    Returns:
        ErrorContext del error
    """
    from app.utils.errors import log_error

    # Registrar error
    context = log_error(error, operation, category, extra)

    # Enviar alerta si es categoría crítica
    if category in CRITICAL_CATEGORIES:
        await send_alert(context, AlertLevel.CRITICAL)

    return context


def sync_alert_critical_error(
    error: Exception,
    operation: str,
    category: ErrorCategory,
    extra: dict[str, Any] | None = None,
) -> ErrorContext:
    """
    Versión síncrona de alert_critical_error.
    Útil para contextos donde no hay event loop activo.
    """
    from app.utils.errors import log_error

    context = log_error(error, operation, category, extra)

    if category in CRITICAL_CATEGORIES:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(send_alert(context, AlertLevel.CRITICAL))
            else:
                loop.run_until_complete(send_alert(context, AlertLevel.CRITICAL))
        except RuntimeError:
            # No hay event loop, intentar crear uno
            asyncio.run(send_alert(context, AlertLevel.CRITICAL))

    return context


async def send_startup_alert() -> bool:
    """Envía alerta de inicio del sistema."""
    from app.services.telegram import get_telegram_service

    try:
        telegram = get_telegram_service()
        message = (
            "🟢 <b>Carlos Command Iniciado</b>\n\n"
            f"<b>Ambiente:</b> {settings.app_env}\n"
            f"<b>Timestamp:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "<i>Sistema listo para recibir comandos.</i>"
        )
        return await telegram.send_message(message)
    except Exception as e:
        logger.error(f"Error enviando alerta de inicio: {e}")
        return False


async def send_shutdown_alert(reason: str = "normal") -> bool:
    """Envía alerta de apagado del sistema."""
    from app.services.telegram import get_telegram_service

    try:
        telegram = get_telegram_service()
        emoji = "🔴" if reason != "normal" else "🟡"
        message = (
            f"{emoji} <b>Carlos Command Detenido</b>\n\n"
            f"<b>Razón:</b> {reason}\n"
            f"<b>Timestamp:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return await telegram.send_message(message)
    except Exception as e:
        logger.error(f"Error enviando alerta de apagado: {e}")
        return False


async def send_health_alert(status: str, details: dict[str, Any]) -> bool:
    """Envía alerta de estado de salud del sistema."""
    from app.services.telegram import get_telegram_service

    try:
        telegram = get_telegram_service()

        emoji = "🟢" if status == "healthy" else "🔴" if status == "unhealthy" else "🟡"

        message_parts = [
            f"{emoji} <b>Health Check: {status.upper()}</b>",
            "",
        ]

        for service, info in details.items():
            service_status = info.get("status", "unknown")
            service_emoji = "✅" if service_status == "ok" else "❌"
            message_parts.append(f"{service_emoji} <b>{service}:</b> {service_status}")
            if "error" in info:
                message_parts.append(f"   └─ {info['error'][:100]}")

        message_parts.extend([
            "",
            f"<i>Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>",
        ])

        return await telegram.send_message("\n".join(message_parts))
    except Exception as e:
        logger.error(f"Error enviando alerta de health: {e}")
        return False
