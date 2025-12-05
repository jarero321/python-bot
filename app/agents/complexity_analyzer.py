"""ComplexityAnalyzer Agent - Analiza complejidad de tareas técnicas."""

import logging
from dataclasses import dataclass
from enum import Enum

import dspy

from app.agents.base import setup_dspy

logger = logging.getLogger(__name__)


class ComplexitySignature(dspy.Signature):
    """Analiza la complejidad de una tarea técnica."""

    task_description: str = dspy.InputField(desc="Descripción de la tarea a analizar")
    user_tech_stack: str = dspy.InputField(desc="Stack tecnológico del usuario")
    similar_tasks_history: str = dspy.InputField(desc="Historial de tareas similares con tiempos")

    complexity: str = dspy.OutputField(desc="Complejidad: quick, standard, heavy, epic")
    estimated_minutes: int = dspy.OutputField(desc="Tiempo estimado en minutos")
    energy_required: str = dspy.OutputField(desc="Energía requerida: deep_work, medium, low")
    should_divide: bool = dspy.OutputField(desc="Si la tarea debe dividirse en subtareas")
    suggested_subtasks: str = dspy.OutputField(desc="Subtareas sugeridas separadas por coma")
    potential_blockers: str = dspy.OutputField(desc="Posibles bloqueadores separados por coma")
    requires_research: bool = dspy.OutputField(desc="Si requiere investigación previa")
    research_topics: str = dspy.OutputField(desc="Temas a investigar separados por coma")


class Complexity(str, Enum):
    """Niveles de complejidad."""

    QUICK = "quick"  # <30 minutos
    STANDARD = "standard"  # 30min - 2h
    HEAVY = "heavy"  # 2-4h
    EPIC = "epic"  # 4h+


class EnergyLevel(str, Enum):
    """Niveles de energía requerida."""

    DEEP_WORK = "deep_work"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ComplexityResult:
    """Resultado del análisis de complejidad."""

    complexity: Complexity
    estimated_minutes: int
    energy_required: EnergyLevel
    should_divide: bool
    suggested_subtasks: list[str]
    potential_blockers: list[str]
    requires_research: bool
    research_topics: list[str]


