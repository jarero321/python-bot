"""Contexto conversacional para mantener estado entre mensajes."""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class EntityType(str, Enum):
    """Tipos de entidades que pueden estar en contexto."""
    TASK = "task"
    PROJECT = "project"
    REMINDER = "reminder"
    EXPENSE = "expense"
    WORKOUT = "workout"
    NUTRITION = "nutrition"
    DEBT = "debt"
    NONE = "none"


class ConversationState(str, Enum):
    """Estados de la conversación."""
    IDLE = "idle"                          # Sin contexto activo
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # Esperando sí/no
    AWAITING_SELECTION = "awaiting_selection"        # Esperando elegir opción
    AWAITING_INPUT = "awaiting_input"      # Esperando texto libre
    EDITING_ENTITY = "editing_entity"      # Editando una entidad
    REVIEWING_SUBTASKS = "reviewing_subtasks"  # Revisando subtareas


@dataclass
class ConversationMessage:
    """Un mensaje en el historial de conversación."""
    role: str  # "user" o "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    intent: str | None = None
    entities: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "intent": self.intent,
            "entities": self.entities,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConversationMessage":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            intent=data.get("intent"),
            entities=data.get("entities", {}),
        )


@dataclass
class ActiveEntity:
    """Entidad actualmente en contexto (última tarea, proyecto, etc.)."""
    entity_type: EntityType
    entity_id: str | None = None
    entity_name: str = ""
    entity_data: dict = field(default_factory=dict)
    subtasks: list[str] = field(default_factory=list)
    suggested_subtasks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type.value,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "entity_data": self.entity_data,
            "subtasks": self.subtasks,
            "suggested_subtasks": self.suggested_subtasks,
            "blockers": self.blockers,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ActiveEntity":
        return cls(
            entity_type=EntityType(data["entity_type"]),
            entity_id=data.get("entity_id"),
            entity_name=data.get("entity_name", ""),
            entity_data=data.get("entity_data", {}),
            subtasks=data.get("subtasks", []),
            suggested_subtasks=data.get("suggested_subtasks", []),
            blockers=data.get("blockers", []),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
        )


