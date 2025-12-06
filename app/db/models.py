"""
Modelos SQLAlchemy para PostgreSQL - Brain V2.

Estos modelos reemplazan los anteriores y son la única fuente de verdad.
Sin dependencia de Notion.
"""

from datetime import date, datetime, time
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

# ============================================================
# USER PROFILE
# ============================================================


class UserProfileModel(Base):
    """Perfil y preferencias del usuario."""

    __tablename__ = "user_profile"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    telegram_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    telegram_chat_id: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), default="Carlos")

    # Horarios laborales
    work_start: Mapped[time | None] = mapped_column(Time, default=time(9, 0))
    work_end: Mapped[time | None] = mapped_column(Time, default=time(18, 0))
    work_days: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), default=["mon", "tue", "wed", "thu", "fri"]
    )
    lunch_start: Mapped[time | None] = mapped_column(Time, default=time(13, 0))
    lunch_end: Mapped[time | None] = mapped_column(Time, default=time(14, 0))

    # Gym
    gym_days: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), default=["mon", "wed", "fri"]
    )
    gym_preferred_time: Mapped[time | None] = mapped_column(Time, default=time(7, 0))

    # Productividad
    deep_work_hours: Mapped[list[time] | None] = mapped_column(ARRAY(Time))
    low_energy_hours: Mapped[list[time] | None] = mapped_column(ARRAY(Time))

    # Contextos de trabajo
    contexts: Mapped[dict | None] = mapped_column(JSONB)
    default_context: Mapped[str | None] = mapped_column(String(50), default="PayCash")

    # Notificaciones
    notification_style: Mapped[str] = mapped_column(String(20), default="balanced")
    quiet_hours_start: Mapped[time | None] = mapped_column(Time, default=time(22, 0))
    quiet_hours_end: Mapped[time | None] = mapped_column(Time, default=time(7, 0))

    # Finanzas
    monthly_budget: Mapped[float | None] = mapped_column(Numeric(10, 2), default=15000)
    payday_days: Mapped[list[int] | None] = mapped_column(ARRAY(Integer), default=[15, 30])

    # Config
    timezone: Mapped[str] = mapped_column(String(50), default="America/Mexico_City")
    language: Mapped[str] = mapped_column(String(5), default="es")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    projects: Mapped[list["ProjectModel"]] = relationship(back_populates="user")
    tasks: Mapped[list["TaskModel"]] = relationship(back_populates="user")


# ============================================================
# PROJECTS
# ============================================================


class ProjectModel(Base):
    """Proyecto."""

    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_profile.id"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    objective: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(20), default="idea")
    type: Mapped[str] = mapped_column(String(20), default="personal")
    context: Mapped[str | None] = mapped_column(String(50))

    progress: Mapped[int] = mapped_column(Integer, default=0)

    start_date: Mapped[date | None] = mapped_column(Date)
    target_date: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    repository_url: Mapped[str | None] = mapped_column(String(500))
    documentation_url: Mapped[str | None] = mapped_column(String(500))

    # Embedding para RAG
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["UserProfileModel"] = relationship(back_populates="projects")
    tasks: Mapped[list["TaskModel"]] = relationship(back_populates="project")


# ============================================================
# TASKS
# ============================================================


class TaskModel(Base):
    """Tarea."""

    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_profile.id"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    # Estado
    status: Mapped[str] = mapped_column(String(20), default="backlog")
    priority: Mapped[str] = mapped_column(String(20), default="normal")

    # Planificación
    due_date: Mapped[date | None] = mapped_column(Date)
    scheduled_date: Mapped[date | None] = mapped_column(Date)
    preferred_time_block: Mapped[str | None] = mapped_column(String(20))

    # Complejidad
    complexity: Mapped[str | None] = mapped_column(String(20))
    energy_required: Mapped[str | None] = mapped_column(String(20))
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    actual_minutes: Mapped[int | None] = mapped_column(Integer)

    # Clasificación
    context: Mapped[str | None] = mapped_column(String(50))
    project_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id")
    )
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    # Jerarquía
    parent_task_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tasks.id")
    )

    # Blockers
    blocked_by_task_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tasks.id")
    )
    blocked_by_external: Mapped[str | None] = mapped_column(String(255))
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Source
    source: Mapped[str] = mapped_column(String(20), default="telegram")

    # Embedding para RAG
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Relationships
    user: Mapped["UserProfileModel"] = relationship(back_populates="tasks")
    project: Mapped["ProjectModel | None"] = relationship(back_populates="tasks")
    subtasks: Mapped[list["TaskModel"]] = relationship(
        "TaskModel",
        foreign_keys=[parent_task_id],
        back_populates="parent_task",
    )
    parent_task: Mapped["TaskModel | None"] = relationship(
        "TaskModel",
        foreign_keys=[parent_task_id],
        remote_side=[id],
        back_populates="subtasks",
    )
    reminders: Mapped[list["ReminderModel"]] = relationship(back_populates="task")


# ============================================================
# REMINDERS
# ============================================================