class ComplexityAnalyzerAgent:
    """Agente para analizar complejidad de tareas técnicas."""

    def __init__(self):
        setup_dspy()
        self.analyzer = dspy.ChainOfThought(ComplexitySignature)

        # Stack técnico del usuario (de Documentacion.MD)
        self.user_tech_stack = "Python, JavaScript, NetSuite, Power Automate, FastAPI, React"

    async def analyze_task(
        self,
        task_description: str,
        similar_tasks_history: list[dict] | None = None,
    ) -> ComplexityResult:
        """
        Analiza la complejidad de una tarea técnica.

        Args:
            task_description: Descripción de la tarea
            similar_tasks_history: Historial de tareas similares con tiempos reales

        Returns:
            ComplexityResult con el análisis completo
        """
        try:
            # Preparar historial de tareas similares
            history_str = ""
            if similar_tasks_history:
                history_items = []
                for task in similar_tasks_history[:5]:
                    name = task.get("name", "Tarea")
                    time = task.get("actual_time", "?")
                    history_items.append(f"- {name}: {time} minutos")
                history_str = "\n".join(history_items)
            else:
                history_str = "Sin historial disponible"

            # Ejecutar análisis
            result = self.analyzer(
                task_description=task_description,
                user_tech_stack=self.user_tech_stack,
                similar_tasks_history=history_str,
            )

            # Parsear complejidad
            complexity_map = {
                "quick": Complexity.QUICK,
                "standard": Complexity.STANDARD,
                "heavy": Complexity.HEAVY,
                "epic": Complexity.EPIC,
            }
            complexity = complexity_map.get(
                result.complexity.lower(), Complexity.STANDARD
            )

            # Parsear energía
            energy_map = {
                "deep_work": EnergyLevel.DEEP_WORK,
                "medium": EnergyLevel.MEDIUM,
                "low": EnergyLevel.LOW,
            }
            energy = energy_map.get(
                result.energy_required.lower(), EnergyLevel.MEDIUM
            )

            # Parsear minutos
            try:
                minutes = int(result.estimated_minutes)
            except (ValueError, TypeError):
                # Estimar basado en complejidad
                minutes_map = {
                    Complexity.QUICK: 20,
                    Complexity.STANDARD: 60,
                    Complexity.HEAVY: 180,
                    Complexity.EPIC: 300,
                }
                minutes = minutes_map[complexity]

            # Parsear subtareas
            subtasks = []
            if result.should_divide and result.suggested_subtasks:
                if isinstance(result.suggested_subtasks, str):
                    subtasks = [
                        s.strip()
                        for s in result.suggested_subtasks.split(",")
                        if s.strip()
                    ]
                else:
                    subtasks = list(result.suggested_subtasks)

            # Parsear blockers
            blockers = []
            if result.potential_blockers:
                if isinstance(result.potential_blockers, str):
                    blockers = [
                        b.strip()
                        for b in result.potential_blockers.split(",")
                        if b.strip()
                    ]
                else:
                    blockers = list(result.potential_blockers)

            # Parsear topics de research
            topics = []
            if result.requires_research and result.research_topics:
                if isinstance(result.research_topics, str):
                    topics = [
                        t.strip()
                        for t in result.research_topics.split(",")
                        if t.strip()
                    ]
                else:
                    topics = list(result.research_topics)

            return ComplexityResult(
                complexity=complexity,
                estimated_minutes=minutes,
                energy_required=energy,
                should_divide=bool(result.should_divide),
                suggested_subtasks=subtasks[:5],  # Máximo 5 subtareas
                potential_blockers=blockers[:3],  # Máximo 3 blockers
                requires_research=bool(result.requires_research),
                research_topics=topics[:3],  # Máximo 3 topics
            )

        except Exception as e:
            logger.error(f"Error analizando complejidad: {e}")
            # Retornar valores por defecto
            return ComplexityResult(
                complexity=Complexity.STANDARD,
                estimated_minutes=60,
                energy_required=EnergyLevel.MEDIUM,
                should_divide=False,
                suggested_subtasks=[],
                potential_blockers=[],
                requires_research=False,
                research_topics=[],
            )

    def get_complexity_emoji(self, complexity: Complexity) -> str:
        """Obtiene el emoji para una complejidad."""
        emoji_map = {
            Complexity.QUICK: "🟢",
            Complexity.STANDARD: "🟡",
            Complexity.HEAVY: "🔴",
            Complexity.EPIC: "⚫",
        }
        return emoji_map.get(complexity, "🟡")

    def get_energy_emoji(self, energy: EnergyLevel) -> str:
        """Obtiene el emoji para un nivel de energía."""
        emoji_map = {
            EnergyLevel.DEEP_WORK: "🧠",
            EnergyLevel.MEDIUM: "💪",
            EnergyLevel.LOW: "😴",
        }
        return emoji_map.get(energy, "💪")

    def format_result_message(self, result: ComplexityResult) -> str:
        """Formatea el resultado como mensaje para Telegram."""
        complexity_emoji = self.get_complexity_emoji(result.complexity)
        energy_emoji = self.get_energy_emoji(result.energy_required)

        # Tiempo estimado formateado
        if result.estimated_minutes < 60:
            time_str = f"{result.estimated_minutes} minutos"
        else:
            hours = result.estimated_minutes // 60
            mins = result.estimated_minutes % 60
            time_str = f"{hours}h {mins}m" if mins else f"{hours}h"

        message = f"{complexity_emoji} <b>Análisis de Complejidad</b>\n\n"
        message += f"<b>Complejidad:</b> {result.complexity.value.title()}\n"
        message += f"<b>Tiempo estimado:</b> {time_str}\n"
        message += f"<b>Energía requerida:</b> {energy_emoji} {result.energy_required.value.replace('_', ' ').title()}\n"

        if result.should_divide and result.suggested_subtasks:
            message += "\n<b>Subtareas sugeridas:</b>\n"
            for i, subtask in enumerate(result.suggested_subtasks, 1):
                message += f"  {i}. {subtask}\n"

        if result.potential_blockers:
            message += "\n⚠️ <b>Posibles blockers:</b>\n"
            for blocker in result.potential_blockers:
                message += f"  • {blocker}\n"

        if result.requires_research and result.research_topics:
            message += "\n📚 <b>Investigar antes:</b>\n"
            for topic in result.research_topics:
                message += f"  • {topic}\n"

        return message
