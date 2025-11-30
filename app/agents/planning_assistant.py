"""PlanningAssistant - Asistente de planificación conversacional."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import dspy

from app.agents.base import setup_dspy
from app.agents.task_planner import TaskPlannerAgent, get_task_planner
from app.agents.complexity_analyzer import ComplexityAnalyzerAgent
from app.services.notion import (
    get_notion_service,
    TaskEstado,
    TaskPrioridad,
)
from app.services.reminder_service import get_reminder_service, ReminderPriority

logger = logging.getLogger(__name__)


class PlanTomorrowSignature(dspy.Signature):
    """Analiza tareas y sugiere plan para mañana."""

    pending_tasks: str = dspy.InputField(
        desc="Lista de tareas pendientes con prioridad, contexto y fechas"
    )
    overdue_tasks: str = dspy.InputField(
        desc="Tareas vencidas que necesitan atención"
    )
    tomorrow_date: str = dspy.InputField(
        desc="Fecha de mañana (YYYY-MM-DD)"
    )
    day_of_week: str = dspy.InputField(
        desc="Día de la semana de mañana"
    )
    user_energy: str = dspy.InputField(
        desc="Nivel de energía del usuario: alto, medio, bajo, no_especificado"
    )
    user_preferences: str = dspy.InputField(
        desc="Preferencias del usuario si las mencionó"
    )

    selected_tasks: str = dspy.OutputField(
        desc="IDs de tareas seleccionadas para mañana separadas por coma (máximo 5-7)"
    )
    task_order: str = dspy.OutputField(
        desc="Orden sugerido de las tareas con horarios aproximados"
    )
    reasoning: str = dspy.OutputField(
        desc="Explicación breve de por qué se eligieron estas tareas"
    )
    warnings: str = dspy.OutputField(
        desc="Alertas importantes: deadlines próximos, tareas bloqueadas, etc."
    )
    suggestions: str = dspy.OutputField(
        desc="Sugerencias adicionales para el día"
    )


class PrioritizeTasksSignature(dspy.Signature):
    """Ayuda a priorizar tareas cuando hay conflicto."""

    task_a: str = dspy.InputField(desc="Primera tarea con detalles")
    task_b: str = dspy.InputField(desc="Segunda tarea con detalles")
    context: str = dspy.InputField(desc="Contexto adicional del usuario")

    recommendation: str = dspy.OutputField(
        desc="Cuál hacer primero: 'a', 'b', o 'ambas_posibles'"
    )
    reasoning: str = dspy.OutputField(
        desc="Explicación de la recomendación"
    )
    alternative_approach: str = dspy.OutputField(
        desc="Enfoque alternativo si el usuario no está de acuerdo"
    )


class RescheduleAnalysisSignature(dspy.Signature):
    """Analiza mejor momento para reprogramar una tarea."""

    task_description: str = dspy.InputField(desc="Descripción de la tarea")
    current_deadline: str = dspy.InputField(desc="Deadline actual si existe")
    reason_for_reschedule: str = dspy.InputField(desc="Por qué se quiere mover")
    existing_schedule: str = dspy.InputField(desc="Tareas ya programadas")
    available_slots: str = dspy.InputField(desc="Huecos disponibles en la agenda")

    suggested_date: str = dspy.OutputField(desc="Fecha sugerida (YYYY-MM-DD)")
    suggested_time_block: str = dspy.OutputField(desc="Bloque: morning, afternoon, evening")
    impact_analysis: str = dspy.OutputField(desc="Impacto de mover la tarea")
    recommendation: str = dspy.OutputField(desc="Recomendación final")


@dataclass
class TomorrowPlan:
    """Plan para mañana."""

    date: str
    day_of_week: str
    selected_tasks: list[dict]
    task_order: list[str]
    reasoning: str
    warnings: list[str]
    suggestions: list[str]
    estimated_workload_hours: float = 0.0


@dataclass
class PrioritizationResult:
    """Resultado de priorización."""

    recommendation: str  # 'a', 'b', 'ambas_posibles'
    reasoning: str
    alternative: str


@dataclass
class RescheduleResult:
    """Resultado del análisis de reprogramación."""

    suggested_date: str
    suggested_time_block: str
    impact_analysis: str
    recommendation: str
    conflicts: list[str] = field(default_factory=list)


class PlanningAssistant:
    """
    Asistente de planificación conversacional.

    Casos de uso:
    1. Planificación nocturna: "¿Qué hago mañana?"
    2. Repriorización: "¿Qué debería hacer primero, X o Y?"
    3. Reprogramación: "Necesito mover esta tarea"
    4. Revisión de carga: "¿Cómo va mi semana?"
    5. Ajuste de prioridades: "Hazla más urgente"
    """

    def __init__(self):
        setup_dspy()
        self.task_planner = get_task_planner()
        self.complexity_analyzer = ComplexityAnalyzerAgent()
        self.reminder_service = get_reminder_service()

        self.tomorrow_planner = dspy.ChainOfThought(PlanTomorrowSignature)
        self.prioritizer = dspy.ChainOfThought(PrioritizeTasksSignature)
        self.reschedule_analyzer = dspy.ChainOfThought(RescheduleAnalysisSignature)

        # Mapeo de días en español
        self.day_names = {
            0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
            4: "Viernes", 5: "Sábado", 6: "Domingo"
        }

    async def plan_tomorrow(
        self,
        user_message: str = "",
        energy_level: str = "no_especificado",
    ) -> TomorrowPlan:
        """
        Genera un plan para mañana.

        Args:
            user_message: Mensaje del usuario con preferencias
            energy_level: Nivel de energía esperado

        Returns:
            TomorrowPlan con tareas seleccionadas
        """
        notion = get_notion_service()
        now = datetime.now()
        tomorrow = now + timedelta(days=1)
        tomorrow_str = tomorrow.strftime("%Y-%m-%d")
        tomorrow_day = self.day_names[tomorrow.weekday()]

        # Es fin de semana mañana?
        is_weekend = tomorrow.weekday() >= 5

        try:
            # Obtener tareas pendientes
            pending_tasks = await notion.get_pending_tasks(limit=30)
            overdue_tasks = []

            # Formatear tareas
            pending_formatted = []
            overdue_formatted = []

            for task in pending_tasks:
                task_info = self._format_task_for_planning(task)
                if not task_info:
                    continue

                # Verificar si está vencida
                if task_info.get("fecha_due"):
                    try:
                        due_date = datetime.strptime(task_info["fecha_due"], "%Y-%m-%d")
                        if due_date.date() < now.date():
                            overdue_formatted.append(task_info)
                            continue
                    except ValueError:
                        pass

                pending_formatted.append(task_info)

            # Convertir a string para el LLM
            pending_str = self._tasks_to_string(pending_formatted)
            overdue_str = self._tasks_to_string(overdue_formatted) or "Sin tareas vencidas"

            # Ejecutar planificador
            result = self.tomorrow_planner(
                pending_tasks=pending_str,
                overdue_tasks=overdue_str,
                tomorrow_date=tomorrow_str,
                day_of_week=tomorrow_day,
                user_energy=energy_level,
                user_preferences=user_message or "Sin preferencias específicas",
            )

            # Parsear resultados
            selected_ids = [
                id.strip()
                for id in str(result.selected_tasks).split(",")
                if id.strip()
            ]

            # Obtener tareas seleccionadas
            selected_tasks = []
            all_tasks = pending_formatted + overdue_formatted

            for task_id in selected_ids:
                for task in all_tasks:
                    if task.get("id") == task_id:
                        selected_tasks.append(task)
                        break

            # Si no encontró por ID, tomar las primeras urgentes/altas
            if not selected_tasks:
                urgent_high = [
                    t for t in all_tasks
                    if t.get("prioridad") in ["🔥 Urgente", "⚡ Alta"]
                ][:5]
                selected_tasks = urgent_high or all_tasks[:5]

            # Parsear orden
            task_order = [
                line.strip()
                for line in str(result.task_order).split("\n")
                if line.strip()
            ]

            # Parsear warnings y sugerencias
            warnings = [
                w.strip()
                for w in str(result.warnings).split(";")
                if w.strip() and w.strip().lower() != "none"
            ]

            suggestions = [
                s.strip()
                for s in str(result.suggestions).split(";")
                if s.strip() and s.strip().lower() != "none"
            ]

            # Calcular carga estimada
            workload = sum(
                task.get("estimated_minutes", 30)
                for task in selected_tasks
            ) / 60

            return TomorrowPlan(
                date=tomorrow_str,
                day_of_week=tomorrow_day,
                selected_tasks=selected_tasks,
                task_order=task_order,
                reasoning=str(result.reasoning),
                warnings=warnings,
                suggestions=suggestions,
                estimated_workload_hours=workload,
            )

        except Exception as e:
            logger.error(f"Error planificando mañana: {e}")
            return await self._fallback_tomorrow_plan(tomorrow_str, tomorrow_day)

    async def prioritize_tasks(
        self,
        task_a_id: str,
        task_b_id: str,
        context: str = "",
    ) -> PrioritizationResult:
        """
        Ayuda a decidir entre dos tareas.

        Args:
            task_a_id: ID de la primera tarea
            task_b_id: ID de la segunda tarea
            context: Contexto adicional del usuario

        Returns:
            PrioritizationResult con recomendación
        """
        notion = get_notion_service()

        try:
            # Obtener detalles de las tareas
            # TODO: Implementar get_task_by_id en notion service
            # Por ahora usamos el contexto proporcionado

            result = self.prioritizer(
                task_a=f"Tarea A (ID: {task_a_id})",
                task_b=f"Tarea B (ID: {task_b_id})",
                context=context or "Sin contexto adicional",
            )

            return PrioritizationResult(
                recommendation=str(result.recommendation).lower(),
                reasoning=str(result.reasoning),
                alternative=str(result.alternative_approach),
            )

        except Exception as e:
            logger.error(f"Error priorizando: {e}")
            return PrioritizationResult(
                recommendation="ambas_posibles",
                reasoning="No pude analizar las tareas en detalle",
                alternative="Considera cuál tiene deadline más cercano",
            )

    async def analyze_reschedule(
        self,
        task_id: str,
        task_description: str,
        current_deadline: str | None,
        reason: str,
    ) -> RescheduleResult:
        """
        Analiza el mejor momento para reprogramar una tarea.

        Args:
            task_id: ID de la tarea
            task_description: Descripción de la tarea
            current_deadline: Deadline actual
            reason: Razón para reprogramar

        Returns:
            RescheduleResult con sugerencias
        """
        notion = get_notion_service()
        now = datetime.now()

        try:
            # Obtener tareas ya programadas
            pending = await notion.get_pending_tasks(limit=20)

            scheduled_tasks = []
            for task in pending:
                info = self._format_task_for_planning(task)
                if info and info.get("fecha_do"):
                    scheduled_tasks.append(f"{info['fecha_do']}: {info['name']}")

            scheduled_str = "\n".join(scheduled_tasks) or "Sin tareas programadas"

            # Calcular slots disponibles (simplificado)
            available_slots = self._calculate_available_slots(pending)

            result = self.reschedule_analyzer(
                task_description=task_description,
                current_deadline=current_deadline or "Sin deadline",
                reason_for_reschedule=reason,
                existing_schedule=scheduled_str,
                available_slots=available_slots,
            )

            return RescheduleResult(
                suggested_date=str(result.suggested_date),
                suggested_time_block=str(result.suggested_time_block),
                impact_analysis=str(result.impact_analysis),
                recommendation=str(result.recommendation),
            )

        except Exception as e:
            logger.error(f"Error analizando reprogramación: {e}")
            # Fallback: sugerir mañana o próximo lunes
            tomorrow = now + timedelta(days=1)
            if tomorrow.weekday() >= 5:  # Fin de semana
                days_until_monday = (7 - now.weekday()) % 7
                if days_until_monday == 0:
                    days_until_monday = 7
                suggested = now + timedelta(days=days_until_monday)
            else:
                suggested = tomorrow

            return RescheduleResult(
                suggested_date=suggested.strftime("%Y-%m-%d"),
                suggested_time_block="morning",
                impact_analysis="No pude analizar el impacto completamente",
                recommendation=f"Sugerencia por defecto: {suggested.strftime('%d/%m')}",
            )

    async def get_week_overview(self) -> dict[str, Any]:
        """
        Genera un resumen de la semana.

        Returns:
            Dict con resumen de carga de trabajo
        """
        notion = get_notion_service()
        now = datetime.now()

        # Inicio de semana (lunes)
        start_of_week = now - timedelta(days=now.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        try:
            pending = await notion.get_pending_tasks(limit=50)

            # Organizar por día
            by_day = {i: [] for i in range(7)}
            no_date = []
            overdue = []

            for task in pending:
                info = self._format_task_for_planning(task)
                if not info:
                    continue

                if info.get("fecha_do"):
                    try:
                        fecha = datetime.strptime(info["fecha_do"], "%Y-%m-%d")
                        if fecha < now:
                            overdue.append(info)
                        elif start_of_week <= fecha <= end_of_week:
                            by_day[fecha.weekday()].append(info)
                    except ValueError:
                        no_date.append(info)
                else:
                    no_date.append(info)

            # Calcular carga por día
            workload_by_day = {}
            for day_num, tasks in by_day.items():
                day_name = self.day_names[day_num]
                workload_by_day[day_name] = {
                    "tasks": len(tasks),
                    "hours": sum(t.get("estimated_minutes", 30) for t in tasks) / 60,
                    "urgent": len([t for t in tasks if "Urgente" in t.get("prioridad", "")]),
                }

            # Contar por prioridad
            all_tasks = [t for tasks in by_day.values() for t in tasks]
            by_priority = {
                "urgente": len([t for t in all_tasks if "Urgente" in t.get("prioridad", "")]),
                "alta": len([t for t in all_tasks if "Alta" in t.get("prioridad", "")]),
                "normal": len([t for t in all_tasks if "Normal" in t.get("prioridad", "")]),
                "baja": len([t for t in all_tasks if "Baja" in t.get("prioridad", "")]),
            }

            return {
                "week_start": start_of_week.strftime("%Y-%m-%d"),
                "week_end": end_of_week.strftime("%Y-%m-%d"),
                "workload_by_day": workload_by_day,
                "by_priority": by_priority,
                "overdue_count": len(overdue),
                "unscheduled_count": len(no_date),
                "total_tasks": len(all_tasks),
                "total_hours": sum(w["hours"] for w in workload_by_day.values()),
            }

        except Exception as e:
            logger.error(f"Error obteniendo resumen: {e}")
            return {"error": str(e)}

    async def quick_reprioritize(
        self,
        task_id: str,
        new_priority: str,
        chat_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """
        Cambia la prioridad de una tarea y ajusta recordatorios.

        Args:
            task_id: ID de la tarea en Notion
            new_priority: Nueva prioridad
            chat_id: ID del chat
            user_id: ID del usuario

        Returns:
            Dict con resultado de la operación
        """
        notion = get_notion_service()

        priority_map = {
            "urgente": TaskPrioridad.URGENTE,
            "alta": TaskPrioridad.ALTA,
            "normal": TaskPrioridad.NORMAL,
            "baja": TaskPrioridad.BAJA,
        }

        priority_enum = priority_map.get(new_priority.lower())
        if not priority_enum:
            return {"success": False, "error": "Prioridad no válida"}

        try:
            # Actualizar prioridad en Notion
            await notion.update_task_priority(task_id, priority_enum)

            # Si es urgente/alta, crear recordatorio si tiene deadline
            # TODO: Obtener detalles de la tarea para ver fecha_due

            return {
                "success": True,
                "new_priority": priority_enum.value,
                "message": f"Prioridad actualizada a {priority_enum.value}",
            }

        except Exception as e:
            logger.error(f"Error cambiando prioridad: {e}")
            return {"success": False, "error": str(e)}

    async def move_task_to_tomorrow(
        self,
        task_id: str,
        chat_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """
        Mueve una tarea para mañana.

        Args:
            task_id: ID de la tarea
            chat_id: ID del chat
            user_id: ID del usuario

        Returns:
            Dict con resultado
        """
        notion = get_notion_service()
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        try:
            await notion.update_task_dates(task_id, fecha_do=tomorrow)

            # Cancelar recordatorios viejos y crear nuevos
            await self.reminder_service.cancel_task_reminders(task_id)

            return {
                "success": True,
                "new_date": tomorrow,
                "message": f"Tarea movida para mañana ({tomorrow})",
            }

        except Exception as e:
            logger.error(f"Error moviendo tarea: {e}")
            return {"success": False, "error": str(e)}

    async def create_planning_reminders(
        self,
        chat_id: str,
        user_id: str,
        plan: TomorrowPlan,
    ) -> list[int]:
        """
        Crea recordatorios basados en el plan de mañana.

        Args:
            chat_id: ID del chat
            user_id: ID del usuario
            plan: Plan de mañana

        Returns:
            Lista de IDs de recordatorios creados
        """
        reminder_ids = []
        tomorrow = datetime.strptime(plan.date, "%Y-%m-%d")

        try:
            # Recordatorio de inicio del día
            morning_reminder = await self.reminder_service.create_reminder(
                chat_id=chat_id,
                user_id=user_id,
                title=f"🌅 Plan del día: {len(plan.selected_tasks)} tareas",
                description="\n".join(plan.task_order[:3]) if plan.task_order else None,
                scheduled_at=tomorrow.replace(hour=7, minute=30),
                priority=ReminderPriority.NORMAL,
            )
            reminder_ids.append(morning_reminder.id)

            # Recordatorios para tareas urgentes
            for task in plan.selected_tasks:
                if "Urgente" in task.get("prioridad", ""):
                    reminder = await self.reminder_service.create_reminder(
                        chat_id=chat_id,
                        user_id=user_id,
                        title=f"🔥 Tarea urgente: {task.get('name', 'Sin nombre')[:50]}",
                        scheduled_at=tomorrow.replace(hour=9, minute=0),
                        priority=ReminderPriority.URGENT,
                        notion_page_id=task.get("id"),
                    )
                    reminder_ids.append(reminder.id)

            # Recordatorio de revisión de medio día
            if len(plan.selected_tasks) > 3:
                midday = await self.reminder_service.create_reminder(
                    chat_id=chat_id,
                    user_id=user_id,
                    title="☀️ Check-in: ¿Cómo vas con las tareas?",
                    scheduled_at=tomorrow.replace(hour=13, minute=0),
                    priority=ReminderPriority.LOW,
                )
                reminder_ids.append(midday.id)

            return reminder_ids

        except Exception as e:
            logger.error(f"Error creando recordatorios de plan: {e}")
            return reminder_ids

    # ==================== HELPERS ====================

    def _format_task_for_planning(self, task: dict) -> dict | None:
        """Formatea una tarea para planificación."""
        props = task.get("properties", {})

        # Obtener nombre
        name = ""
        title = props.get("Tarea", {}).get("title", [])
        if title:
            name = title[0].get("text", {}).get("content", "")

        if not name:
            return None

        # Obtener otros campos
        prioridad = props.get("Prioridad", {}).get("select", {}).get("name", "🔄 Normal")
        contexto = props.get("Contexto", {}).get("select", {}).get("name", "Personal")
        estado = props.get("Estado", {}).get("select", {}).get("name", "Backlog")
        complejidad = props.get("Complejidad", {}).get("select", {}).get("name", "Standard")

        fecha_do = props.get("Fecha Do", {}).get("date", {})
        fecha_do_str = fecha_do.get("start") if fecha_do else None

        fecha_due = props.get("Fecha Due", {}).get("date", {})
        fecha_due_str = fecha_due.get("start") if fecha_due else None

        # Estimar minutos según complejidad
        complexity_minutes = {
            "Quick": 15,
            "Standard": 45,
            "Heavy": 90,
            "Epic": 180,
        }
        estimated_minutes = complexity_minutes.get(complejidad, 45)

        return {
            "id": task.get("id"),
            "name": name,
            "prioridad": prioridad,
            "contexto": contexto,
            "estado": estado,
            "complejidad": complejidad,
            "fecha_do": fecha_do_str,
            "fecha_due": fecha_due_str,
            "estimated_minutes": estimated_minutes,
        }

    def _tasks_to_string(self, tasks: list[dict]) -> str:
        """Convierte lista de tareas a string para LLM."""
        if not tasks:
            return "Sin tareas"

        lines = []
        for t in tasks:
            line = f"- [{t.get('id', 'N/A')[:8]}] {t.get('name', 'Sin nombre')} "
            line += f"[{t.get('prioridad', 'Normal')}] "
            line += f"Contexto: {t.get('contexto', 'Personal')}"

            if t.get("fecha_due"):
                line += f" | Due: {t['fecha_due']}"

            lines.append(line)

        return "\n".join(lines)

    def _calculate_available_slots(self, pending_tasks: list[dict]) -> str:
        """Calcula slots disponibles (simplificado)."""
        now = datetime.now()
        slots = []

        for i in range(1, 8):  # Próximos 7 días
            day = now + timedelta(days=i)
            if day.weekday() < 5:  # Días laborales
                day_name = self.day_names[day.weekday()]
                slots.append(f"{day.strftime('%Y-%m-%d')} ({day_name}): Disponible")

        return "\n".join(slots)

    async def _fallback_tomorrow_plan(
        self,
        tomorrow_str: str,
        tomorrow_day: str,
    ) -> TomorrowPlan:
        """Plan por defecto cuando falla el LLM."""
        notion = get_notion_service()

        try:
            pending = await notion.get_pending_tasks(limit=10)
            tasks = []

            for task in pending[:5]:
                info = self._format_task_for_planning(task)
                if info:
                    tasks.append(info)

            return TomorrowPlan(
                date=tomorrow_str,
                day_of_week=tomorrow_day,
                selected_tasks=tasks,
                task_order=[t.get("name", "") for t in tasks],
                reasoning="Plan generado automáticamente con tareas prioritarias",
                warnings=["No se pudo hacer análisis completo"],
                suggestions=["Revisa las tareas manualmente"],
                estimated_workload_hours=len(tasks) * 0.75,
            )

        except Exception as e:
            logger.error(f"Error en fallback plan: {e}")
            return TomorrowPlan(
                date=tomorrow_str,
                day_of_week=tomorrow_day,
                selected_tasks=[],
                task_order=[],
                reasoning="Error obteniendo tareas",
                warnings=["Error al obtener tareas de Notion"],
                suggestions=["Intenta más tarde"],
            )


# Singleton
_planning_assistant: PlanningAssistant | None = None


def get_planning_assistant() -> PlanningAssistant:
    """Obtiene la instancia del asistente de planificación."""
    global _planning_assistant
    if _planning_assistant is None:
        _planning_assistant = PlanningAssistant()
    return _planning_assistant
