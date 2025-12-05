"""
Servicio de tracking de interacciones pendientes.

Permite al bot:
- Registrar mensajes que esperan respuesta
- Detectar si el usuario ignoró un mensaje
- Hacer seguimiento proactivo
- Escalar si es necesario
"""

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import PendingInteraction

logger = logging.getLogger(__name__)


class InteractionTracker:
    """Rastrea interacciones pendientes con el usuario."""

    # Tiempos de seguimiento por tipo
    FOLLOW_UP_TIMES = {
        "checkin": timedelta(hours=1),  # Seguimiento después de 1 hora
        "reminder": timedelta(minutes=30),  # Más urgente
        "question": timedelta(hours=2),  # Menos urgente
        "task_prompt": timedelta(hours=1),
    }

    # Mensajes de seguimiento
    FOLLOW_UP_MESSAGES = {
        "checkin": [
            "Hey, ¿todo bien? No vi respuesta al check-in anterior.",
            "Solo verificando que sigas por ahí. ¿Cómo vas?",
        ],
        "reminder": [
            "El recordatorio sigue pendiente.",
            "Esto parece importante - ¿lo revisamos?",
        ],
        "question": [
            "¿Pudiste ver mi pregunta anterior?",
        ],
        "task_prompt": [
            "¿Decidiste qué tarea tomar?",
        ],
    }

    async def register_interaction(
        self,
        chat_id: str,
        message_id: int,
        interaction_type: str,
        context: dict | None = None,
        expires_in: timedelta | None = None,
    ) -> PendingInteraction:
        """
        Registra una interacción que espera respuesta.

        Args:
            chat_id: ID del chat
            message_id: ID del mensaje enviado
            interaction_type: Tipo de interacción (checkin, reminder, etc.)
            context: Datos adicionales para el seguimiento
            expires_in: Tiempo después del cual ya no hacer seguimiento
        """
        async with get_session() as session:
            # Calcular tiempos
            now = datetime.utcnow()
            follow_up_delta = self.FOLLOW_UP_TIMES.get(
                interaction_type, timedelta(hours=1)
            )

            interaction = PendingInteraction(
                chat_id=chat_id,
                message_id=message_id,
                interaction_type=interaction_type,
                context=json.dumps(context) if context else None,
                next_follow_up_at=now + follow_up_delta,
                expires_at=now + expires_in if expires_in else now + timedelta(hours=8),
            )

            session.add(interaction)
            await session.commit()
            await session.refresh(interaction)

            logger.info(
                f"Interacción registrada: {interaction_type} (msg_id={message_id})"
            )
            return interaction

    async def mark_responded(
        self,
        chat_id: str,
        message_id: int | None = None,
        response_type: str = "button_click",
    ) -> bool:
        """
        Marca interacciones como respondidas.

        Si message_id es None, marca la interacción pendiente más reciente.
        """
        async with get_session() as session:
            # Construir query
            if message_id:
                query = select(PendingInteraction).where(
                    and_(
                        PendingInteraction.chat_id == chat_id,
                        PendingInteraction.message_id == message_id,
                        PendingInteraction.responded == False,
                    )
                )
            else:
                # Obtener la más reciente no respondida
                query = (
                    select(PendingInteraction)
                    .where(
                        and_(
                            PendingInteraction.chat_id == chat_id,
                            PendingInteraction.responded == False,
                        )
                    )
                    .order_by(PendingInteraction.created_at.desc())
                    .limit(1)
                )

            result = await session.execute(query)
            interaction = result.scalar_one_or_none()

            if interaction:
                interaction.responded = True
                interaction.responded_at = datetime.utcnow()
                interaction.response_type = response_type
                await session.commit()
                logger.info(f"Interacción marcada como respondida: {interaction.id}")
                return True

            return False

    async def get_pending_for_follow_up(self) -> list[PendingInteraction]:
        """Obtiene interacciones que necesitan seguimiento."""
        async with get_session() as session:
            now = datetime.utcnow()

            query = select(PendingInteraction).where(
                and_(
                    PendingInteraction.responded == False,
                    PendingInteraction.next_follow_up_at <= now,
                    PendingInteraction.follow_up_count < PendingInteraction.max_follow_ups,
                    # No expiradas
                    (PendingInteraction.expires_at == None)
                    | (PendingInteraction.expires_at > now),
                )
            )

            result = await session.execute(query)
            return list(result.scalars().all())

    async def increment_follow_up(
        self, interaction_id: int
    ) -> None:
        """Incrementa el contador de seguimientos y programa el siguiente."""
        async with get_session() as session:
            query = select(PendingInteraction).where(
                PendingInteraction.id == interaction_id
            )
            result = await session.execute(query)
            interaction = result.scalar_one_or_none()

            if interaction:
                interaction.follow_up_count += 1
                # Siguiente seguimiento en el doble de tiempo
                delta = self.FOLLOW_UP_TIMES.get(
                    interaction.interaction_type, timedelta(hours=1)
                )
                interaction.next_follow_up_at = datetime.utcnow() + (
                    delta * (interaction.follow_up_count + 1)
                )
                await session.commit()

    def get_follow_up_message(
        self, interaction_type: str, follow_up_count: int
    ) -> str:
        """Obtiene el mensaje de seguimiento apropiado."""
        messages = self.FOLLOW_UP_MESSAGES.get(interaction_type, ["¿Sigues ahí?"])
        index = min(follow_up_count, len(messages) - 1)
        return messages[index]

    async def cleanup_old_interactions(self, days: int = 7) -> int:
        """Limpia interacciones antiguas."""
        async with get_session() as session:
            cutoff = datetime.utcnow() - timedelta(days=days)

            from sqlalchemy import delete

            query = delete(PendingInteraction).where(
                PendingInteraction.created_at < cutoff
            )
            result = await session.execute(query)
            await session.commit()

            count = result.rowcount
            if count > 0:
                logger.info(f"Limpiadas {count} interacciones antiguas")
            return count

    async def get_response_stats(self, chat_id: str, days: int = 7) -> dict:
        """Obtiene estadísticas de respuesta del usuario."""
        async with get_session() as session:
            cutoff = datetime.utcnow() - timedelta(days=days)

            from sqlalchemy import func

            # Total de interacciones
            total_query = select(func.count(PendingInteraction.id)).where(
                and_(
                    PendingInteraction.chat_id == chat_id,
                    PendingInteraction.created_at >= cutoff,
                )
            )
            total_result = await session.execute(total_query)
            total = total_result.scalar() or 0

            # Respondidas
            responded_query = select(func.count(PendingInteraction.id)).where(
                and_(
                    PendingInteraction.chat_id == chat_id,
                    PendingInteraction.created_at >= cutoff,
                    PendingInteraction.responded == True,
                )
            )
            responded_result = await session.execute(responded_query)
            responded = responded_result.scalar() or 0

            return {
                "total": total,
                "responded": responded,
                "ignored": total - responded,
                "response_rate": (responded / total * 100) if total > 0 else 0,
            }


# Singleton
_tracker: InteractionTracker | None = None


def get_interaction_tracker() -> InteractionTracker:
    """Obtiene la instancia del tracker."""
    global _tracker
    if _tracker is None:
        _tracker = InteractionTracker()
    return _tracker
