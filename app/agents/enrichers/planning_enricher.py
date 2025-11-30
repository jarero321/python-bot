"""
Planning Enricher - Enriquece intents de planificación.

Integra:
- PlanningAssistant: Planificación de días y semanas
- MorningPlannerAgent: Planes matutinos
- StudyBalancerAgent: Balance de estudio
"""

import logging
from datetime import datetime
from typing import Any

from app.agents.enrichers.base import BaseEnricher, EnrichmentResult
from app.agents.intent_router import UserIntent
from app.agents.planning_assistant import PlanningAssistant, get_planning_assistant
from app.agents.morning_planner import MorningPlannerAgent
from app.agents.study_balancer import StudyBalancerAgent

logger = logging.getLogger(__name__)


class PlanningEnricher(BaseEnricher):
    """Enricher para planificación - usa PlanningAssistant, MorningPlanner, StudyBalancer."""

    name = "PlanningEnricher"
    intents = [
        UserIntent.PLAN_TOMORROW,
        UserIntent.PLAN_WEEK,
        UserIntent.PRIORITIZE,
        UserIntent.RESCHEDULE,
        UserIntent.WORKLOAD_CHECK,
        UserIntent.STUDY_SESSION,
    ]

    def __init__(self):
        super().__init__()
        self._planning_assistant: PlanningAssistant | None = None
        self._morning_planner: MorningPlannerAgent | None = None
        self._study_balancer: StudyBalancerAgent | None = None

    @property
    def planning_assistant(self) -> PlanningAssistant:
        if self._planning_assistant is None:
            self._planning_assistant = get_planning_assistant()
        return self._planning_assistant

    @property
    def morning_planner(self) -> MorningPlannerAgent:
        if self._morning_planner is None:
            self._morning_planner = MorningPlannerAgent()
        return self._morning_planner

    @property
    def study_balancer(self) -> StudyBalancerAgent:
        if self._study_balancer is None:
            self._study_balancer = StudyBalancerAgent()
        return self._study_balancer

    async def enrich(
        self,
        intent: UserIntent,
        message: str,
        entities: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> EnrichmentResult:
        """Enriquece intent de planificación."""
        result = EnrichmentResult(enricher_name=self.name)

        if intent == UserIntent.PLAN_TOMORROW:
            await self._enrich_plan_tomorrow(message, entities, result, context)
        elif intent == UserIntent.PLAN_WEEK:
            await self._enrich_plan_week(message, entities, result, context)
        elif intent == UserIntent.PRIORITIZE:
            await self._enrich_prioritize(message, entities, result, context)
        elif intent == UserIntent.RESCHEDULE:
            await self._enrich_reschedule(message, entities, result)
        elif intent == UserIntent.WORKLOAD_CHECK:
            await self._enrich_workload(message, entities, result, context)
        elif intent == UserIntent.STUDY_SESSION:
            await self._enrich_study(message, entities, result)

        return result

    async def _enrich_plan_tomorrow(
        self,
        message: str,
        entities: dict[str, Any],
        result: EnrichmentResult,
        context: dict[str, Any] | None,
    ) -> None:
        """Enriquece planificación del día siguiente."""
        try:
            # Obtener tareas pendientes del contexto
            pending_tasks = context.get("pending_tasks", []) if context else []
            energy_level = entities.get("energy", "normal")

            plan = await self.planning_assistant.plan_tomorrow(
                pending_tasks=pending_tasks,
                energy_preference=energy_level,
            )

            result.planning_data = {
                "type": "tomorrow_plan",
                "top_priorities": plan.top_priorities,
                "time_blocks": [
                    {
                        "time": tb.time_slot,
                        "task": tb.task_title,
                        "duration": tb.duration_minutes,
                    }
                    for tb in plan.suggested_schedule
                ],
                "focus_areas": plan.focus_areas,
                "warnings": plan.warnings,
            }
            result.agents_used.append("PlanningAssistant")

        except Exception as e:
            self.logger.warning(f"Error en PlanningAssistant: {e}")
            result.planning_data = {"type": "tomorrow_plan", "error": str(e)}

    async def _enrich_plan_week(
        self,
        message: str,
        entities: dict[str, Any],
        result: EnrichmentResult,
        context: dict[str, Any] | None,
    ) -> None:
        """Enriquece planificación semanal."""
        result.planning_data = {
            "type": "week_plan",
            "week_start": datetime.now().strftime("%Y-%m-%d"),
        }

    async def _enrich_prioritize(
        self,
        message: str,
        entities: dict[str, Any],
        result: EnrichmentResult,
        context: dict[str, Any] | None,
    ) -> None:
        """Enriquece priorización de tareas."""
        try:
            tasks_to_prioritize = entities.get("tasks", [])

            if tasks_to_prioritize:
                prioritization = await self.planning_assistant.prioritize_tasks(
                    tasks=tasks_to_prioritize,
                )

                result.planning_data = {
                    "type": "prioritization",
                    "ranked_tasks": prioritization.ranked_tasks,
                    "rationale": prioritization.rationale,
                    "quick_wins": prioritization.quick_wins,
                }
                result.agents_used.append("PlanningAssistant")
            else:
                result.planning_data = {
                    "type": "prioritization",
                    "needs_input": True,
                    "message": "Necesito saber qué tareas quieres priorizar",
                }

        except Exception as e:
            self.logger.warning(f"Error en priorización: {e}")

    async def _enrich_reschedule(
        self,
        message: str,
        entities: dict[str, Any],
        result: EnrichmentResult,
    ) -> None:
        """Enriquece reprogramación de tarea."""
        task_name = entities.get("task", "")
        new_date = entities.get("date", "")

        result.planning_data = {
            "type": "reschedule",
            "task": task_name,
            "new_date": new_date,
        }

    async def _enrich_workload(
        self,
        message: str,
        entities: dict[str, Any],
        result: EnrichmentResult,
        context: dict[str, Any] | None,
    ) -> None:
        """Enriquece análisis de carga de trabajo."""
        result.planning_data = {
            "type": "workload_check",
        }

    async def _enrich_study(
        self,
        message: str,
        entities: dict[str, Any],
        result: EnrichmentResult,
    ) -> None:
        """Enriquece sesión de estudio."""
        try:
            # TODO: Obtener proyectos de estudio de Notion
            study_projects = []

            if study_projects:
                suggestion = await self.study_balancer.suggest_study_session(
                    projects=study_projects,
                    available_time=60,  # minutos
                )

                result.planning_data = {
                    "type": "study_session",
                    "suggested_topic": suggestion.topic,
                    "duration": suggestion.duration_minutes,
                    "resources": suggestion.resources,
                    "goals": suggestion.session_goals,
                }
                result.agents_used.append("StudyBalancer")
            else:
                result.planning_data = {
                    "type": "study_session",
                    "needs_setup": True,
                    "message": "No hay proyectos de estudio configurados",
                }

        except Exception as e:
            self.logger.warning(f"Error en StudyBalancer: {e}")
