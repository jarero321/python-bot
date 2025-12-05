"""
Jira HU Builder Agent - Ayuda a crear Historias de Usuario para Jira.

Toma contexto libre del usuario y lo estructura en formato de HU
con criterios de aceptación, estimación y notas técnicas.
"""

import logging
from dataclasses import dataclass
from enum import Enum

import dspy

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class BuildHU(dspy.Signature):
    """Estructura una Historia de Usuario para Jira a partir de contexto libre."""

    task_title: str = dspy.InputField(desc="Título de la tarea completada")
    user_context: str = dspy.InputField(desc="Contexto libre proporcionado por el usuario")

    hu_title: str = dspy.OutputField(desc="Título de la HU en formato: [Tipo] Descripción breve")
    hu_description: str = dspy.OutputField(
        desc="Descripción en formato: Como [rol], quiero [acción], para [beneficio]"
    )
    acceptance_criteria: str = dspy.OutputField(
        desc="Lista de criterios de aceptación separados por |"
    )
    story_points: int = dspy.OutputField(desc="Estimación en story points (1, 2, 3, 5, 8, 13)")
    technical_notes: str = dspy.OutputField(desc="Notas técnicas relevantes para desarrollo")


class HUType(str, Enum):
    """Tipos de Historia de Usuario."""

    FEATURE = "Feature"
    BUG = "Bug"
    IMPROVEMENT = "Improvement"
    TECH_DEBT = "Tech Debt"
    SPIKE = "Spike"


@dataclass
class HUResult:
    """Resultado del builder de HU."""

    title: str
    description: str
    acceptance_criteria: list[str]
    story_points: int
    technical_notes: str
    hu_type: HUType

    def to_markdown(self) -> str:
        """Formatea la HU en Markdown para copiar a Jira."""
        criteria_text = "\n".join(f"- [ ] {c}" for c in self.acceptance_criteria)

        return f"""## {self.title}

**Tipo:** {self.hu_type.value}
**Story Points:** {self.story_points}

### Descripción
{self.description}

### Criterios de Aceptación
{criteria_text}

### Notas Técnicas
{self.technical_notes}
"""

    def to_telegram(self) -> str:
        """Formatea la HU para Telegram."""
        criteria_text = "\n".join(f"• {c}" for c in self.acceptance_criteria)

        return f"""<b>{self.title}</b>

<b>Tipo:</b> {self.hu_type.value}
<b>Story Points:</b> {self.story_points}

<b>Descripción:</b>
{self.description}

<b>Criterios de Aceptación:</b>
{criteria_text}

<b>Notas Técnicas:</b>
{self.technical_notes}
"""


class JiraHUBuilderAgent(BaseAgent):
    """Agente para construir Historias de Usuario."""

    name = "JiraHUBuilder"

    def __init__(self):
        super().__init__()
        self.builder = dspy.ChainOfThought(BuildHU)

    async def execute(
        self,
        task_title: str,
        user_context: str,
    ) -> HUResult:
        """
        Construye una HU a partir del contexto del usuario.

        Args:
            task_title: Título de la tarea completada
            user_context: Contexto libre del usuario

        Returns:
            HUResult con la HU estructurada
        """
        self.logger.info(f"Construyendo HU para: {task_title}")

        try:
            result = self.builder(
                task_title=task_title,
                user_context=user_context,
            )

            # Parsear criterios de aceptación
            criteria = [
                c.strip()
                for c in result.acceptance_criteria.split("|")
                if c.strip()
            ]

            # Parsear story points
            try:
                story_points = int(result.story_points)
                # Validar que sea fibonacci
                valid_points = [1, 2, 3, 5, 8, 13]
                if story_points not in valid_points:
                    story_points = min(valid_points, key=lambda x: abs(x - story_points))
            except (ValueError, TypeError):
                story_points = 3  # Default

            # Detectar tipo de HU
            hu_type = self._detect_hu_type(task_title, user_context)

            return HUResult(
                title=result.hu_title,
                description=result.hu_description,
                acceptance_criteria=criteria or ["Funcionalidad implementada correctamente"],
                story_points=story_points,
                technical_notes=result.technical_notes or "N/A",
                hu_type=hu_type,
            )

        except Exception as e:
            self.logger.error(f"Error construyendo HU: {e}")
            # Fallback básico
            return HUResult(
                title=f"[Feature] {task_title}",
                description=f"Implementación de: {task_title}",
                acceptance_criteria=["Funcionalidad implementada", "Tests pasando"],
                story_points=3,
                technical_notes=user_context[:200] if user_context else "N/A",
                hu_type=HUType.FEATURE,
            )

    def _detect_hu_type(self, title: str, context: str) -> HUType:
        """Detecta el tipo de HU basado en el título y contexto."""
        combined = f"{title} {context}".lower()

        if any(word in combined for word in ["bug", "fix", "error", "corregir", "arreglar"]):
            return HUType.BUG

        if any(word in combined for word in ["mejorar", "optimizar", "refactor", "improve"]):
            return HUType.IMPROVEMENT

        if any(word in combined for word in ["deuda", "debt", "cleanup", "limpiar"]):
            return HUType.TECH_DEBT

        if any(word in combined for word in ["investigar", "spike", "research", "poc"]):
            return HUType.SPIKE

        return HUType.FEATURE

    def get_template_message(self) -> str:
        """Retorna una plantilla para que el usuario llene."""
        return """<b>Plantilla para HU</b>

Copia y responde lo siguiente:

<b>1. Problema que resuelve:</b>
(¿Qué issue o necesidad atendiste?)

<b>2. Cambios realizados:</b>
(¿Qué archivos/módulos modificaste?)

<b>3. Criterios de aceptación:</b>
(¿Cómo se valida que funciona?)

<b>4. Notas técnicas:</b>
(¿Algo importante para otros devs?)
"""


# Singleton
_hu_builder: JiraHUBuilderAgent | None = None


def get_hu_builder() -> JiraHUBuilderAgent:
    """Obtiene instancia del builder de HU."""
    global _hu_builder
    if _hu_builder is None:
        _hu_builder = JiraHUBuilderAgent()
    return _hu_builder
