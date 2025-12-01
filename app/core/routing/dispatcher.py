"""
Intent Dispatcher - Punto de entrada unificado para procesamiento de mensajes.

Este módulo usa el UnifiedOrchestrator para:
1. Clasificar intenciones
2. Enriquecer con agentes especializados
3. Despachar al handler correcto con TODA la información
4. Proporcionar feedback visual durante procesamiento
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


# Constantes de feedback
PROCESSING_MESSAGES = {
    "analyzing": "🔄 Analizando mensaje...",
    "task_create": "📝 Preparando tarea...",
    "task_query": "🔍 Buscando tareas...",
    "expense_analyze": "💰 Analizando compra...",
    "project_create": "📁 Creando proyecto...",
    "reminder_create": "⏰ Configurando recordatorio...",
    "plan_tomorrow": "📋 Planificando...",
}


async def _handle_custom_reminder_time(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
) -> None:
    """Procesa la hora personalizada de un recordatorio."""
    import re
    from datetime import datetime, timedelta
    from app.services.reminder_service import get_reminder_service

    pending = context.user_data.get("pending_reminder", {})
    reminder_text = pending.get("text", "")

    if not reminder_text:
        context.user_data.pop("awaiting_reminder_time", None)
        await update.message.reply_text("❌ No hay recordatorio pendiente.")
        return

    # Parsear hora del mensaje
    now = datetime.now()
    scheduled_at = None
    text_lower = text.lower()

    # Patrones: "en X horas/minutos"
    match = re.search(r"en\s+(\d+)\s*(hora|horas|h|minuto|minutos|min|m)", text_lower)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        if unit.startswith("h"):
            scheduled_at = now + timedelta(hours=amount)
        else:
            scheduled_at = now + timedelta(minutes=amount)

    # Patrones: "mañana a las X"
    if not scheduled_at and "mañana" in text_lower:
        hour_match = re.search(r"(\d{1,2})(?::(\d{2}))?(?:\s*(am|pm))?", text_lower)
        if hour_match:
            hour = int(hour_match.group(1))
            minute = int(hour_match.group(2) or 0)
            ampm = hour_match.group(3)
            if ampm == "pm" and hour < 12:
                hour += 12
            scheduled_at = (now + timedelta(days=1)).replace(hour=hour, minute=minute, second=0)
        else:
            scheduled_at = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0)

    # Patrones: "a las X"
    if not scheduled_at:
        hour_match = re.search(r"(?:a\s+las?\s+)?(\d{1,2})(?::(\d{2}))?(?:\s*(am|pm))?", text_lower)
        if hour_match:
            hour = int(hour_match.group(1))
            minute = int(hour_match.group(2) or 0)
            ampm = hour_match.group(3)
            if ampm == "pm" and hour < 12:
                hour += 12
            scheduled_at = now.replace(hour=hour, minute=minute, second=0)
            # Si la hora ya pasó, poner para mañana
            if scheduled_at <= now:
                scheduled_at += timedelta(days=1)

    # Patrones: días de la semana
    days = {
        "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2,
        "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6
    }
    for day_name, day_num in days.items():
        if day_name in text_lower and not scheduled_at:
            days_ahead = day_num - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            scheduled_at = (now + timedelta(days=days_ahead)).replace(hour=9, minute=0, second=0)
            # Buscar hora específica
            hour_match = re.search(r"(\d{1,2})(?::(\d{2}))?(?:\s*(am|pm))?", text_lower)
            if hour_match:
                hour = int(hour_match.group(1))
                minute = int(hour_match.group(2) or 0)
                ampm = hour_match.group(3)
                if ampm == "pm" and hour < 12:
                    hour += 12
                scheduled_at = scheduled_at.replace(hour=hour, minute=minute)
            break

    if not scheduled_at:
        await update.message.reply_html(
            "🤔 No entendí cuándo quieres el recordatorio.\n\n"
            "Ejemplos:\n"
            "• \"en 2 horas\"\n"
            "• \"mañana a las 10\"\n"
            "• \"el viernes a las 3pm\"\n\n"
            "Escribe /cancel para cancelar."
        )
        return

    # Crear el recordatorio
    try:
        chat_id = str(update.effective_chat.id)
        user_id = str(update.effective_user.id)
        service = get_reminder_service()

        await service.create_reminder(
            chat_id=chat_id,
            user_id=user_id,
            title=reminder_text,
            scheduled_at=scheduled_at,
        )

        time_str = scheduled_at.strftime("%H:%M del %d/%m")
        await update.message.reply_html(
            f"✅ <b>Recordatorio creado</b>\n\n"
            f"<i>{reminder_text}</i>\n\n"
            f"⏰ Te recordaré: {time_str}"
        )

        # Limpiar estado
        context.user_data.pop("pending_reminder", None)
        context.user_data.pop("awaiting_reminder_time", None)

    except Exception as e:
        logger.error(f"Error creando recordatorio personalizado: {e}")
        await update.message.reply_text("❌ Error creando el recordatorio. Intenta de nuevo.")


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
    Handler principal de mensajes usando el UnifiedOrchestrator.

    Flujo:
    1. Enviar feedback visual (mensaje de procesamiento)
    2. Usar UnifiedOrchestrator para clasificar y enriquecer
    3. Despachar al handler con TODA la información
    4. Actualizar mensaje de feedback con resultado
    """
    processing_msg = None

    try:
        text = update.message.text
        user = update.effective_user
        user_id = user.id

        logger.info(f"Mensaje de {user_id}: {text[:50]}...")

        # Verificar si estamos esperando hora personalizada de recordatorio
        if context.user_data.get("awaiting_reminder_time"):
            await _handle_custom_reminder_time(update, context, text)
            return

        # 1. Enviar feedback visual inmediato
        try:
            processing_msg = await update.message.reply_text(
                PROCESSING_MESSAGES["analyzing"]
            )
        except Exception:
            processing_msg = None

        # 2. Usar UnifiedOrchestrator
        from app.agents.unified_orchestrator import get_unified_orchestrator
        from app.agents.intent_router import IntentResult
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        orchestrator = get_unified_orchestrator()

        try:
            response = await orchestrator.process_message(
                user_id=user_id,
                message=text,
            )

            # Actualizar feedback según el intent
            if processing_msg and response.intent:
                feedback_key = response.intent.value
                if feedback_key in PROCESSING_MESSAGES:
                    try:
                        await processing_msg.edit_text(PROCESSING_MESSAGES[feedback_key])
                    except Exception:
                        pass

            # Si ya fue manejado por el orquestador (contextual)
            if response.already_handled:
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

                # Eliminar mensaje de procesamiento y enviar respuesta
                if processing_msg:
                    try:
                        await processing_msg.delete()
                    except Exception:
                        pass

                await update.message.reply_html(
                    response.message,
                    reply_markup=keyboard,
                )
                return

            # 3. Construir IntentResult ENRIQUECIDO con toda la información
            # Usar el nuevo método get_enriched_entities() que combina entities + enrichment
            entities = response.get_enriched_entities()

            intent_result = IntentResult(
                intent=response.intent,
                confidence=response.confidence,
                entities=entities,
                suggested_response=None,
                raw_message=text,
            )

            # 4. Guardar mensaje en contexto para futuras clasificaciones
            last_messages = context.user_data.get("last_messages_list", [])
            last_messages.append(text[:100])
            if len(last_messages) > 5:
                last_messages = last_messages[-5:]
            context.user_data["last_messages_list"] = last_messages
            context.user_data["last_messages"] = " | ".join(last_messages)

            # Guardar enrichment para el handler
            enrichment = response.enrichment
            context.user_data["current_enrichment"] = {
                "enricher": enrichment.enricher_name if enrichment else None,
                # Task data (combinado de campos de tareas)
                "complexity": enrichment.complexity if enrichment else None,
                "subtasks": enrichment.subtasks if enrichment else [],
                "blockers": enrichment.blockers if enrichment else [],
                "suggested_priority": enrichment.suggested_priority if enrichment else None,
                # Planning data
                "planning_data": enrichment.planning_data if enrichment else None,
                # Fitness data
                "workout_data": enrichment.workout_data if enrichment else None,
                "nutrition_data": enrichment.nutrition_data if enrichment else None,
                # Finance data
                "financial_analysis": enrichment.financial_analysis if enrichment else None,
                # Project data
                "project_match": enrichment.project_match if enrichment else None,
                # Metadata
                "agents_used": response.agents_used,
                "processing_time_ms": response.processing_time_ms,
            }

            # Log de la clasificación
            logger.info(
                f"Intent: {intent_result.intent.value}, "
                f"Confidence: {intent_result.confidence:.2f}, "
                f"Entities: {intent_result.entities}, "
                f"Agents: {response.agents_used}"
            )

            # 5. Despachar usando el registry (eliminar mensaje de procesamiento)
            if processing_msg:
                try:
                    await processing_msg.delete()
                except Exception:
                    pass

            await dispatch_intent(update, context, intent_result)

        except Exception as e:
            logger.warning(f"UnifiedOrchestrator falló, usando fallback: {e}")

            # Fallback: Usar IntentRouter directamente
            from app.agents.intent_router import get_intent_router

            router = get_intent_router()
            conversation_context = context.user_data.get("last_messages", "")

            try:
                intent_result = await router.execute(text, conversation_context)
            except Exception as e2:
                logger.exception(f"Error en IntentRouter, usando fallback: {e2}")
                intent_result = await router.get_fallback_intent(text)

            # Eliminar mensaje de procesamiento
            if processing_msg:
                try:
                    await processing_msg.delete()
                except Exception:
                    pass

            await dispatch_intent(update, context, intent_result)

    except Exception as e:
        logger.exception(f"Error en handle_message_with_registry: {e}")

        # Limpiar mensaje de procesamiento
        if processing_msg:
            try:
                await processing_msg.delete()
            except Exception:
                pass

        await update.message.reply_text(
            "Ocurrió un error procesando tu mensaje. Por favor intenta de nuevo."
        )