class ReminderModel(Base):
    """Recordatorio."""

    __tablename__ = "reminders"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_profile.id"), nullable=False
    )

    message: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="pending")
    escalation_level: Mapped[int] = mapped_column(Integer, default=1)

    task_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tasks.id")
    )

    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime)
    snooze_count: Mapped[int] = mapped_column(Integer, default=0)
    max_snoozes: Mapped[int] = mapped_column(Integer, default=3)

    context: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Relationships
    task: Mapped["TaskModel | None"] = relationship(back_populates="reminders")


# ============================================================
# FINANCE
# ============================================================


class TransactionModel(Base):
    """Transacción financiera."""

    __tablename__ = "transactions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_profile.id"), nullable=False
    )

    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # income, expense

    category: Mapped[str | None] = mapped_column(String(50))
    subcategory: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)

    date: Mapped[date] = mapped_column(Date, default=date.today)

    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    is_necessary: Mapped[bool | None] = mapped_column(Boolean)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(768))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DebtModel(Base):
    """Deuda."""

    __tablename__ = "debts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_profile.id"), nullable=False
    )

    creditor: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    original_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    current_balance: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    interest_rate: Mapped[float | None] = mapped_column(Numeric(5, 2))
    monthly_payment: Mapped[float | None] = mapped_column(Numeric(10, 2))
    due_day: Mapped[int | None] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(String(20), default="active")

    start_date: Mapped[date | None] = mapped_column(Date)
    expected_payoff_date: Mapped[date | None] = mapped_column(Date)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime)


# ============================================================
# HEALTH
# ============================================================


class WorkoutModel(Base):
    """Entrenamiento."""

    __tablename__ = "workouts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_profile.id"), nullable=False
    )

    date: Mapped[date] = mapped_column(Date, default=date.today)
    type: Mapped[str] = mapped_column(String(20), nullable=False)

    exercises: Mapped[dict | None] = mapped_column(JSONB)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)

    feeling: Mapped[str | None] = mapped_column(String(20))
    energy_before: Mapped[str | None] = mapped_column(String(20))
    energy_after: Mapped[str | None] = mapped_column(String(20))

    prs: Mapped[dict | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NutritionLogModel(Base):
    """Log de nutrición."""

    __tablename__ = "nutrition_logs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_profile.id"), nullable=False
    )

    date: Mapped[date] = mapped_column(Date, default=date.today)
    meal_type: Mapped[str] = mapped_column(String(20), nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=False)

    calories_estimate: Mapped[int | None] = mapped_column(Integer)
    protein_estimate: Mapped[int | None] = mapped_column(Integer)
    carbs_estimate: Mapped[int | None] = mapped_column(Integer)
    fat_estimate: Mapped[int | None] = mapped_column(Integer)

    is_healthy: Mapped[bool | None] = mapped_column(Boolean)
    is_homemade: Mapped[bool | None] = mapped_column(Boolean)

    photo_url: Mapped[str | None] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ============================================================
# BRAIN MEMORY
# ============================================================


class ConversationHistoryModel(Base):
    """Historial de conversación."""

    __tablename__ = "conversation_history"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_profile.id"), nullable=False
    )

    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    trigger_type: Mapped[str | None] = mapped_column(String(50))
    intent_detected: Mapped[str | None] = mapped_column(String(50))
    entities_extracted: Mapped[dict | None] = mapped_column(JSONB)
    action_taken: Mapped[str | None] = mapped_column(String(100))

    embedding: Mapped[list[float] | None] = mapped_column(Vector(768))

    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkingMemoryModel(Base):
    """Working memory de sesión."""

    __tablename__ = "working_memory"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_profile.id"), nullable=False
    )

    active_entity_type: Mapped[str | None] = mapped_column(String(50))
    active_entity_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    active_entity_data: Mapped[dict | None] = mapped_column(JSONB)

    conversation_mode: Mapped[str | None] = mapped_column(String(50))
    pending_question: Mapped[dict | None] = mapped_column(JSONB)
    last_action: Mapped[str | None] = mapped_column(String(100))
    last_action_at: Mapped[datetime | None] = mapped_column(DateTime)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class LearnedPatternModel(Base):
    """Patrones aprendidos del usuario."""

    __tablename__ = "learned_patterns"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_profile.id"), nullable=False
    )

    pattern_type: Mapped[str] = mapped_column(String(50), nullable=False)
    pattern_key: Mapped[str] = mapped_column(String(100), nullable=False)
    pattern_value: Mapped[str] = mapped_column(String(100), nullable=False)

    confidence: Mapped[float] = mapped_column(Numeric(3, 2), default=0.5)
    occurrences: Mapped[int] = mapped_column(Integer, default=1)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


# ============================================================
# SYSTEM
# ============================================================


class BrainMetricModel(Base):
    """Métricas del Brain."""

    __tablename__ = "brain_metrics"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)

    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)

    execution_time_ms: Mapped[int | None] = mapped_column(Integer)
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    tools_called: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None] = mapped_column(Text)

    user_feedback: Mapped[str | None] = mapped_column(String(20))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TriggerLogModel(Base):
    """Log de triggers ejecutados."""

    __tablename__ = "trigger_logs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)

    trigger_name: Mapped[str] = mapped_column(String(50), nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    action_taken: Mapped[str | None] = mapped_column(String(100))
    message_sent: Mapped[str | None] = mapped_column(Text)

    context: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
