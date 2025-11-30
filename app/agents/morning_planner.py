"""MorningPlanner Agent - Crea el plan del día."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import dspy

from app.agents.base import setup_dspy, GenerateMorningPlan

logger = logging.getLogger(__name__)


@dataclass
class TimeBlock:
    """Bloque de tiempo del día."""

    name: str
    start: str
    end: str
    task: str | None = None
    type: str = "work"  # work, break, personal, gym, study


@dataclass
class MorningPlanResult:
    """Resultado del plan del día."""

    greeting: str
    top_3_tasks: list[dict]
    time_blocks: list[TimeBlock]
    reminders: list[str]
    habit_prompts: list[str]
    motivation: str
    financial_alert: str | None = None


class MorningPlannerAgent:
    """Agente para crear el plan del día."""

    def __init__(self):
        setup_dspy()
        self.planner = dspy.ChainOfThought(GenerateMorningPlan)

        # Bloques de tiempo estándar (de Documentacion.MD)
        self.standard_blocks = [
            TimeBlock("Gym", "07:00", "08:00", type="gym"),
            TimeBlock("Prep + Daily", "08:30", "09:30", type="work"),
            TimeBlock("Deep Work 1", "09:30", "12:30", type="work"),
            TimeBlock("Almuerzo", "14:00", "15:30", type="break"),
            TimeBlock("Shallow Work", "15:30", "17:30", type="work"),
            TimeBlock("Estudio", "17:30", "18:30", type="study"),
            TimeBlock("Cierre", "18:30", "19:00", type="work"),
        ]

    async def create_morning_plan(
        self,
        pending_tasks: list[dict],
        calendar_events: list[dict] | None = None,
        yesterday_incomplete: list[dict] | None = None,
        blockers_pending: list[dict] | None = None,
        habits_status: dict | None = None,
    ) -> MorningPlanResult:
        """
        Crea el plan del día.

        Args:
            pending_tasks: Tareas pendientes (backlog, planned, today)
            calendar_events: Eventos del calendario
            yesterday_incomplete: Tareas no completadas ayer
            blockers_pending: Recordatorios de blockers
            habits_status: Estado de hábitos (gym, etc)

        Returns:
            MorningPlanResult con el plan completo
        """
        try:
            now = datetime.now()
            day_of_week = now.strftime("%A")
            day_names_es = {
                "Monday": "Lunes",
                "Tuesday": "Martes",
                "Wednesday": "Miércoles",
                "Thursday": "Jueves",
                "Friday": "Viernes",
                "Saturday": "Sábado",
                "Sunday": "Domingo",
            }
            day_es = day_names_es.get(day_of_week, day_of_week)

            # Formatear tareas pendientes
            tasks_str = self._format_tasks(pending_tasks)

            # Formatear eventos
            events_str = "Sin eventos" if not calendar_events else self._format_events(
                calendar_events
            )

            # Formatear tareas incompletas de ayer
            incomplete_str = (
                "Ninguna"
                if not yesterday_incomplete
                else self._format_tasks(yesterday_incomplete)
            )

            # Formatear blockers
            blockers_str = (
                "Ninguno"
                if not blockers_pending
                else ", ".join(b.get("description", "?") for b in blockers_pending)
            )

            # Formatear hábitos
            habits_str = self._format_habits(habits_status or {})

            # Ejecutar planner
            result = self.planner(
                pending_tasks=tasks_str,
                calendar_events=events_str,
                yesterday_incomplete=incomplete_str,
                blockers_pending=blockers_str,
                habits_status=habits_str,
                day_of_week=day_es,
            )

            # Parsear top 3 tasks
            top_3 = self._parse_top_3(result.top_3_tasks, pending_tasks)

            # Parsear time blocks
            time_blocks = self._parse_time_blocks(result.time_blocks, top_3)

            # Parsear reminders
            reminders = self._parse_list(result.reminders)

            # Parsear habit prompts
            habit_prompts = self._parse_list(result.habit_prompts)

            return MorningPlanResult(
                greeting=str(result.greeting),
                top_3_tasks=top_3,
                time_blocks=time_blocks,
                reminders=reminders,
                habit_prompts=habit_prompts,
                motivation=str(result.motivation),
            )

        except Exception as e:
            logger.error(f"Error creando plan de mañana: {e}")
            # Retornar plan básico
            return self._create_fallback_plan(pending_tasks)

    def _format_tasks(self, tasks: list[dict]) -> str:
        """Formatea lista de tareas."""
        if not tasks:
            return "Sin tareas"

        lines = []
        for task in tasks[:10]:  # Máximo 10 tareas
            name = task.get("name", task.get("tarea", "?"))
            priority = task.get("prioridad", task.get("priority", "Normal"))
            contexto = task.get("contexto", task.get("context", "?"))
            lines.append(f"- [{priority}] {name} ({contexto})")

        return "\n".join(lines)

    def _format_events(self, events: list[dict]) -> str:
        """Formatea lista de eventos."""
        lines = []
        for event in events:
            time = event.get("time", "?")
            name = event.get("name", "?")
            lines.append(f"- {time}: {name}")
        return "\n".join(lines) if lines else "Sin eventos"

    def _format_habits(self, habits: dict) -> str:
        """Formatea estado de hábitos."""
        lines = []

        # Gym
        gym = habits.get("gym", {})
        if gym:
            gym_day = gym.get("scheduled", False)
            gym_type = gym.get("type", "?")
            lines.append(
                f"Gym: {'Día de ' + gym_type if gym_day else 'Descanso'}"
            )

        # Nutrición
        nutrition = habits.get("nutrition", {})
        if nutrition:
            yesterday_rating = nutrition.get("yesterday_rating", "?")
            lines.append(f"Nutrición ayer: {yesterday_rating}")

        return "\n".join(lines) if lines else "Sin datos de hábitos"

    def _parse_top_3(
        self, top_3_str: str | list, pending_tasks: list[dict]
    ) -> list[dict]:
        """Parsea el top 3 de tareas."""
        top_3 = []

        # Si ya es lista, usarla
        if isinstance(top_3_str, list):
            raw_tasks = top_3_str
        else:
            # Intentar separar por líneas o comas
            raw_tasks = [
                t.strip()
                for t in str(top_3_str).replace("\n", ",").split(",")
                if t.strip()
            ]

        for i, task_text in enumerate(raw_tasks[:3], 1):
            # Buscar tarea coincidente en pending_tasks
            matched_task = None
            task_text_lower = task_text.lower()

            for task in pending_tasks:
                task_name = task.get("name", task.get("tarea", "")).lower()
                if task_name and task_name in task_text_lower:
                    matched_task = task
                    break

            if matched_task:
                top_3.append({
                    "rank": i,
                    "name": matched_task.get("name", matched_task.get("tarea")),
                    "id": matched_task.get("id"),
                    "contexto": matched_task.get("contexto", "Personal"),
                    "bloque": matched_task.get("bloque", "Morning" if i == 1 else "Afternoon"),
                })
            else:
                # Tarea no encontrada, usar el texto
                top_3.append({
                    "rank": i,
                    "name": task_text,
                    "id": None,
                    "contexto": "Personal",
                    "bloque": "Morning" if i == 1 else "Afternoon",
                })

        return top_3

    def _parse_time_blocks(
        self, blocks_str: str | dict, top_3: list[dict]
    ) -> list[TimeBlock]:
        """Parsea los bloques de tiempo."""
        # Usar bloques estándar y asignar tareas del top 3
        blocks = []

        for standard_block in self.standard_blocks:
            block = TimeBlock(
                name=standard_block.name,
                start=standard_block.start,
                end=standard_block.end,
                type=standard_block.type,
            )

            # Asignar tareas a bloques de trabajo
            if standard_block.type == "work" and standard_block.name == "Deep Work 1":
                if top_3:
                    block.task = top_3[0].get("name")
            elif standard_block.type == "work" and standard_block.name == "Shallow Work":
                if len(top_3) > 1:
                    block.task = top_3[1].get("name")

            blocks.append(block)

        return blocks

    def _parse_list(self, items_str: str | list) -> list[str]:
        """Parsea una lista de strings."""
        if isinstance(items_str, list):
            return [str(item) for item in items_str]

        if not items_str:
            return []

        # Separar por líneas o comas
        items = [
            item.strip()
            for item in str(items_str).replace("\n", ",").split(",")
            if item.strip()
        ]
        return items[:5]  # Máximo 5 items

    def _create_fallback_plan(self, pending_tasks: list[dict]) -> MorningPlanResult:
        """Crea un plan básico como fallback."""
        now = datetime.now()
        hour = now.hour

        # Saludo según hora
        if hour < 12:
            greeting = "¡Buenos días! 🌅"
        elif hour < 18:
            greeting = "¡Buenas tardes! ☀️"
        else:
            greeting = "¡Buenas noches! 🌙"

        # Top 3 de las tareas pendientes más prioritarias
        top_3 = []
        for i, task in enumerate(pending_tasks[:3], 1):
            top_3.append({
                "rank": i,
                "name": task.get("name", task.get("tarea", "Tarea pendiente")),
                "id": task.get("id"),
                "contexto": task.get("contexto", "Personal"),
                "bloque": "Morning" if i == 1 else "Afternoon",
            })

        return MorningPlanResult(
            greeting=greeting,
            top_3_tasks=top_3,
            time_blocks=self.standard_blocks,
            reminders=["Revisar tareas pendientes"],
            habit_prompts=["¿Vas al gym hoy?"],
            motivation="Un paso a la vez. ¡Tú puedes! 💪",
        )

    def format_telegram_message(self, plan: MorningPlanResult) -> str:
        """Formatea el plan como mensaje de Telegram."""
        now = datetime.now()
        date_str = now.strftime("%d/%m/%Y")

        message = f"{plan.greeting}\n"
        message += f"📅 <b>{date_str}</b>\n\n"

        # Top 3 MITs
        message += "🎯 <b>Tus 3 MITs de hoy:</b>\n"
        for task in plan.top_3_tasks:
            emoji = "1️⃣" if task["rank"] == 1 else "2️⃣" if task["rank"] == 2 else "3️⃣"
            message += f"{emoji} {task['name']}\n"

        message += "\n"

        # Time blocks relevantes
        message += "⏰ <b>Bloques de hoy:</b>\n"
        for block in plan.time_blocks:
            if block.type in ["work", "study"]:
                task_str = f" → {block.task}" if block.task else ""
                message += f"• {block.start}-{block.end}: {block.name}{task_str}\n"

        # Recordatorios
        if plan.reminders:
            message += "\n📌 <b>Recordatorios:</b>\n"
            for reminder in plan.reminders:
                message += f"• {reminder}\n"

        # Hábitos
        if plan.habit_prompts:
            message += "\n💪 <b>Hábitos:</b>\n"
            for prompt in plan.habit_prompts:
                message += f"• {prompt}\n"

        # Motivación
        message += f"\n✨ {plan.motivation}"

        return message
