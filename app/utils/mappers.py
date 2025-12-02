"""
Mappers centralizados - Elimina duplicación de mapas en todo el código.

Este módulo consolida todos los mapas de prioridad, energía, complejidad, etc.
que estaban duplicados en múltiples archivos.
"""

from app.domain.entities.task import (
    TaskComplexity,
    TaskEnergy,
    TaskPriority,
    TaskStatus,
    TaskTimeBlock,
)


# =============================================================================
# PRIORITY MAPPERS
# =============================================================================

# String to Enum
PRIORITY_STR_TO_ENUM: dict[str, TaskPriority] = {
    "urgent": TaskPriority.URGENT,
    "urgente": TaskPriority.URGENT,
    "high": TaskPriority.HIGH,
    "alta": TaskPriority.HIGH,
    "normal": TaskPriority.NORMAL,
    "low": TaskPriority.LOW,
    "baja": TaskPriority.LOW,
}

# Enum to Emoji + Text (for display)
PRIORITY_DISPLAY: dict[TaskPriority, str] = {
    TaskPriority.URGENT: "🔥 Urgente",
    TaskPriority.HIGH: "⚡ Alta",
    TaskPriority.NORMAL: "🔄 Normal",
    TaskPriority.LOW: "🧊 Baja",
}

# Just emojis
PRIORITY_EMOJI: dict[TaskPriority, str] = {
    TaskPriority.URGENT: "🔥",
    TaskPriority.HIGH: "⚡",
    TaskPriority.NORMAL: "🔵",
    TaskPriority.LOW: "🧊",
}

# String to Notion value
PRIORITY_TO_NOTION: dict[str, str] = {
    "urgent": "Urgente",
    "urgente": "Urgente",
    "high": "Alta",
    "alta": "Alta",
    "normal": "Normal",
    "low": "Baja",
    "baja": "Baja",
}


def parse_priority(value: str | None, default: TaskPriority = TaskPriority.NORMAL) -> TaskPriority:
    """Parsea string de prioridad a enum."""
    if not value:
        return default
    return PRIORITY_STR_TO_ENUM.get(value.lower(), default)


def priority_to_display(priority: TaskPriority | None) -> str:
    """Convierte prioridad a texto con emoji para mostrar."""
    if not priority:
        return "🔄 Normal"
    return PRIORITY_DISPLAY.get(priority, "🔄 Normal")


def priority_to_emoji(priority: TaskPriority | None) -> str:
    """Retorna solo el emoji de la prioridad."""
    if not priority:
        return "🔵"
    return PRIORITY_EMOJI.get(priority, "🔵")


# =============================================================================
# ENERGY MAPPERS
# =============================================================================

ENERGY_STR_TO_ENUM: dict[str, TaskEnergy] = {
    "deep_work": TaskEnergy.DEEP_WORK,
    "deep work": TaskEnergy.DEEP_WORK,
    "alta": TaskEnergy.DEEP_WORK,
    "high": TaskEnergy.DEEP_WORK,
    "medium": TaskEnergy.MEDIUM,
    "media": TaskEnergy.MEDIUM,
    "low": TaskEnergy.LOW,
    "baja": TaskEnergy.LOW,
}

ENERGY_DISPLAY: dict[TaskEnergy, str] = {
    TaskEnergy.DEEP_WORK: "🧠 Deep Work",
    TaskEnergy.MEDIUM: "💪 Medium",
    TaskEnergy.LOW: "😴 Low",
}


def parse_energy(value: str | None) -> TaskEnergy | None:
    """Parsea string de energía a enum."""
    if not value:
        return None
    return ENERGY_STR_TO_ENUM.get(value.lower())


def energy_to_display(energy: TaskEnergy | None) -> str:
    """Convierte energía a texto con emoji."""
    if not energy:
        return ""
    return ENERGY_DISPLAY.get(energy, energy.value)


# =============================================================================
# COMPLEXITY MAPPERS
# =============================================================================

COMPLEXITY_STR_TO_ENUM: dict[str, TaskComplexity] = {
    "quick": TaskComplexity.QUICK,
    "rapida": TaskComplexity.QUICK,
    "rápida": TaskComplexity.QUICK,
    "standard": TaskComplexity.STANDARD,
    "estandar": TaskComplexity.STANDARD,
    "estándar": TaskComplexity.STANDARD,
    "heavy": TaskComplexity.HEAVY,
    "pesada": TaskComplexity.HEAVY,
    "epic": TaskComplexity.EPIC,
    "épica": TaskComplexity.EPIC,
    "epica": TaskComplexity.EPIC,
}

COMPLEXITY_DISPLAY: dict[TaskComplexity, str] = {
    TaskComplexity.QUICK: "🟢 Quick (<30m)",
    TaskComplexity.STANDARD: "🟡 Standard (30m-2h)",
    TaskComplexity.HEAVY: "🔴 Heavy (2-4h)",
    TaskComplexity.EPIC: "🟣 Epic (4h+)",
}

