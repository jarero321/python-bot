"""
Task Enricher - Enriquece intents de tareas.

Integra:
- ComplexityAnalyzerAgent: Analiza complejidad, sugiere subtareas
- TaskPlannerAgent: Detecta deadlines, genera recordatorios
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from app.agents.enrichers.base import BaseEnricher, EnrichmentResult
from app.agents.intent_router import UserIntent
from app.agents.complexity_analyzer import ComplexityAnalyzerAgent
from app.agents.task_planner import TaskPlannerAgent, get_task_planner
from app.services.notion import TaskContexto

logger = logging.getLogger(__name__)


class TaskEnricher(BaseEnricher):
    """Enricher para tareas - usa ComplexityAnalyzer y TaskPlanner."""

    name = "TaskEnricher"
    intents = [
        UserIntent.TASK_CREATE,
        UserIntent.TASK_UPDATE,
        UserIntent.TASK_STATUS_CHANGE,
    ]

    def __init__(self):
        super().__init__()
        self._complexity_analyzer: ComplexityAnalyzerAgent | None = None
        self._task_planner: TaskPlannerAgent | None = None

        # Keywords para detección
        self.urgency_keywords = {
            "urgente": 3, "asap": 3, "ya": 2, "ahora": 2, "hoy": 2,
            "mañana": 1, "pronto": 1, "entrega": 2, "deadline": 3,
            "cliente": 2, "importante": 2, "crítico": 3, "bloqueado": 2,
        }

        self.context_keywords = {
            TaskContexto.PAYCASH: ["paycash", "trabajo", "oficina", "netsuite"],
            TaskContexto.FREELANCE_PA: ["power automate", "pa", "microsoft"],
            TaskContexto.FREELANCE_GOOGLE: ["google", "apps script", "sheets"],
            TaskContexto.WORKANA: ["workana", "freelance", "cliente"],
            TaskContexto.ESTUDIO: ["estudiar", "aprender", "curso", "tutorial", "dspy"],
            TaskContexto.PERSONAL: ["personal", "casa", "propio"],
        }

    @property
    def complexity_analyzer(self) -> ComplexityAnalyzerAgent:
        if self._complexity_analyzer is None:
            self._complexity_analyzer = ComplexityAnalyzerAgent()
        return self._complexity_analyzer

    @property
    def task_planner(self) -> TaskPlannerAgent:
        if self._task_planner is None:
            self._task_planner = get_task_planner()
        return self._task_planner

    async def enrich(
        self,
        intent: UserIntent,
        message: str,
        entities: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> EnrichmentResult:
        """Enriquece intent de tarea con análisis de complejidad y planificación."""
        result = EnrichmentResult(enricher_name=self.name)
        task_title = entities.get("task", message)

        logger.info(f"TaskEnricher: Enriqueciendo tarea '{task_title[:50]}'")

        # 1. Analizar complejidad
        try:
            logger.info("TaskEnricher: Ejecutando ComplexityAnalyzer...")
            complexity_result = await self.complexity_analyzer.analyze_task(task_title)
            logger.info(f"TaskEnricher: ComplexityAnalyzer OK - {complexity_result.complexity.value}, {complexity_result.estimated_minutes}min")
            # Asignar bloque de tiempo basado en energía requerida
            # Deep Work → Morning (máxima concentración)
            # Medium → Afternoon (trabajo estándar)
            # Low → Evening (tareas simples)
            energy_to_block = {
                "deep_work": "morning",
                "medium": "afternoon",
                "low": "evening",
            }
            suggested_block = energy_to_block.get(
                complexity_result.energy_required.value, "afternoon"
            )

            result.complexity = {
                "level": complexity_result.complexity.value,
                "estimated_minutes": complexity_result.estimated_minutes,
                "energy_required": complexity_result.energy_required.value,
                "should_divide": False,  # Desactivado: subtareas siempre manuales
                "requires_research": complexity_result.requires_research,
                "best_time_block": suggested_block,  # Bloque sugerido por energía
            }
            result.estimated_minutes = complexity_result.estimated_minutes
            result.energy_required = complexity_result.energy_required.value
            result.suggested_time_block = suggested_block
            # Subtareas desactivadas: el usuario las crea manualmente
            result.subtasks = []
            result.blockers = complexity_result.potential_blockers or []
            result.agents_used.append("ComplexityAnalyzer")
            logger.info(
                f"TaskEnricher: Bloque sugerido={suggested_block} "
                f"(energía={complexity_result.energy_required.value}), "
                f"Blockers={len(result.blockers)}"
            )
        except Exception as e:
            logger.error(f"TaskEnricher: Error en ComplexityAnalyzer: {e}", exc_info=True)

        # 2. Detectar urgencia
        urgency_score = self._calculate_urgency_score(message)

        # 3. Sugerir prioridad
        priority = entities.get("priority")
        if not priority:
            if urgency_score >= 7:
                priority = "urgent"
            elif urgency_score >= 4:
                priority = "high"
            else:
                priority = "normal"
        result.suggested_priority = priority

        # 4. Detectar contexto
        detected_context = self._detect_context(message)
        result.suggested_context = detected_context.value

        # 5. Detectar deadline y sugerir fechas
        try:
            deadline_result = await self.task_planner.detect_deadline(message)
            if deadline_result.has_deadline:
                result.suggested_dates = {
                    "fecha_due": deadline_result.deadline_date,
                    "fecha_do": deadline_result.suggested_start_date,
                }
                result.reminders = [
                    {"datetime": r.datetime.isoformat(), "message": r.message}
                    for r in deadline_result.reminders
                ]
                result.agents_used.append("TaskPlanner")
        except Exception as e:
            self.logger.warning(f"Error en TaskPlanner: {e}")
            # Fallback: calcular fechas basadas en urgencia
            fecha_do, fecha_due = self._suggest_dates(
                urgency_score,
                result.complexity.get("level", "standard") if result.complexity else "standard",
            )
            if fecha_do or fecha_due:
                result.suggested_dates = {"fecha_do": fecha_do, "fecha_due": fecha_due}

        # 6. Generar recordatorios si hay fecha
        if result.suggested_dates and result.suggested_dates.get("fecha_due") and not result.reminders:
            result.reminders = self._generate_reminders(
                task_title,
                priority,
                result.suggested_dates["fecha_due"],
            )

        # 7. Detectar proyecto relacionado (usando contexto detectado)
        try:
            project_match = await self._find_related_project(
                message, task_title, detected_context
            )
            if project_match:
                result.project_match = project_match
                result.agents_used.append("ProjectMatcher")
        except Exception as e:
            self.logger.warning(f"Error detectando proyecto: {e}")

        # 8. Analizar carga de trabajo (anti-burnout)
        try:
            workload = await self._analyze_workload(
                result.suggested_dates.get("fecha_do") if result.suggested_dates else None,
                result.estimated_minutes or 60,
            )
            if workload:
                result.workload_analysis = workload
                if workload.get("warning"):
                    result.workload_warning = workload["warning"]
                    logger.info(f"TaskEnricher: Advertencia de carga: {workload['warning']}")
        except Exception as e:
            self.logger.warning(f"Error analizando carga: {e}")

        # Log final del resultado
        logger.info(
            f"TaskEnricher RESULTADO: complexity={result.complexity}, "
            f"subtasks={len(result.subtasks)}, priority={result.suggested_priority}, "
            f"project={result.project_match.get('name') if result.project_match else None}, "
            f"workload_warning={result.workload_warning}"
        )

        return result

    def _calculate_urgency_score(self, message: str) -> int:
        """Calcula score de urgencia (0-10)."""
        message_lower = message.lower()
        score = 0

        for keyword, points in self.urgency_keywords.items():
            if keyword in message_lower:
                score += points

        return min(score, 10)

    def _detect_context(self, message: str) -> TaskContexto:
        """Detecta el contexto de trabajo."""
        message_lower = message.lower()

        for contexto, keywords in self.context_keywords.items():
            if any(kw in message_lower for kw in keywords):
                return contexto

        return TaskContexto.PERSONAL

    def _suggest_dates(
        self,
        urgency_score: int,
        complexity: str,
    ) -> tuple[str | None, str | None]:
        """Sugiere fechas basadas en urgencia y complejidad."""
        now = datetime.now()

        # Siguiente día laboral
        if now.weekday() >= 5:
            days_until_monday = (7 - now.weekday()) % 7 or 7
            next_workday = now + timedelta(days=days_until_monday)
        else:
            next_workday = now

        if urgency_score >= 7:
            fecha_do = next_workday.strftime("%Y-%m-%d")
            fecha_due = (next_workday + timedelta(days=1)).strftime("%Y-%m-%d")
        elif urgency_score >= 4:
            fecha_do = (next_workday + timedelta(days=1)).strftime("%Y-%m-%d")
            fecha_due = (next_workday + timedelta(days=3)).strftime("%Y-%m-%d")
        elif complexity in ["heavy", "epic"]:
            fecha_do = (next_workday + timedelta(days=2)).strftime("%Y-%m-%d")
            fecha_due = (next_workday + timedelta(days=7)).strftime("%Y-%m-%d")
        else:
            fecha_do = None
            fecha_due = None

        return fecha_do, fecha_due

    def _generate_reminders(
        self,
        task_title: str,
        priority: str,
        fecha_due: str,
    ) -> list[dict]:
        """Genera recordatorios para una tarea."""
        reminders = []

        try:
            due_date = datetime.strptime(fecha_due, "%Y-%m-%d")

            # Recordatorio un día antes
            reminder_date = due_date - timedelta(days=1)
            reminders.append({
                "datetime": reminder_date.strftime("%Y-%m-%d 09:00"),
                "message": f"Mañana vence: {task_title}",
            })

            # Para urgentes, recordatorio el mismo día
            if priority in ["urgent", "high"]:
                reminders.append({
                    "datetime": due_date.strftime("%Y-%m-%d 07:00"),
                    "message": f"HOY vence: {task_title}",
                })
        except Exception as e:
            logger.warning(f"Error generando recordatorios: {e}")

        return reminders

    async def _find_related_project(
        self,
        message: str,
        task_title: str,
        detected_context: "TaskContexto | None" = None,
    ) -> dict[str, Any] | None:
        """
        Detecta si la tarea está relacionada con algún proyecto activo.

        Usa múltiples estrategias:
        1. Coincidencia exacta del nombre del proyecto
        2. Coincidencia de palabras clave
        3. Filtrado por tipo de proyecto basado en el contexto detectado
        """
        from app.domain.repositories import get_project_repository
        from app.domain.entities.project import ProjectType

        try:
            project_repo = get_project_repository()
            active_projects = await project_repo.get_active()

            if not active_projects:
                return None

            # Mapeo de contexto a tipo de proyecto
            context_to_project_type = {
                TaskContexto.PAYCASH: [ProjectType.WORK],
                TaskContexto.FREELANCE_PA: [ProjectType.FREELANCE],
                TaskContexto.FREELANCE_GOOGLE: [ProjectType.FREELANCE],
                TaskContexto.WORKANA: [ProjectType.FREELANCE],
                TaskContexto.ESTUDIO: [ProjectType.LEARNING],
                TaskContexto.PERSONAL: [ProjectType.PERSONAL, ProjectType.SIDE_PROJECT, ProjectType.HOBBY],
            }

            # Filtrar proyectos por tipo si tenemos contexto
            preferred_types = context_to_project_type.get(detected_context, []) if detected_context else []

            # Separar proyectos: preferidos por contexto vs resto
            preferred_projects = []
            other_projects = []
            for project in active_projects:
                if project.type in preferred_types:
                    preferred_projects.append(project)
                else:
                    other_projects.append(project)

            # Combinar mensaje y título para búsqueda
            search_text = f"{message} {task_title}".lower()

            # Función para buscar coincidencias
            def find_match(projects: list) -> dict | None:
                for project in projects:
                    project_name_lower = project.name.lower()

                    # Coincidencia exacta del nombre
                    if project_name_lower in search_text:
                        return {
                            "id": project.id,
                            "name": project.name,
                            "type": project.type.value if project.type else None,
                            "confidence": "high",
                        }

                    # Coincidencia de palabras clave del proyecto
                    project_words = set(project_name_lower.split())
                    search_words = set(search_text.split())

                    # Si al menos 2 palabras coinciden (para proyectos con nombres largos)
                    common_words = project_words & search_words
                    # Filtrar palabras comunes muy cortas o genéricas
                    common_words = {w for w in common_words if len(w) > 3}

                    if len(common_words) >= 2:
                        return {
                            "id": project.id,
                            "name": project.name,
                            "type": project.type.value if project.type else None,
                            "confidence": "medium",
                        }
                return None

            # Primero buscar en proyectos preferidos por contexto
            match = find_match(preferred_projects)
            if match:
                match["matched_by"] = "context_and_name"
                logger.info(f"Proyecto encontrado por contexto+nombre: {match['name']}")
                return match

            # Si no hay coincidencia, buscar en el resto
            match = find_match(other_projects)
            if match:
                match["matched_by"] = "name_only"
                logger.info(f"Proyecto encontrado solo por nombre: {match['name']}")
                return match

            # NO auto-asignar proyecto si no hay match claro
            # Antes: asignaba el primer proyecto del tipo, causando que todo
            # cayera en "Carlos - TikTok" u otro proyecto default
            # Ahora: dejamos None y el usuario elige
            logger.info("No se encontró proyecto relacionado - dejando sin asignar")
            return None

        except Exception as e:
            logger.warning(f"Error buscando proyecto relacionado: {e}")
            return None

    async def _analyze_workload(
        self,
        target_date: str | None,
        new_task_minutes: int,
    ) -> dict[str, Any] | None:
        """
        Analiza la carga de trabajo para evitar sobrecarga (anti-burnout).

        Límites:
        - Máximo 8 horas de trabajo por día (480 min)
        - Máximo 5 tareas de alta prioridad por día
        - Advertencia si ya hay 3+ tareas EPIC/HEAVY

        Returns:
            dict con análisis y posible warning, o None si no hay problema
        """
        from datetime import date, datetime
        from app.domain.repositories import get_task_repository

        try:
            # Si no hay fecha, usar hoy
            if target_date:
                check_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            else:
                check_date = date.today()

            task_repo = get_task_repository()

            # Obtener tareas del día
            tasks_for_day = await task_repo.get_by_scheduled_date(check_date)

            if not tasks_for_day:
                return {
                    "date": check_date.isoformat(),
                    "current_tasks": 0,
                    "current_minutes": 0,
                    "available_minutes": 480,
                    "warning": None,
                }

            # Calcular carga actual
            current_minutes = sum(t.estimated_minutes or 60 for t in tasks_for_day)
            high_priority_count = sum(
                1 for t in tasks_for_day
                if t.priority and t.priority.value in ["🔥 Urgente", "⚡ Alta"]
            )
            heavy_tasks = sum(
                1 for t in tasks_for_day
                if t.complexity and t.complexity.value in ["🔴 Heavy (2-4h)", "⚫ Epic (4h+)"]
            )

            # Calcular con la nueva tarea
            total_minutes = current_minutes + new_task_minutes

            # Generar warnings
            warning = None
            if total_minutes > 480:
                hours_over = (total_minutes - 480) / 60
                warning = f"⚠️ Sobrecarga: {hours_over:.1f}h más de lo recomendado para este día"
            elif total_minutes > 420:
                warning = "⚡ Día muy cargado: considera mover algo a mañana"
            elif high_priority_count >= 5:
                warning = "🔥 Demasiadas tareas urgentes/altas para un día"
            elif heavy_tasks >= 3:
                warning = "🏋️ Muchas tareas pesadas: riesgo de burnout"

            return {
                "date": check_date.isoformat(),
                "current_tasks": len(tasks_for_day),
                "current_minutes": current_minutes,
                "total_with_new": total_minutes,
                "available_minutes": max(0, 480 - total_minutes),
                "high_priority_count": high_priority_count,
                "heavy_tasks": heavy_tasks,
                "warning": warning,
            }

        except Exception as e:
            logger.warning(f"Error analizando carga de trabajo: {e}")
            return None
