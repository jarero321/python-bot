"""Repository para manejo de estado de conversaciones."""

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConversationState

logger = logging.getLogger(__name__)


class ConversationStateRepository:
    """Repository para operaciones CRUD de ConversationState."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_chat_id(self, chat_id: str) -> ConversationState | None:
        """Obtiene el estado de conversación por chat_id."""
        result = await self.session.execute(
            select(ConversationState).where(ConversationState.chat_id == chat_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        chat_id: str,
        user_id: str,
        current_flow: str | None = None,
        current_step: str | None = None,
        flow_data: dict[str, Any] | None = None,
    ) -> ConversationState:
        """Crea un nuevo estado de conversación."""
        state = ConversationState(
            chat_id=chat_id,
            user_id=user_id,
            current_flow=current_flow,
            current_step=current_step,
            flow_data=json.dumps(flow_data) if flow_data else None,
        )
        self.session.add(state)
        await self.session.flush()
        logger.info(f"Estado de conversación creado para chat_id={chat_id}")
        return state

    async def update_flow(
        self,
        chat_id: str,
        flow: str | None,
        step: str | None = None,
        flow_data: dict[str, Any] | None = None,
    ) -> ConversationState | None:
        """Actualiza el flujo actual de una conversación."""
        state = await self.get_by_chat_id(chat_id)
        if state:
            state.current_flow = flow
            state.current_step = step
            state.flow_data = json.dumps(flow_data) if flow_data else None
            state.updated_at = datetime.utcnow()
            await self.session.flush()
            logger.debug(f"Flujo actualizado: chat_id={chat_id}, flow={flow}")
        return state

    async def update_last_message(
        self,
        chat_id: str,
        message: str,
        intent: str | None = None,
    ) -> ConversationState | None:
        """Actualiza el último mensaje recibido."""
        state = await self.get_by_chat_id(chat_id)
        if state:
            state.last_message = message
            state.last_intent = intent
            state.updated_at = datetime.utcnow()
            await self.session.flush()
        return state

    async def clear_flow(self, chat_id: str) -> ConversationState | None:
        """Limpia el flujo actual."""
        return await self.update_flow(chat_id, flow=None, step=None, flow_data=None)

    async def get_or_create(
        self, chat_id: str, user_id: str
    ) -> tuple[ConversationState, bool]:
        """Obtiene o crea un estado de conversación."""
        state = await self.get_by_chat_id(chat_id)
        if state:
            return state, False
        state = await self.create(chat_id=chat_id, user_id=user_id)
        return state, True

    def get_flow_data(self, state: ConversationState) -> dict[str, Any]:
        """Deserializa los datos del flujo."""
        if state.flow_data:
            return json.loads(state.flow_data)
        return {}
