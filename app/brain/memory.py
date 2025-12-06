"""
Memory System para Carlos Brain.

Tres niveles de memoria:
1. Working Memory: Sesión actual (2h TTL)
2. Short-term Memory: Últimas N conversaciones
3. Long-term Memory: RAG + patrones aprendidos
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, delete, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session

logger = logging.getLogger(__name__)


@dataclass
class ActiveEntity:
    """Entidad actualmente en foco de la conversación."""
    type: str  # task, project, reminder, etc.
    id: str
    title: str
    data: dict = field(default_factory=dict)


@dataclass
class WorkingMemory:
    """
    Memoria de trabajo - Sesión actual.

    Mantiene el contexto inmediato de la conversación:
    - Entidad activa (la tarea/proyecto que estamos discutiendo)
    - Modo de conversación
    - Pregunta pendiente (si esperamos respuesta)
    """

    user_id: str
    active_entity: ActiveEntity | None = None
    conversation_mode: str | None = None  # task_management, planning, finance, casual
    pending_question: dict | None = None  # {question, options, callback_action}
    last_action: str | None = None
    last_action_at: datetime | None = None

    def set_active_entity(
        self,
        entity_type: str,
        entity_id: str,
        title: str,
        data: dict | None = None
    ) -> None:
        """Establece la entidad activa en la conversación."""
        self.active_entity = ActiveEntity(
            type=entity_type,
            id=entity_id,
            title=title,
            data=data or {}
        )
        self.last_action = f"set_active_{entity_type}"
        self.last_action_at = datetime.now()

    def clear_active_entity(self) -> None:
        """Limpia la entidad activa."""
        self.active_entity = None

    def set_pending_question(
        self,
        question: str,
        options: list[str],
        callback_action: str
    ) -> None:
        """Establece una pregunta pendiente."""
        self.pending_question = {
            "question": question,
            "options": options,
            "callback_action": callback_action,
            "asked_at": datetime.now().isoformat()
        }

    def clear_pending_question(self) -> None:
        """Limpia la pregunta pendiente."""
        self.pending_question = None

    def to_context(self) -> dict:
        """Convierte a diccionario para pasar al LLM."""
        return {
            "active_entity": {
                "type": self.active_entity.type,
                "id": self.active_entity.id,
                "title": self.active_entity.title,
                "data": self.active_entity.data
            } if self.active_entity else None,
            "conversation_mode": self.conversation_mode,
            "pending_question": self.pending_question,
            "last_action": self.last_action,
        }


@dataclass
class ConversationMessage:
    """Un mensaje en el historial de conversación."""
    role: str  # user, assistant, system
    content: str
    timestamp: datetime
    trigger_type: str | None = None
    intent_detected: str | None = None
    entities: dict | None = None


class MemoryManager:
    """
    Gestiona los tres niveles de memoria del Brain.

    Uso:
        memory = MemoryManager(user_id)
        await memory.load()

        # Working memory
        memory.working.set_active_entity("task", "uuid", "Mi tarea")

        # Short-term (automático al conversar)
        await memory.add_message("user", "Hola")
        await memory.add_message("assistant", "Hola! ¿En qué te ayudo?")

        # Guardar estado
        await memory.save()
    """

    def __init__(self, user_id: str, short_term_limit: int = 20):
        self.user_id = user_id
        self.short_term_limit = short_term_limit

        # Memorias
        self.working = WorkingMemory(user_id=user_id)
        self.short_term: list[ConversationMessage] = []

    async def load(self) -> None:
        """Carga el estado de memoria desde la BD."""
        async with get_session() as session:
            # Cargar working memory
            await self._load_working_memory(session)

            # Cargar short-term memory
            await self._load_short_term(session)

    async def save(self) -> None:
        """Guarda el estado de memoria en la BD."""
        async with get_session() as session:
            await self._save_working_memory(session)
            await session.commit()

    async def add_message(
        self,
        role: str,
        content: str,
        trigger_type: str | None = None,
        intent: str | None = None,
        entities: dict | None = None,
        save_to_db: bool = True
    ) -> None:
        """Agrega un mensaje al historial."""
        message = ConversationMessage(
            role=role,
            content=content,
            timestamp=datetime.now(),
            trigger_type=trigger_type,
            intent_detected=intent,
            entities=entities
        )

        self.short_term.append(message)

        # Mantener límite
        if len(self.short_term) > self.short_term_limit:
            self.short_term = self.short_term[-self.short_term_limit:]

        # Guardar en BD
        if save_to_db:
            async with get_session() as session:
                await self._save_message(session, message)
                await session.commit()

    def get_context_for_llm(self) -> dict:
        """
        Genera el contexto completo para pasar al LLM.

        Incluye:
        - Working memory (entidad activa, modo, pregunta pendiente)
        - Short-term memory (últimas conversaciones)
        """
        return {
            "working_memory": self.working.to_context(),
            "recent_messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                }
                for msg in self.short_term[-10:]  # Últimos 10 para el LLM
            ],
            "session_summary": self._generate_session_summary()
        }

    def _generate_session_summary(self) -> str:
        """Genera un resumen de la sesión actual."""
        if not self.short_term:
            return "Nueva sesión, sin historial reciente."

        user_messages = [m for m in self.short_term if m.role == "user"]

        if not user_messages:
            return "Sesión iniciada por sistema (trigger automático)."

        # Resumen básico
        summary_parts = [f"Sesión con {len(self.short_term)} mensajes."]

        if self.working.active_entity:
            summary_parts.append(
                f"Entidad activa: {self.working.active_entity.type} "
                f"'{self.working.active_entity.title}'"
            )

        if self.working.pending_question:
            summary_parts.append("Hay una pregunta pendiente de respuesta.")

        return " ".join(summary_parts)

    # ==================== Private DB Methods ====================

    async def _load_working_memory(self, session: AsyncSession) -> None:
        """Carga working memory desde BD."""
        from app.db.models import WorkingMemoryModel

        result = await session.execute(
            select(WorkingMemoryModel)
            .where(WorkingMemoryModel.user_id == self.user_id)
            .where(WorkingMemoryModel.expires_at > datetime.now())
        )
        row = result.scalar_one_or_none()

        if row:
            if row.active_entity_type and row.active_entity_id:
                self.working.active_entity = ActiveEntity(
                    type=row.active_entity_type,
                    id=str(row.active_entity_id),
                    title=row.active_entity_data.get("title", "") if row.active_entity_data else "",
                    data=row.active_entity_data or {}
                )
            self.working.conversation_mode = row.conversation_mode
            self.working.pending_question = row.pending_question
            self.working.last_action = row.last_action

    async def _save_working_memory(self, session: AsyncSession) -> None:
        """Guarda working memory en BD."""
        from app.db.models import WorkingMemoryModel

        # Buscar existente
        result = await session.execute(
            select(WorkingMemoryModel)
            .where(WorkingMemoryModel.user_id == self.user_id)
        )
        existing = result.scalar_one_or_none()

        expires_at = datetime.now() + timedelta(hours=2)

        if existing:
            # Actualizar
            existing.active_entity_type = self.working.active_entity.type if self.working.active_entity else None
            existing.active_entity_id = self.working.active_entity.id if self.working.active_entity else None
            existing.active_entity_data = self.working.active_entity.data if self.working.active_entity else None
            existing.conversation_mode = self.working.conversation_mode
            existing.pending_question = self.working.pending_question
            existing.last_action = self.working.last_action
            existing.expires_at = expires_at
        else:
            # Crear nuevo
            new_memory = WorkingMemoryModel(
                user_id=self.user_id,
                active_entity_type=self.working.active_entity.type if self.working.active_entity else None,
                active_entity_id=self.working.active_entity.id if self.working.active_entity else None,
                active_entity_data=self.working.active_entity.data if self.working.active_entity else None,
                conversation_mode=self.working.conversation_mode,
                pending_question=self.working.pending_question,
                last_action=self.working.last_action,
                expires_at=expires_at
            )
            session.add(new_memory)

    async def _load_short_term(self, session: AsyncSession) -> None:
        """Carga los últimos N mensajes."""
        from app.db.models import ConversationHistoryModel

        result = await session.execute(
            select(ConversationHistoryModel)
            .where(ConversationHistoryModel.user_id == self.user_id)
            .order_by(desc(ConversationHistoryModel.timestamp))
            .limit(self.short_term_limit)
        )
        rows = result.scalars().all()

        # Invertir para orden cronológico
        self.short_term = [
            ConversationMessage(
                role=row.role,
                content=row.content,
                timestamp=row.timestamp,
                trigger_type=row.trigger_type,
                intent_detected=row.intent_detected,
                entities=row.entities_extracted
            )
            for row in reversed(rows)
        ]

    async def _save_message(self, session: AsyncSession, message: ConversationMessage) -> None:
        """Guarda un mensaje en el historial."""
        from app.db.models import ConversationHistoryModel

        new_msg = ConversationHistoryModel(
            user_id=self.user_id,
            role=message.role,
            content=message.content,
            trigger_type=message.trigger_type,
            intent_detected=message.intent_detected,
            entities_extracted=message.entities,
            timestamp=message.timestamp
        )
        session.add(new_msg)

    async def clear_working_memory(self) -> None:
        """Limpia la working memory (fin de sesión)."""
        self.working = WorkingMemory(user_id=self.user_id)
        async with get_session() as session:
            from app.db.models import WorkingMemoryModel
            await session.execute(
                delete(WorkingMemoryModel)
                .where(WorkingMemoryModel.user_id == self.user_id)
            )
            await session.commit()


# ==================== RAG / Long-term Memory ====================

class LongTermMemory:
    """
    Memoria a largo plazo usando RAG.

    Permite:
    - Buscar tareas/proyectos similares
    - Detectar duplicados
    - Aprender patrones del usuario
    """

    def __init__(self, user_id: str):
        self.user_id = user_id

    async def search_similar_tasks(
        self,
        query: str,
        limit: int = 5,
        min_similarity: float = 0.5
    ) -> list[dict]:
        """Busca tareas similares usando embeddings."""
        from app.brain.embeddings import get_embedding

        query_embedding = await get_embedding(query)

        async with get_session() as session:
            # Usar pgvector para búsqueda
            result = await session.execute(f"""
                SELECT id, title, status, context, project_id,
                       1 - (embedding <=> :query_embedding) as similarity
                FROM tasks
                WHERE user_id = :user_id
                  AND embedding IS NOT NULL
                  AND 1 - (embedding <=> :query_embedding) > :min_similarity
                ORDER BY embedding <=> :query_embedding
                LIMIT :limit
            """, {
                "query_embedding": query_embedding,
                "user_id": self.user_id,
                "min_similarity": min_similarity,
                "limit": limit
            })

            return [
                {
                    "id": row.id,
                    "title": row.title,
                    "status": row.status,
                    "context": row.context,
                    "similarity": row.similarity
                }
                for row in result
            ]

    async def find_duplicates(
        self,
        title: str,
        threshold: float = 0.85
    ) -> list[dict]:
        """Encuentra posibles duplicados de una tarea."""
        similar = await self.search_similar_tasks(
            query=title,
            limit=3,
            min_similarity=threshold
        )
        return [s for s in similar if s["status"] not in ("done", "cancelled")]

    async def infer_context(self, text: str) -> tuple[str | None, float]:
        """
        Infiere el contexto de un texto basándose en patrones aprendidos.

        Returns:
            (contexto, confianza)
        """
        async with get_session() as session:
            # Buscar patrones que coincidan
            from app.db.models import LearnedPatternModel

            result = await session.execute(
                select(LearnedPatternModel)
                .where(LearnedPatternModel.user_id == self.user_id)
                .where(LearnedPatternModel.pattern_type == "context_inference")
            )
            patterns = result.scalars().all()

            text_lower = text.lower()
            best_match = None
            best_confidence = 0.0

            for pattern in patterns:
                if pattern.pattern_key.lower() in text_lower:
                    if pattern.confidence > best_confidence:
                        best_match = pattern.pattern_value
                        best_confidence = pattern.confidence

            return best_match, best_confidence

    async def learn_pattern(
        self,
        pattern_type: str,
        key: str,
        value: str,
        confidence_boost: float = 0.1
    ) -> None:
        """Aprende o refuerza un patrón."""
        async with get_session() as session:
            from app.db.models import LearnedPatternModel

            result = await session.execute(
                select(LearnedPatternModel)
                .where(LearnedPatternModel.user_id == self.user_id)
                .where(LearnedPatternModel.pattern_type == pattern_type)
                .where(LearnedPatternModel.pattern_key == key)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Reforzar patrón existente
                existing.occurrences += 1
                existing.confidence = min(0.99, existing.confidence + confidence_boost)
                if existing.pattern_value != value:
                    # Si el valor cambió, bajar confianza
                    existing.confidence = max(0.5, existing.confidence - 0.2)
                    existing.pattern_value = value
            else:
                # Crear nuevo patrón
                new_pattern = LearnedPatternModel(
                    user_id=self.user_id,
                    pattern_type=pattern_type,
                    pattern_key=key,
                    pattern_value=value,
                    confidence=0.6,
                    occurrences=1
                )
                session.add(new_pattern)

            await session.commit()
