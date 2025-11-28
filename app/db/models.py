"""Modelos de SQLAlchemy para la base de datos."""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class ReminderStatus(str, PyEnum):
    """Estados de un recordatorio."""

    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    SNOOZED = "snoozed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ReminderPriority(str, PyEnum):
    """Niveles de prioridad de un recordatorio."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ConversationState(Base):
    """Estado de conversación para manejar flujos multi-paso."""

    __tablename__ = "conversation_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(50), index=True)

    # Estado actual del flujo
    current_flow: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_step: Mapped[str | None] = mapped_column(String(50), nullable=True)
    flow_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON serializado

    # Contexto de la última interacción
    last_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_intent: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<ConversationState(chat_id={self.chat_id}, flow={self.current_flow})>"


class ScheduledReminder(Base):
    """Recordatorio programado persistente."""

    __tablename__ = "scheduled_reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[str] = mapped_column(String(50), index=True)
    user_id: Mapped[str] = mapped_column(String(50), index=True)

    # Contenido
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Programación
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    remind_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Estado y prioridad
    status: Mapped[ReminderStatus] = mapped_column(
        Enum(ReminderStatus), default=ReminderStatus.PENDING, nullable=False
    )
    priority: Mapped[ReminderPriority] = mapped_column(
        Enum(ReminderPriority), default=ReminderPriority.NORMAL, nullable=False
    )

    # Escalación
    escalation_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reminded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    snooze_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Referencia a Notion (opcional)
    notion_page_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<ScheduledReminder(id={self.id}, title={self.title[:20]}, status={self.status})>"


class AgentMetric(Base):
    """Métricas de uso y rendimiento de los agents."""

    __tablename__ = "agent_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Identificación
    agent_name: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Métricas de rendimiento
    execution_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)

    # Input/Output
    input_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_length: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Calidad (si aplica)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    user_feedback: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # positive/negative/neutral

    # Contexto
    context: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON serializado
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<AgentMetric(agent={self.agent_name}, time={self.execution_time_ms}ms)>"


class UserPreference(Base):
    """Preferencias del usuario."""

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    chat_id: Mapped[str] = mapped_column(String(50), index=True)

    # Horarios preferidos
    wake_up_time: Mapped[str | None] = mapped_column(
        String(5), nullable=True
    )  # HH:MM format
    sleep_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    work_start_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    work_end_time: Mapped[str | None] = mapped_column(String(5), nullable=True)

    # Días de gym
    gym_days: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # "1,2,3,4,5" para L-V

    # Notificaciones
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    quiet_hours_start: Mapped[str | None] = mapped_column(String(5), nullable=True)
    quiet_hours_end: Mapped[str | None] = mapped_column(String(5), nullable=True)

    # Preferencias de UI
    language: Mapped[str] = mapped_column(String(5), default="es")
    timezone: Mapped[str] = mapped_column(String(50), default="America/Mexico_City")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<UserPreference(user_id={self.user_id})>"


class DailyLog(Base):
    """Log diario para tracking de hábitos."""

    __tablename__ = "daily_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), index=True)
    date: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD

    # Gym
    gym_completed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    gym_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Nutrición
    nutrition_logged: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    calories_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protein_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Productividad
    tasks_completed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    focus_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Mood/Energy (1-5 scale)
    mood_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    energy_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Notas generales
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<DailyLog(user_id={self.user_id}, date={self.date})>"
