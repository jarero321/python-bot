"""InboxProcessor Agent - Clasifica y procesa mensajes del inbox."""

import logging
from dataclasses import dataclass
from enum import Enum

from app.agents.base import BaseAgent, MessageClassifier, TaskExtractor

logger = logging.getLogger(__name__)


class MessageCategory(str, Enum):
    """Categorías de mensajes."""

    TASK = "task"
    IDEA = "idea"
    EVENT = "event"
    NOTE = "note"
    QUESTION = "question"
    EXPENSE = "expense"
    GYM = "gym"
    FOOD = "food"
    UNKNOWN = "unknown"


@dataclass
class ClassificationResult:
    """Resultado de la clasificación de un mensaje."""

    category: MessageCategory
    confidence: float
    reasoning: str
    task_info: dict | None = None  # Solo si category == TASK
    needs_clarification: bool = False
    clarification_question: str | None = None


class InboxProcessorAgent(BaseAgent):
    """Agent para procesar y clasificar mensajes del inbox."""

    name = "InboxProcessor"

    def __init__(self):
        super().__init__()
        self.classifier = MessageClassifier()
        self.task_extractor = TaskExtractor()

    async def execute(
        self,
        message: str,
        context: str = "",
    ) -> ClassificationResult:
        """
        Clasifica un mensaje y extrae información relevante.

        Args:
            message: El mensaje a clasificar
            context: Contexto adicional (historial, preferencias del usuario)

        Returns:
            ClassificationResult con la categoría y datos extraídos
        """
        self.logger.info(f"Clasificando mensaje: {message[:50]}...")

        # Paso 1: Clasificar el mensaje
        classification = self.classifier(message=message, context=context)

        # Parsear categoría
        category_str = classification.category.lower().strip()
        try:
            category = MessageCategory(category_str)
        except ValueError:
            category = MessageCategory.UNKNOWN

        confidence = float(classification.confidence)
        reasoning = classification.reasoning

        self.logger.debug(
            f"Clasificación: {category} (confianza: {confidence:.2f})"
        )

        # Determinar si necesita clarificación
        needs_clarification = confidence < 0.5
        clarification_question = None

        if needs_clarification:
            clarification_question = self._generate_clarification_question(
                category, message
            )

        # Paso 2: Si es una tarea con buena confianza, extraer info
        task_info = None
        if category == MessageCategory.TASK and confidence >= 0.5:
            task_info = await self._extract_task_info(message)

        return ClassificationResult(
            category=category,
            confidence=confidence,
            reasoning=reasoning,
            task_info=task_info,
            needs_clarification=needs_clarification,
            clarification_question=clarification_question,
        )

    async def _extract_task_info(self, message: str) -> dict:
        """Extrae información detallada de una tarea."""
        try:
            extraction = self.task_extractor(message=message)

            return {
                "title": extraction.title,
                "description": extraction.description,
                "priority": extraction.priority,
                "due_date": (
                    extraction.due_date
                    if extraction.due_date != "none"
                    else None
                ),
                "project_hint": extraction.project_hint,
            }
        except Exception as e:
            self.logger.error(f"Error extrayendo info de tarea: {e}")
            return {
                "title": message[:100],
                "description": "",
                "priority": "Medium",
                "due_date": None,
                "project_hint": "",
            }

    def _generate_clarification_question(
        self,
        category: MessageCategory,
        message: str,
    ) -> str:
        """Genera una pregunta de clarificación."""
        questions = {
            MessageCategory.TASK: (
                "¿Esto es una tarea que quieres agregar? "
                "¿Tiene fecha límite o prioridad específica?"
            ),
            MessageCategory.IDEA: (
                "¿Es una idea que quieres guardar para después? "
                "¿Está relacionada con algún proyecto?"
            ),
            MessageCategory.EVENT: (
                "¿Es un evento para tu calendario? "
                "¿Cuándo es exactamente?"
            ),
            MessageCategory.NOTE: (
                "¿Es una nota que quieres guardar? "
                "¿En qué categoría la clasifico?"
            ),
            MessageCategory.EXPENSE: (
                "¿Estás considerando una compra? "
                "¿Cuál es el precio exacto?"
            ),
            MessageCategory.UNKNOWN: (
                "No estoy seguro de cómo clasificar esto. "
                "¿Podrías darme más contexto?"
            ),
        }

        return questions.get(
            category,
            "¿Podrías darme más detalles sobre esto?",
        )

    async def suggest_project(
        self,
        task_info: dict,
        available_projects: list[tuple[str, str]],
    ) -> str | None:
        """
        Sugiere un proyecto basado en el hint y los proyectos disponibles.

        Args:
            task_info: Información de la tarea extraída
            available_projects: Lista de (id, nombre) de proyectos

        Returns:
            ID del proyecto sugerido o None
        """
        hint = task_info.get("project_hint", "").lower()
        if not hint:
            return None

        # Búsqueda simple por coincidencia de palabras
        for project_id, project_name in available_projects:
            if any(
                word in project_name.lower()
                for word in hint.split()
                if len(word) > 3
            ):
                return project_id

        return None


# Singleton
_inbox_processor: InboxProcessorAgent | None = None


def get_inbox_processor() -> InboxProcessorAgent:
    """Obtiene la instancia del InboxProcessor."""
    global _inbox_processor
    if _inbox_processor is None:
        _inbox_processor = InboxProcessorAgent()
    return _inbox_processor
