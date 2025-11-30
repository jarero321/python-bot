"""
Inbox Entity - Items capturados pendientes de procesar.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class InboxSource(str, Enum):
    """Fuente del item."""
    TELEGRAM = "telegram"
    MANUAL = "manual"
    API = "api"
    EMAIL = "email"


class InboxStatus(str, Enum):
    """Estado del item."""
    PENDING = "pending"
    PROCESSED = "processed"
    ARCHIVED = "archived"


@dataclass
class InboxItem:
    """
    Entidad de Inbox.

    Representa un item capturado pendiente de clasificación.
    """

    id: str
    content: str
    source: InboxSource = InboxSource.TELEGRAM
    status: InboxStatus = InboxStatus.PENDING

    # Clasificación (después de procesar)
    classified_as: str | None = None  # task, idea, note, event
    converted_to_id: str | None = None  # ID del item creado

    # Contexto
    notes: str | None = None
    tags: list[str] = field(default_factory=list)

    # Metadata
    created_at: datetime | None = None
    processed_at: datetime | None = None
    user_id: int | None = None

    # Raw data
    _raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_processed(self) -> bool:
        """Verifica si ya fue procesado."""
        return self.status != InboxStatus.PENDING

    def to_dict(self) -> dict[str, Any]:
        """Convierte a diccionario."""
        return {
            "id": self.id,
            "content": self.content,
            "source": self.source.value,
            "status": self.status.value,
            "classified_as": self.classified_as,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
