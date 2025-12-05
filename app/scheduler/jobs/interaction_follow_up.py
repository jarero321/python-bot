"""
Job de seguimiento de interacciones ignoradas.

Revisa periódicamente si hay mensajes sin respuesta y hace seguimiento.
"""

import json
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.telegram import get_telegram_service
from app.services.interaction_tracker import get_interaction_tracker

logger = logging.getLogger(__name__)


async def check_pending_interactions_job() -> None:
    """
    Revisa interacciones pendientes y envía seguimiento si es necesario.

    Se ejecuta cada 15-30 minutos para detectar mensajes ignorados.
    """
    logger.info("Verificando interacciones pendientes...")

    tracker = get_interaction_tracker()
    telegram = get_telegram_service()

    try:
        # Obtener interacciones que necesitan seguimiento
        pending = await tracker.get_pending_for_follow_up()

        if not pending:
            logger.debug("No hay interacciones pendientes de seguimiento")
            return

        logger.info(f"Encontradas {len(pending)} interacciones para seguimiento")

        for interaction in pending:
            try:
                # Obtener mensaje de seguimiento
                message = tracker.get_follow_up_message(
                    interaction.interaction_type,
                    interaction.follow_up_count,
                )

                # Construir contexto si existe
                context_data = {}
                if interaction.context:
                    try:
                        context_data = json.loads(interaction.context)
                    except json.JSONDecodeError:
                        pass

                # Personalizar mensaje según tipo
                if interaction.interaction_type == "checkin":
                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(
                                "👍 Estoy bien",
                                callback_data="followup_ok",
                            ),
                            InlineKeyboardButton(
                                "💼 Ocupado",
                                callback_data="followup_busy",
                            ),
                        ],
                        [
                            InlineKeyboardButton(
                                "🛑 No molestar hoy",
                                callback_data="followup_dnd",
                            ),
                        ],
                    ])
                else:
                    keyboard = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(
                                "✅ Ya lo vi",
                                callback_data="followup_acknowledged",
                            ),
                            InlineKeyboardButton(
                                "⏰ Más tarde",
                                callback_data="followup_later",
                            ),
                        ],
                    ])

                # Enviar seguimiento
                await telegram.send_message_with_keyboard(
                    text=message,
                    reply_markup=keyboard,
                    chat_id=interaction.chat_id,
                )

                # Incrementar contador
                await tracker.increment_follow_up(interaction.id)

                logger.info(
                    f"Seguimiento enviado para interacción {interaction.id} "
                    f"(intento {interaction.follow_up_count + 1})"
                )

            except Exception as e:
                logger.error(
                    f"Error enviando seguimiento para interacción {interaction.id}: {e}"
                )

    except Exception as e:
        logger.error(f"Error en check_pending_interactions_job: {e}")


async def cleanup_interactions_job() -> None:
    """Limpia interacciones antiguas (> 7 días)."""
    tracker = get_interaction_tracker()
    count = await tracker.cleanup_old_interactions(days=7)
    if count > 0:
        logger.info(f"Limpiadas {count} interacciones antiguas")
