"""TaskPlannerAgent - Planificación inteligente de tareas con DSPy."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import dspy

from app.agents.base import setup_dspy
from app.services.notion import (
    TaskPrioridad,
    TaskComplejidad,
    TaskContexto,
    TaskBloque,
)

logger = logging.getLogger(__name__)


class PlanTaskSignature(dspy.Signature):
    """Planifica una tarea analizando contexto, urgencia y disponibilidad."""

    task_description: str = dspy.InputField(
        desc="Descripción de la tarea a planificar"
    )
    current_date: str = dspy.InputField(
        desc="Fecha actual en formato YYYY-MM-DD"
    )
    day_of_week: str = dspy.InputField(
        desc="Día de la semana actual (Lunes, Martes, etc.)"
    )
    existing_workload: str = dspy.InputField(
        desc="Tareas pendientes actuales con fechas y prioridades"
    )
    active_projects: str = dspy.InputField(
        desc="Lista de proyectos activos del usuario"
    )
    user_context: str = dspy.InputField(
        desc="Contexto adicional: fin de semana, horario laboral, etc."
    )

    priority: str = dspy.OutputField(
        desc="Prioridad sugerida: urgente, alta, normal, baja"
    )
    priority_reason: str = dspy.OutputField(
        desc="Breve explicación de por qué se sugiere esta prioridad"
    )
    contexto: str = dspy.OutputField(
        desc="Contexto de trabajo: PayCash, Freelance-PA, Freelance-Google, Personal, Workana, Estudio"
    )
    fecha_do: str = dspy.OutputField(
        desc="Fecha sugerida para empezar en YYYY-MM-DD o 'none' si no aplica"
    )
    fecha_due: str = dspy.OutputField(
        desc="Fecha límite sugerida en YYYY-MM-DD o 'none' si no tiene deadline"
    )
    bloque: str = dspy.OutputField(
        desc="Bloque de tiempo sugerido: morning, afternoon, evening o 'none'"
    )
    related_project: str = dspy.OutputField(
        desc="Nombre del proyecto relacionado si existe, o 'none'"
    )
    scheduling_notes: str = dspy.OutputField(
        desc="Notas sobre la programación y recomendaciones"
    )


class DetectDeadlineSignature(dspy.Signature):
    """Detecta si hay un deadline implícito o explícito en el mensaje."""

    message: str = dspy.InputField(
        desc="Mensaje del usuario describiendo la tarea"
    )
    current_date: str = dspy.InputField(
        desc="Fecha actual en YYYY-MM-DD"
    )

    has_deadline: bool = dspy.OutputField(
        desc="True si se detectó un deadline"
    )
    deadline_date: str = dspy.OutputField(
        desc="Fecha del deadline en YYYY-MM-DD o 'none' si no hay"
    )
    deadline_type: str = dspy.OutputField(
        desc="Tipo: explicit (mencionado), implicit (inferido), none"
    )
    confidence: float = dspy.OutputField(
        desc="Confianza de 0.0 a 1.0"
    )
    reasoning: str = dspy.OutputField(
        desc="Explicación de cómo se detectó el deadline"
    )


class SuggestRemindersSignature(dspy.Signature):
    """Sugiere recordatorios apropiados para una tarea."""

    task_description: str = dspy.InputField(
        desc="Descripción de la tarea"
    )
    priority: str = dspy.InputField(
        desc="Prioridad de la tarea"
    )
    fecha_do: str = dspy.InputField(
        desc="Fecha de inicio planificada"
    )
    fecha_due: str = dspy.InputField(
        desc="Fecha límite"
    )
    complexity: str = dspy.InputField(
        desc="Complejidad: quick, standard, heavy, epic"
    )

    reminders: str = dspy.OutputField(
        desc="Lista de recordatorios en formato 'YYYY-MM-DD HH:MM|mensaje' separados por ';'"
    )
    reminder_strategy: str = dspy.OutputField(
        desc="Explicación de la estrategia de recordatorios"
    )


@dataclass
class DeadlineDetectionResult:
    """Resultado de la detección de deadline."""

    has_deadline: bool
    deadline_date: str | None
    deadline_type: str  # explicit, implicit, none
    confidence: float
    reasoning: str


@dataclass
class TaskScheduleResult:
    """Resultado completo de la planificación de una tarea."""

    # Valores sugeridos
    priority: TaskPrioridad
    contexto: TaskContexto
    fecha_do: str | None
    fecha_due: str | None
    bloque: TaskBloque | None
    related_project_name: str | None

    # Metadata
    priority_reason: str
    scheduling_notes: str
    deadline_detection: DeadlineDetectionResult | None

    # Recordatorios sugeridos
    reminders: list[dict] = field(default_factory=list)


@dataclass
class Reminder:
    """Recordatorio programado."""

    datetime_str: str  # YYYY-MM-DD HH:MM
    message: str
    task_id: str | None = None


class TaskPlannerAgent:
    """
    Agente especializado en planificación inteligente de tareas.

    Analiza:
    - Urgencia implícita/explícita
    - Contexto de trabajo
    - Carga de trabajo existente
    - Proyectos relacionados
    - Fechas óptimas de ejecución
    """

    def __init__(self):
        setup_dspy()
        self.planner = dspy.ChainOfThought(PlanTaskSignature)
        self.deadline_detector = dspy.ChainOfThought(DetectDeadlineSignature)
        self.reminder_suggester = dspy.ChainOfThought(SuggestRemindersSignature)

        # Mapeos de valores
        self.priority_map = {
            "urgente": TaskPrioridad.URGENTE,
            "alta": TaskPrioridad.ALTA,
            "normal": TaskPrioridad.NORMAL,
            "baja": TaskPrioridad.BAJA,
        }

        self.contexto_map = {
            "paycash": TaskContexto.PAYCASH,
            "freelance-pa": TaskContexto.FREELANCE_PA,
            "freelance-google": TaskContexto.FREELANCE_GOOGLE,
            "personal": TaskContexto.PERSONAL,
            "workana": TaskContexto.WORKANA,
            "estudio": TaskContexto.ESTUDIO,
        }

        self.bloque_map = {
            "morning": TaskBloque.MORNING,
            "afternoon": TaskBloque.AFTERNOON,
            "evening": TaskBloque.EVENING,
        }

        # Keywords para detección de urgencia (fallback)
        self.urgency_keywords = {
            "urgente": 3,
            "asap": 3,
            "ya": 2,
            "ahora": 2,
            "hoy": 2,
            "mañana": 1,
            "entrega": 2,
            "deadline": 3,
            "cliente espera": 3,
            "importante": 2,
            "crítico": 3,
            "bloqueado": 2,
            "para el": 1,
        }

        # Keywords para detección de contexto (fallback)
        self.context_keywords = {
            TaskContexto.PAYCASH: ["paycash", "netsuite", "trabajo", "oficina"],
            TaskContexto.FREELANCE_PA: ["power automate", "pa ", "microsoft", "flow"],
            TaskContexto.FREELANCE_GOOGLE: ["google", "apps script", "sheets", "spreadsheet"],
            TaskContexto.WORKANA: ["workana", "freelance", "cliente"],
            TaskContexto.ESTUDIO: ["estudiar", "aprender", "curso", "tutorial", "dspy", "ai"],
            TaskContexto.PERSONAL: ["personal", "casa", "propio", "yo"],
        }

    async def plan_task(
        self,
        task_description: str,
        existing_tasks: list[dict] | None = None,
        active_projects: list[dict] | None = None,
        complexity: str = "standard",
    ) -> TaskScheduleResult:
        """
        Planifica una tarea completa.

        Args:
            task_description: Descripción de la tarea
            existing_tasks: Tareas pendientes actuales
            active_projects: Proyectos activos
            complexity: Complejidad de la tarea

        Returns:
            TaskScheduleResult con toda la planificación
        """
        now = datetime.now()
        current_date = now.strftime("%Y-%m-%d")
        day_names_es = {
            0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
            4: "Viernes", 5: "Sábado", 6: "Domingo"
        }
        day_of_week = day_names_es[now.weekday()]
        is_weekend = now.weekday() >= 5

        try:
            # 1. Detectar deadline primero
            deadline_result = await self._detect_deadline(task_description, current_date)

            # 2. Formatear workload existente
            workload_str = self._format_existing_workload(existing_tasks or [])

            # 3. Formatear proyectos
            projects_str = self._format_projects(active_projects or [])

            # 4. Crear contexto del usuario
            user_context = self._build_user_context(now, is_weekend)

            # 5. Ejecutar planificador
            result = self.planner(
                task_description=task_description,
                current_date=current_date,
                day_of_week=day_of_week,
                existing_workload=workload_str,
                active_projects=projects_str,
                user_context=user_context,
            )

            # 6. Parsear resultados
            priority = self._parse_priority(result.priority)
            contexto = self._parse_contexto(result.contexto)
            fecha_do = self._parse_date(result.fecha_do)
            fecha_due = self._parse_date(result.fecha_due)
            bloque = self._parse_bloque(result.bloque)

            # Usar deadline detectado si no hay fecha_due
            if not fecha_due and deadline_result.has_deadline:
                fecha_due = deadline_result.deadline_date

            # 7. Generar recordatorios
            reminders = await self._suggest_reminders(
                task_description=task_description,
                priority=priority.value,
                fecha_do=fecha_do,
                fecha_due=fecha_due,
                complexity=complexity,
            )

            return TaskScheduleResult(
                priority=priority,
                contexto=contexto,
                fecha_do=fecha_do,
                fecha_due=fecha_due,
                bloque=bloque,
                related_project_name=self._parse_project_name(result.related_project),
                priority_reason=str(result.priority_reason),
                scheduling_notes=str(result.scheduling_notes),
                deadline_detection=deadline_result,
                reminders=reminders,
            )

        except Exception as e:
            logger.error(f"Error en planificación: {e}")
            return self._create_fallback_schedule(task_description, is_weekend)

    async def _detect_deadline(
        self,
        message: str,
        current_date: str,
    ) -> DeadlineDetectionResult:
        """Detecta deadlines en el mensaje."""
        try:
            result = self.deadline_detector(
                message=message,
                current_date=current_date,
            )

            has_deadline = bool(result.has_deadline)
            deadline_date = None

            if has_deadline and result.deadline_date and result.deadline_date != "none":
                deadline_date = result.deadline_date

            return DeadlineDetectionResult(
                has_deadline=has_deadline,
                deadline_date=deadline_date,
                deadline_type=str(result.deadline_type) if result.deadline_type else "none",
                confidence=float(result.confidence) if result.confidence else 0.5,
                reasoning=str(result.reasoning) if result.reasoning else "",
            )

        except Exception as e:
            logger.warning(f"Error detectando deadline: {e}")
            # Fallback: búsqueda simple de patrones
            return self._fallback_deadline_detection(message, current_date)

    async def _suggest_reminders(
        self,
        task_description: str,
        priority: str,
        fecha_do: str | None,
        fecha_due: str | None,
        complexity: str,
    ) -> list[dict]:
        """Sugiere recordatorios para la tarea."""
        if not fecha_due and not fecha_do:
            return []

        try:
            result = self.reminder_suggester(
                task_description=task_description,
                priority=priority,
                fecha_do=fecha_do or "none",
                fecha_due=fecha_due or "none",
                complexity=complexity,
            )

            reminders = []
            if result.reminders:
                for reminder_str in str(result.reminders).split(";"):
                    parts = reminder_str.strip().split("|")
                    if len(parts) == 2:
                        reminders.append({
                            "datetime": parts[0].strip(),
                            "message": parts[1].strip(),
                        })

            return reminders

        except Exception as e:
            logger.warning(f"Error sugiriendo recordatorios: {e}")
            return self._fallback_reminders(task_description, priority, fecha_due)

    def _format_existing_workload(self, tasks: list[dict]) -> str:
        """Formatea las tareas existentes."""
        if not tasks:
            return "Sin tareas pendientes"

        lines = []
        for task in tasks[:10]:
            props = task.get("properties", {})

            name = ""
            title = props.get("Tarea", {}).get("title", [])
            if title:
                name = title[0].get("text", {}).get("content", "")

            priority = props.get("Prioridad", {}).get("select", {}).get("name", "Normal")
            estado = props.get("Estado", {}).get("select", {}).get("name", "Backlog")

            fecha_due = props.get("Fecha Due", {}).get("date")
            due_str = fecha_due.get("start", "") if fecha_due else "sin fecha"

            lines.append(f"- {name} [{priority}] Estado: {estado}, Due: {due_str}")

        return "\n".join(lines)

    def _format_projects(self, projects: list[dict]) -> str:
        """Formatea los proyectos activos."""
        if not projects:
            return "Sin proyectos activos"

        lines = []
        for project in projects[:10]:
            props = project.get("properties", {})

            name = ""
            title = props.get("Proyecto", {}).get("title", [])
            if title:
                name = title[0].get("text", {}).get("content", "")

            tipo = props.get("Tipo", {}).get("select", {}).get("name", "Personal")

            lines.append(f"- {name} ({tipo})")

        return "\n".join(lines)

    def _build_user_context(self, now: datetime, is_weekend: bool) -> str:
        """Construye el contexto del usuario."""
        context_parts = []

        if is_weekend:
            context_parts.append("Es fin de semana, el usuario no trabaja")
        else:
            if 9 <= now.hour < 18:
                context_parts.append("Horario laboral activo")
            elif now.hour < 9:
                context_parts.append("Antes del horario laboral")
            else:
                context_parts.append("Después del horario laboral")

        # Detectar proximidad a quincena
        if now.day in [13, 14, 15]:
            context_parts.append("Próximo a quincena (día 15)")
        elif now.day in [28, 29, 30, 31, 1]:
            context_parts.append("Próximo a fin de mes")

        return ". ".join(context_parts) if context_parts else "Contexto normal"

    def _parse_priority(self, priority_str: str) -> TaskPrioridad:
        """Parsea string de prioridad al enum."""
        priority_lower = priority_str.lower().strip()
        return self.priority_map.get(priority_lower, TaskPrioridad.NORMAL)

    def _parse_contexto(self, contexto_str: str) -> TaskContexto:
        """Parsea string de contexto al enum."""
        contexto_lower = contexto_str.lower().strip()
        return self.contexto_map.get(contexto_lower, TaskContexto.PERSONAL)

    def _parse_bloque(self, bloque_str: str) -> TaskBloque | None:
        """Parsea string de bloque al enum."""
        if not bloque_str or bloque_str.lower() == "none":
            return None
        return self.bloque_map.get(bloque_str.lower().strip())

    def _parse_date(self, date_str: str) -> str | None:
        """Parsea string de fecha."""
        if not date_str or date_str.lower() in ["none", "n/a", ""]:
            return None
        # Validar formato
        try:
            datetime.strptime(date_str.strip(), "%Y-%m-%d")
            return date_str.strip()
        except ValueError:
            return None

    def _parse_project_name(self, project_str: str) -> str | None:
        """Parsea nombre del proyecto."""
        if not project_str or project_str.lower() in ["none", "n/a", ""]:
            return None
        return project_str.strip()

    def _fallback_deadline_detection(
        self,
        message: str,
        current_date: str,
    ) -> DeadlineDetectionResult:
        """Detección de deadline por reglas simples."""
        import re

        message_lower = message.lower()
        now = datetime.strptime(current_date, "%Y-%m-%d")

        # Patrones de fechas explícitas
        date_patterns = [
            (r"para el (\d{1,2})[/\-](\d{1,2})", "explicit"),
            (r"deadline[:\s]+(\d{4}[-/]\d{2}[-/]\d{2})", "explicit"),
            (r"entrega[:\s]+(\d{1,2})[/\-](\d{1,2})", "explicit"),
        ]

        for pattern, dtype in date_patterns:
            match = re.search(pattern, message_lower)
            if match:
                try:
                    if len(match.groups()) == 2:
                        day, month = int(match.group(1)), int(match.group(2))
                        year = now.year
                        deadline_date = datetime(year, month, day)
                        if deadline_date < now:
                            deadline_date = datetime(year + 1, month, day)
                    else:
                        deadline_date = datetime.strptime(match.group(1), "%Y-%m-%d")

                    return DeadlineDetectionResult(
                        has_deadline=True,
                        deadline_date=deadline_date.strftime("%Y-%m-%d"),
                        deadline_type=dtype,
                        confidence=0.8,
                        reasoning=f"Fecha encontrada en el mensaje: {match.group(0)}",
                    )
                except ValueError:
                    pass

        # Palabras clave temporales
        if "hoy" in message_lower:
            return DeadlineDetectionResult(
                has_deadline=True,
                deadline_date=now.strftime("%Y-%m-%d"),
                deadline_type="implicit",
                confidence=0.7,
                reasoning="Keyword 'hoy' detectado",
            )

        if "mañana" in message_lower:
            tomorrow = now + timedelta(days=1)
            return DeadlineDetectionResult(
                has_deadline=True,
                deadline_date=tomorrow.strftime("%Y-%m-%d"),
                deadline_type="implicit",
                confidence=0.7,
                reasoning="Keyword 'mañana' detectado",
            )

        if "esta semana" in message_lower:
            # Próximo viernes
            days_until_friday = (4 - now.weekday()) % 7
            if days_until_friday == 0:
                days_until_friday = 7
            friday = now + timedelta(days=days_until_friday)
            return DeadlineDetectionResult(
                has_deadline=True,
                deadline_date=friday.strftime("%Y-%m-%d"),
                deadline_type="implicit",
                confidence=0.6,
                reasoning="Keyword 'esta semana' detectado",
            )

        return DeadlineDetectionResult(
            has_deadline=False,
            deadline_date=None,
            deadline_type="none",
            confidence=0.9,
            reasoning="No se detectó deadline",
        )

    def _fallback_reminders(
        self,
        task_description: str,
        priority: str,
        fecha_due: str | None,
    ) -> list[dict]:
        """Recordatorios por defecto."""
        if not fecha_due:
            return []

        reminders = []
        due_date = datetime.strptime(fecha_due, "%Y-%m-%d")

        # Un día antes
        day_before = due_date - timedelta(days=1)
        reminders.append({
            "datetime": day_before.strftime("%Y-%m-%d 09:00"),
            "message": f"Mañana vence: {task_description[:50]}",
        })

        # Si es urgente, recordatorio el mismo día
        if "urgente" in priority.lower() or "alta" in priority.lower():
            reminders.append({
                "datetime": due_date.strftime("%Y-%m-%d 07:00"),
                "message": f"HOY vence: {task_description[:50]}",
            })

        return reminders

    def _create_fallback_schedule(
        self,
        task_description: str,
        is_weekend: bool,
    ) -> TaskScheduleResult:
        """Planificación por defecto cuando falla el LLM."""
        now = datetime.now()

        # Si es fin de semana, programar para el lunes
        if is_weekend:
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            fecha_do = (now + timedelta(days=days_until_monday)).strftime("%Y-%m-%d")
        else:
            fecha_do = None

        # Detectar contexto por keywords
        contexto = TaskContexto.PERSONAL
        task_lower = task_description.lower()
        for ctx, keywords in self.context_keywords.items():
            if any(kw in task_lower for kw in keywords):
                contexto = ctx
                break

        # Calcular urgencia simple
        urgency_score = 0
        for keyword, score in self.urgency_keywords.items():
            if keyword in task_lower:
                urgency_score += score

        if urgency_score >= 5:
            priority = TaskPrioridad.URGENTE
        elif urgency_score >= 3:
            priority = TaskPrioridad.ALTA
        else:
            priority = TaskPrioridad.NORMAL

        return TaskScheduleResult(
            priority=priority,
            contexto=contexto,
            fecha_do=fecha_do,
            fecha_due=None,
            bloque=None,
            related_project_name=None,
            priority_reason="Planificación por defecto basada en keywords",
            scheduling_notes="No se pudo ejecutar el análisis completo",
            deadline_detection=None,
            reminders=[],
        )

    def calculate_urgency_score(self, message: str) -> int:
        """Calcula score de urgencia basado en keywords (público para otros módulos)."""
        message_lower = message.lower()
        score = 0

        for keyword, points in self.urgency_keywords.items():
            if keyword in message_lower:
                score += points

        return min(score, 10)

    def detect_context(self, message: str) -> TaskContexto:
        """Detecta contexto basado en keywords (público para otros módulos)."""
        message_lower = message.lower()

        for contexto, keywords in self.context_keywords.items():
            if any(kw in message_lower for kw in keywords):
                return contexto

        return TaskContexto.PERSONAL


# Singleton
_task_planner: TaskPlannerAgent | None = None


def get_task_planner() -> TaskPlannerAgent:
    """Obtiene la instancia del TaskPlanner."""
    global _task_planner
    if _task_planner is None:
        _task_planner = TaskPlannerAgent()
    return _task_planner