@dataclass
class PendingAction:
    """Acción pendiente que requiere confirmación o input adicional."""
    action_type: str  # "create_task", "add_subtasks", "confirm_delete", etc.
    target_entity: EntityType
    target_id: str | None = None
    data: dict = field(default_factory=dict)
    options: list[str] = field(default_factory=list)  # Para selección múltiple
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(minutes=5))

    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at

    def to_dict(self) -> dict:
        return {
            "action_type": self.action_type,
            "target_entity": self.target_entity.value,
            "target_id": self.target_id,
            "data": self.data,
            "options": self.options,
            "expires_at": self.expires_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PendingAction":
        return cls(
            action_type=data["action_type"],
            target_entity=EntityType(data["target_entity"]),
            target_id=data.get("target_id"),
            data=data.get("data", {}),
            options=data.get("options", []),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else datetime.now() + timedelta(minutes=5),
        )


@dataclass
class ConversationContext:
    """Contexto completo de una conversación con un usuario."""
    user_id: int
    state: ConversationState = ConversationState.IDLE
    history: list[ConversationMessage] = field(default_factory=list)
    active_entity: ActiveEntity | None = None
    pending_action: PendingAction | None = None
    last_intent: str | None = None
    last_activity: datetime = field(default_factory=datetime.now)

    # Límites
    MAX_HISTORY = 20  # Últimos 20 mensajes
    CONTEXT_TTL_MINUTES = 30  # Contexto expira después de 30 min de inactividad

    def add_message(self, role: str, content: str, intent: str | None = None, entities: dict | None = None):
        """Agrega un mensaje al historial."""
        msg = ConversationMessage(
            role=role,
            content=content,
            intent=intent,
            entities=entities or {},
        )
        self.history.append(msg)
        self.last_activity = datetime.now()

        # Mantener límite de historial
        if len(self.history) > self.MAX_HISTORY:
            self.history = self.history[-self.MAX_HISTORY:]

        # Actualizar último intent si es del usuario
        if role == "user" and intent:
            self.last_intent = intent

    def set_active_entity(
        self,
        entity_type: EntityType,
        entity_id: str | None = None,
        entity_name: str = "",
        entity_data: dict | None = None,
        subtasks: list[str] | None = None,
        suggested_subtasks: list[str] | None = None,
    ):
        """Establece la entidad activa en contexto."""
        self.active_entity = ActiveEntity(
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            entity_data=entity_data or {},
            subtasks=subtasks or [],
            suggested_subtasks=suggested_subtasks or [],
        )
        self.last_activity = datetime.now()

    def set_pending_action(
        self,
        action_type: str,
        target_entity: EntityType,
        target_id: str | None = None,
        data: dict | None = None,
        options: list[str] | None = None,
    ):
        """Establece una acción pendiente."""
        self.pending_action = PendingAction(
            action_type=action_type,
            target_entity=target_entity,
            target_id=target_id,
            data=data or {},
            options=options or [],
        )
        self.last_activity = datetime.now()

    def clear_pending_action(self):
        """Limpia la acción pendiente."""
        self.pending_action = None

    def clear_active_entity(self):
        """Limpia la entidad activa."""
        self.active_entity = None
        self.state = ConversationState.IDLE

    def is_context_expired(self) -> bool:
        """Verifica si el contexto ha expirado."""
        return datetime.now() - self.last_activity > timedelta(minutes=self.CONTEXT_TTL_MINUTES)

    def get_recent_history(self, limit: int = 5) -> list[ConversationMessage]:
        """Obtiene los últimos N mensajes."""
        return self.history[-limit:]

    def get_history_summary(self) -> str:
        """Genera un resumen del historial para el LLM."""
        if not self.history:
            return "Sin historial de conversación."

        recent = self.get_recent_history(5)
        lines = []
        for msg in recent:
            role = "Usuario" if msg.role == "user" else "Asistente"
            content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            lines.append(f"{role}: {content}")

        return "\n".join(lines)

    def get_context_summary(self) -> str:
        """Genera un resumen del contexto actual para el LLM."""
        parts = []

        if self.active_entity:
            parts.append(f"Entidad activa: {self.active_entity.entity_type.value} - {self.active_entity.entity_name}")
            if self.active_entity.subtasks:
                parts.append(f"Subtareas: {', '.join(self.active_entity.subtasks)}")
            if self.active_entity.suggested_subtasks:
                parts.append(f"Subtareas sugeridas: {', '.join(self.active_entity.suggested_subtasks)}")

        if self.pending_action and not self.pending_action.is_expired():
            parts.append(f"Acción pendiente: {self.pending_action.action_type}")

        if self.last_intent:
            parts.append(f"Última intención: {self.last_intent}")

        return " | ".join(parts) if parts else "Sin contexto activo"

    def to_dict(self) -> dict:
        """Serializa el contexto a diccionario."""
        return {
            "user_id": self.user_id,
            "state": self.state.value,
            "history": [msg.to_dict() for msg in self.history],
            "active_entity": self.active_entity.to_dict() if self.active_entity else None,
            "pending_action": self.pending_action.to_dict() if self.pending_action else None,
            "last_intent": self.last_intent,
            "last_activity": self.last_activity.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConversationContext":
        """Deserializa el contexto desde diccionario."""
        ctx = cls(
            user_id=data["user_id"],
            state=ConversationState(data.get("state", "idle")),
            last_intent=data.get("last_intent"),
            last_activity=datetime.fromisoformat(data["last_activity"]) if data.get("last_activity") else datetime.now(),
        )

        # Restaurar historial
        if data.get("history"):
            ctx.history = [ConversationMessage.from_dict(m) for m in data["history"]]

        # Restaurar entidad activa
        if data.get("active_entity"):
            ctx.active_entity = ActiveEntity.from_dict(data["active_entity"])

        # Restaurar acción pendiente
        if data.get("pending_action"):
            ctx.pending_action = PendingAction.from_dict(data["pending_action"])

        return ctx


class ConversationStore:
    """Almacén persistente de contextos de conversación."""

    def __init__(self, storage_path: str | None = None):
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            # Usar directorio data en el proyecto
            self.storage_path = Path(__file__).parent.parent.parent / "data" / "conversations.json"

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._contexts: dict[int, ConversationContext] = {}
        self._load()

    def _load(self):
        """Carga contextos desde archivo."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for user_id_str, ctx_data in data.items():
                        user_id = int(user_id_str)
                        self._contexts[user_id] = ConversationContext.from_dict(ctx_data)
                logger.info(f"Cargados {len(self._contexts)} contextos de conversación")
            except Exception as e:
                logger.error(f"Error cargando contextos: {e}")
                self._contexts = {}

    def _save(self):
        """Guarda contextos a archivo."""
        try:
            data = {
                str(user_id): ctx.to_dict()
                for user_id, ctx in self._contexts.items()
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error guardando contextos: {e}")

    def get(self, user_id: int) -> ConversationContext:
        """Obtiene el contexto de un usuario (crea uno nuevo si no existe)."""
        if user_id not in self._contexts:
            self._contexts[user_id] = ConversationContext(user_id=user_id)

        ctx = self._contexts[user_id]

        # Limpiar contexto si expiró
        if ctx.is_context_expired():
            ctx.clear_active_entity()
            ctx.clear_pending_action()
            ctx.state = ConversationState.IDLE

        return ctx

    def save(self, context: ConversationContext):
        """Guarda un contexto."""
        self._contexts[context.user_id] = context
        self._save()

    def clear(self, user_id: int):
        """Limpia el contexto de un usuario."""
        if user_id in self._contexts:
            self._contexts[user_id] = ConversationContext(user_id=user_id)
            self._save()

    def cleanup_expired(self):
        """Limpia contextos expirados."""
        expired = [
            user_id for user_id, ctx in self._contexts.items()
            if ctx.is_context_expired()
        ]
        for user_id in expired:
            self._contexts[user_id] = ConversationContext(user_id=user_id)

        if expired:
            self._save()
            logger.info(f"Limpiados {len(expired)} contextos expirados")


# Singleton
_conversation_store: ConversationStore | None = None


def get_conversation_store() -> ConversationStore:
    """Obtiene la instancia del store de conversaciones."""
    global _conversation_store
    if _conversation_store is None:
        _conversation_store = ConversationStore()
    return _conversation_store
