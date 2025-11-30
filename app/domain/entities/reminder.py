"""
Reminder Entity - Representación de un recordatorio.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ReminderStatus(str, Enum):
    """Estados de recordatorio."""
    PENDING = "pending"
    SENT = "sent"
    SNOOZED = "snoozed"
    CANCELLED = "cancelled"


class ReminderPriority(str, Enum):
    """Prioridad del recordatorio."""
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


@dataclass
class Reminder:
    """
    Entidad de Recordatorio.

    Representa un recordatorio programado.
    """

    id: str
    message: str
    remind_at: datetime
    status: ReminderStatus = ReminderStatus.PENDING
    priority: ReminderPriority = ReminderPriority.NORMAL

    # Usuario
    user_id: int | None = None  # Telegram user ID
    chat_id: int | None = None  # Telegram chat ID

    # Recurrencia
    is_recurring: bool = False
    recurrence_pattern: str | None = None  # cron expression or similar

    # Relaciones
    task_id: str | None = None
    project_id: str | None = None

    # Snooze
    snooze_count: int = 0
    max_snoozes: int = 3

    # Metadata
    created_at: datetime | None = None
    sent_at: datetime | None = None

    # Raw data
    _raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_due(self) -> bool:
        """Verifica si el recordatorio está vencido."""
        if self.status != ReminderStatus.PENDING:
            return False
        return datetime.now() >= self.remind_at

    @property
    def can_snooze(self) -> bool:
        """Verifica si se puede posponer."""
        return self.snooze_count < self.max_snoozes

    def to_dict(self) -> dict[str, Any]:
        """Convierte a diccionario."""
        return {
            "id": self.id,
            "message": self.message,
            "remind_at": self.remind_at.isoformat(),
            "status": self.status.value,
            "priority": self.priority.value,
            "user_id": self.user_id,
            "task_id": self.task_id,
            "is_due": self.is_due,
            "can_snooze": self.can_snooze,
        }