# Para downgrade de complejidad en subtareas
COMPLEXITY_DOWNGRADE: dict[TaskComplexity, TaskComplexity] = {
    TaskComplexity.EPIC: TaskComplexity.HEAVY,
    TaskComplexity.HEAVY: TaskComplexity.STANDARD,
    TaskComplexity.STANDARD: TaskComplexity.QUICK,
    TaskComplexity.QUICK: TaskComplexity.QUICK,
}


def parse_complexity(value: str | None) -> TaskComplexity | None:
    """Parsea string de complejidad a enum."""
    if not value:
        return None
    return COMPLEXITY_STR_TO_ENUM.get(value.lower())


def complexity_to_display(complexity: TaskComplexity | None) -> str:
    """Convierte complejidad a texto con emoji."""
    if not complexity:
        return ""
    return COMPLEXITY_DISPLAY.get(complexity, complexity.value)


def downgrade_complexity(complexity: TaskComplexity | None) -> TaskComplexity | None:
    """Reduce un nivel de complejidad (para subtareas)."""
    if not complexity:
        return None
    return COMPLEXITY_DOWNGRADE.get(complexity, TaskComplexity.QUICK)


# =============================================================================
# TIME BLOCK MAPPERS
# =============================================================================

TIME_BLOCK_STR_TO_ENUM: dict[str, TaskTimeBlock] = {
    "morning": TaskTimeBlock.MORNING,
    "mañana": TaskTimeBlock.MORNING,
    "afternoon": TaskTimeBlock.AFTERNOON,
    "tarde": TaskTimeBlock.AFTERNOON,
    "evening": TaskTimeBlock.EVENING,
    "noche": TaskTimeBlock.EVENING,
}

TIME_BLOCK_DISPLAY: dict[TaskTimeBlock, str] = {
    TaskTimeBlock.MORNING: "🌅 Morning",
    TaskTimeBlock.AFTERNOON: "☀️ Afternoon",
    TaskTimeBlock.EVENING: "🌆 Evening",
}

# Mapa de energía a bloque sugerido
ENERGY_TO_TIME_BLOCK: dict[str, str] = {
    "deep_work": "morning",
    "medium": "afternoon",
    "low": "evening",
}


def parse_time_block(value: str | None) -> TaskTimeBlock | None:
    """Parsea string de bloque a enum."""
    if not value:
        return None
    return TIME_BLOCK_STR_TO_ENUM.get(value.lower())


def time_block_to_display(block: TaskTimeBlock | None) -> str:
    """Convierte bloque a texto con emoji."""
    if not block:
        return ""
    return TIME_BLOCK_DISPLAY.get(block, block.value)


def suggest_time_block_from_energy(energy: str | None) -> str:
    """Sugiere bloque de tiempo basado en energía requerida."""
    if not energy:
        return "afternoon"
    return ENERGY_TO_TIME_BLOCK.get(energy.lower(), "afternoon")


# =============================================================================
# STATUS MAPPERS
# =============================================================================

STATUS_STR_TO_ENUM: dict[str, TaskStatus] = {
    "backlog": TaskStatus.BACKLOG,
    "planned": TaskStatus.PLANNED,
    "planificado": TaskStatus.PLANNED,
    "today": TaskStatus.TODAY,
    "hoy": TaskStatus.TODAY,
    "doing": TaskStatus.DOING,
    "haciendo": TaskStatus.DOING,
    "paused": TaskStatus.PAUSED,
    "pausado": TaskStatus.PAUSED,
    "done": TaskStatus.DONE,
    "hecho": TaskStatus.DONE,
    "completado": TaskStatus.DONE,
    "cancelled": TaskStatus.CANCELLED,
    "cancelado": TaskStatus.CANCELLED,
}

STATUS_DISPLAY: dict[TaskStatus, str] = {
    TaskStatus.BACKLOG: "📥 Backlog",
    TaskStatus.PLANNED: "📅 Planificado",
    TaskStatus.TODAY: "🎯 Hoy",
    TaskStatus.DOING: "🔄 En progreso",
    TaskStatus.PAUSED: "⏸️ Pausado",
    TaskStatus.DONE: "✅ Completado",
    TaskStatus.CANCELLED: "❌ Cancelado",
}


def parse_status(value: str | None, default: TaskStatus = TaskStatus.BACKLOG) -> TaskStatus:
    """Parsea string de status a enum."""
    if not value:
        return default
    return STATUS_STR_TO_ENUM.get(value.lower(), default)


def status_to_display(status: TaskStatus | None) -> str:
    """Convierte status a texto con emoji."""
    if not status:
        return "📥 Backlog"
    return STATUS_DISPLAY.get(status, status.value)
