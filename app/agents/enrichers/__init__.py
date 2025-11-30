"""
Enrichers - Agentes que enriquecen intenciones por dominio.

Cada enricher es responsable de un dominio específico y añade
información relevante al intent antes de que llegue al handler.

Arquitectura:
    Intent → EnricherRegistry.get(intent) → Enricher.enrich() → EnrichedResult
"""

from app.agents.enrichers.base import (
    BaseEnricher,
    EnricherRegistry,
    EnrichmentResult,
    get_enricher_registry,
)
from app.agents.enrichers.task_enricher import TaskEnricher
from app.agents.enrichers.finance_enricher import FinanceEnricher
from app.agents.enrichers.fitness_enricher import FitnessEnricher
from app.agents.enrichers.project_enricher import ProjectEnricher
from app.agents.enrichers.planning_enricher import PlanningEnricher


def register_all_enrichers() -> EnricherRegistry:
    """Registra todos los enrichers en el registry."""
    registry = get_enricher_registry()

    # Registrar enrichers
    registry.register(TaskEnricher())
    registry.register(FinanceEnricher())
    registry.register(FitnessEnricher())
    registry.register(ProjectEnricher())
    registry.register(PlanningEnricher())

    return registry


__all__ = [
    "BaseEnricher",
    "EnricherRegistry",
    "EnrichmentResult",
    "get_enricher_registry",
    "TaskEnricher",
    "FinanceEnricher",
    "FitnessEnricher",
    "ProjectEnricher",
    "PlanningEnricher",
    "register_all_enrichers",
]
