"""
Base Enricher - Clase base y registry para enrichers.

El patrón Enricher permite:
1. Eliminar if/else en el orquestador
2. Agregar nuevos dominios sin modificar código existente
3. Separar responsabilidades por dominio
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.agents.intent_router import UserIntent

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentResult:
    """Resultado del enriquecimiento de un intent."""

    # Análisis de complejidad
    complexity: dict[str, Any] | None = None
    estimated_minutes: int | None = None
    energy_required: str | None = None

    # Sugerencias
    suggested_priority: str | None = None
    suggested_context: str | None = None
    suggested_dates: dict[str, str] | None = None

    # Descomposición
    subtasks: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    # Recordatorios
    reminders: list[dict] = field(default_factory=list)

    # Finanzas
    financial_analysis: dict[str, Any] | None = None

    # Fitness
    workout_data: dict[str, Any] | None = None
    nutrition_data: dict[str, Any] | None = None

    # Proyectos
    project_match: dict[str, Any] | None = None
    project_suggestions: list[str] = field(default_factory=list)

    # Planificación
    planning_data: dict[str, Any] | None = None
    schedule_suggestions: list[dict] = field(default_factory=list)

    # Metadata
    enricher_name: str = ""
    agents_used: list[str] = field(default_factory=list)

    def to_entities_dict(self) -> dict[str, Any]:
        """Convierte el resultado a un dict para agregar a entities."""
        result = {}

        if self.complexity:
            result["_complexity"] = self.complexity
        if self.subtasks:
            result["_subtasks"] = self.subtasks
        if self.blockers:
            result["_blockers"] = self.blockers
        if self.suggested_priority:
            result["priority"] = self.suggested_priority
        if self.suggested_context:
            result["_context"] = self.suggested_context
        if self.suggested_dates:
            result["_dates"] = self.suggested_dates
        if self.reminders:
            result["_reminders"] = self.reminders
        if self.financial_analysis:
            result["_financial"] = self.financial_analysis
        if self.workout_data:
            result["_workout"] = self.workout_data
        if self.nutrition_data:
            result["_nutrition"] = self.nutrition_data
        if self.project_match:
            result["_project"] = self.project_match
        if self.planning_data:
            result["_planning"] = self.planning_data

        return result


class BaseEnricher(ABC):
    """
    Clase base para enrichers.

    Cada enricher es responsable de:
    1. Declarar qué intents maneja
    2. Enriquecer el intent con información adicional usando agentes

    Ejemplo:
        class TaskEnricher(BaseEnricher):
            intents = [UserIntent.TASK_CREATE, UserIntent.TASK_UPDATE]

            async def enrich(self, intent, message, entities, context):
                # Analizar complejidad, sugerir subtareas, etc.
                return EnrichmentResult(...)
    """

    # Intents que este enricher maneja
    intents: list[UserIntent] = []

    # Nombre para logging
    name: str = "BaseEnricher"

    def __init__(self):
        self.logger = logging.getLogger(f"enricher.{self.name}")

    def handles(self, intent: UserIntent) -> bool:
        """Verifica si este enricher maneja el intent dado."""
        return intent in self.intents

    @abstractmethod
    async def enrich(
        self,
        intent: UserIntent,
        message: str,
        entities: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> EnrichmentResult:
        """
        Enriquece un intent con información adicional.

        Args:
            intent: Intención clasificada
            message: Mensaje original del usuario
            entities: Entidades extraídas por el IntentRouter
            context: Contexto adicional (conversación, usuario, etc.)

        Returns:
            EnrichmentResult con toda la información adicional
        """
        pass


class EnricherRegistry:
    """
    Registry de enrichers.

    Permite registrar y obtener enrichers sin if/else:
        registry.get(intent)  # Retorna el enricher correcto o None
    """

    _instance: "EnricherRegistry | None" = None

    def __new__(cls) -> "EnricherRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._enrichers = []
            cls._instance._intent_map = {}
        return cls._instance

    def register(self, enricher: BaseEnricher) -> None:
        """Registra un enricher."""
        self._enrichers.append(enricher)

        # Mapear intents al enricher
        for intent in enricher.intents:
            if intent in self._intent_map:
                logger.warning(
                    f"Intent {intent} ya tiene enricher, sobrescribiendo con {enricher.name}"
                )
            self._intent_map[intent] = enricher

        logger.info(f"Enricher registrado: {enricher.name} para {len(enricher.intents)} intents")

    def get(self, intent: UserIntent) -> BaseEnricher | None:
        """Obtiene el enricher para un intent."""
        return self._intent_map.get(intent)

    async def enrich(
        self,
        intent: UserIntent,
        message: str,
        entities: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> EnrichmentResult | None:
        """
        Enriquece un intent usando el enricher registrado.

        Returns:
            EnrichmentResult si hay enricher, None si no
        """
        enricher = self.get(intent)
        if enricher is None:
            return None

        try:
            return await enricher.enrich(intent, message, entities, context)
        except Exception as e:
            logger.error(f"Error en enricher {enricher.name}: {e}")
            return None

    def get_all_intents(self) -> list[UserIntent]:
        """Retorna todos los intents registrados."""
        return list(self._intent_map.keys())

    def get_stats(self) -> dict[str, Any]:
        """Retorna estadísticas del registry."""
        return {
            "total_enrichers": len(self._enrichers),
            "total_intents": len(self._intent_map),
            "enrichers": [e.name for e in self._enrichers],
        }


# Singleton
_enricher_registry: EnricherRegistry | None = None


def get_enricher_registry() -> EnricherRegistry:
    """Obtiene la instancia del registry de enrichers."""
    global _enricher_registry
    if _enricher_registry is None:
        _enricher_registry = EnricherRegistry()
    return _enricher_registry
