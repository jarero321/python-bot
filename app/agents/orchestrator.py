"""AgentOrchestrator - Cerebro central que coordina todos los agentes."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from app.agents.base import setup_dspy
from app.agents.intent_router import IntentRouterAgent, UserIntent, IntentResult
from app.agents.complexity_analyzer import ComplexityAnalyzerAgent, ComplexityResult
from app.agents.morning_planner import MorningPlannerAgent, MorningPlanResult
from app.agents.nutrition_analyzer import NutritionAnalyzerAgent
from app.agents.workout_logger import WorkoutLoggerAgent
from app.agents.spending_analyzer import SpendingAnalyzerAgent
from app.agents.debt_strategist import DebtStrategistAgent
from app.agents.study_balancer import StudyBalancerAgent, EnergyLevel as StudyEnergyLevel
from app.services.notion import (
    get_notion_service,
    TaskEstado,
    TaskPrioridad,
    TaskComplejidad,
    TaskEnergia,
    TaskContexto,
    TaskBloque,
    ProjectTipo,
)

logger = logging.getLogger(__name__)


class OrchestratorMode(str, Enum):
    """Modos de operación del orquestador."""

    REACTIVE = "reactive"      # Responde a mensajes del usuario
    PROACTIVE = "proactive"    # Genera notificaciones y recordatorios
    PLANNING = "planning"      # Planificación del día/semana


@dataclass
class UserContext:
    """Contexto completo del usuario para toma de decisiones."""

    # Tiempo
    current_datetime: datetime = field(default_factory=datetime.now)
    day_of_week: str = ""
    is_weekend: bool = False
    is_work_hours: bool = False

    # Tareas
    tasks_today: list[dict] = field(default_factory=list)
    tasks_overdue: list[dict] = field(default_factory=list)
    tasks_pending: list[dict] = field(default_factory=list)

    # Proyectos
    active_projects: list[dict] = field(default_factory=list)

    # Finanzas
    total_debt: float = 0.0
    monthly_budget_remaining: float = 0.0

    # Hábitos
    gym_today: bool = False
    last_workout_type: str | None = None
    nutrition_logged_today: bool = False

    # Estado general
    energy_level: str = "medium"

    def __post_init__(self):
        """Calcula valores derivados."""
        now = self.current_datetime
        self.day_of_week = now.strftime("%A")
        self.is_weekend = now.weekday() >= 5
        # Horario laboral: 9:00 - 18:00 L-V
        self.is_work_hours = (
            not self.is_weekend and 9 <= now.hour < 18
        )


@dataclass
class TaskPlanningResult:
    """Resultado de la planificación de una tarea."""

    task_title: str
    suggested_priority: TaskPrioridad
    suggested_complexity: TaskComplejidad
    suggested_energy: TaskEnergia
    suggested_context: TaskContexto
    suggested_bloque: TaskBloque | None
    suggested_fecha_do: str | None  # YYYY-MM-DD
    suggested_fecha_due: str | None
    project_id: str | None
    project_name: str | None
    subtasks: list[str]
    blockers: list[str]
    reasoning: str
    reminders: list[dict]  # {"datetime": ..., "message": ...}


@dataclass
class ProactiveNotification:
    """Notificación proactiva generada por el orquestador."""

    type: str  # deadline, reminder, check_in, suggestion, alert
    priority: str  # low, medium, high, urgent
    title: str
    message: str
    related_task_id: str | None = None
    related_project_id: str | None = None
    action_buttons: list[dict] = field(default_factory=list)
    scheduled_time: datetime | None = None


class AgentOrchestrator:
    """
    Orquestador central que coordina todos los agentes del sistema.

    Responsabilidades:
    1. Mantener contexto global del usuario
    2. Enrutar mensajes al agente apropiado
    3. Combinar outputs de múltiples agentes
    4. Generar notificaciones proactivas
    5. Tomar decisiones inteligentes sobre prioridades y tiempos
    """

    def __init__(self):
        setup_dspy()
        self.logger = logging.getLogger("orchestrator")

        # Inicializar agentes (lazy loading)
        self._intent_router: IntentRouterAgent | None = None
        self._complexity_analyzer: ComplexityAnalyzerAgent | None = None
        self._morning_planner: MorningPlannerAgent | None = None
        self._nutrition_analyzer: NutritionAnalyzerAgent | None = None
        self._workout_logger: WorkoutLoggerAgent | None = None
        self._spending_analyzer: SpendingAnalyzerAgent | None = None
        self._debt_strategist: DebtStrategistAgent | None = None
        self._study_balancer: StudyBalancerAgent | None = None

        # Cache de contexto
        self._context_cache: UserContext | None = None
        self._context_cache_time: datetime | None = None
        self._context_cache_ttl = timedelta(minutes=5)

        # Palabras clave para detección de urgencia
        self.urgency_keywords = {
            "urgente": 3,
            "asap": 3,
            "ya": 2,
            "ahora": 2,
            "hoy": 2,
            "mañana": 1,
            "pronto": 1,
            "entrega": 2,
            "deadline": 3,
            "cliente": 2,
            "importante": 2,
            "crítico": 3,
            "bloqueado": 2,
        }

        # Palabras clave para contextos
        self.context_keywords = {
            TaskContexto.PAYCASH: ["paycash", "trabajo", "oficina", "netsuite"],
            TaskContexto.FREELANCE_PA: ["power automate", "pa", "microsoft"],
            TaskContexto.FREELANCE_GOOGLE: ["google", "apps script", "sheets"],
            TaskContexto.WORKANA: ["workana", "freelance", "cliente"],
            TaskContexto.ESTUDIO: ["estudiar", "aprender", "curso", "tutorial", "dspy"],
            TaskContexto.PERSONAL: ["personal", "casa", "propio"],
        }

    # ==================== LAZY LOADING DE AGENTES ====================

    @property
    def intent_router(self) -> IntentRouterAgent:
        if self._intent_router is None:
            self._intent_router = IntentRouterAgent()
        return self._intent_router

    @property
    def complexity_analyzer(self) -> ComplexityAnalyzerAgent:
        if self._complexity_analyzer is None:
            self._complexity_analyzer = ComplexityAnalyzerAgent()
        return self._complexity_analyzer

    @property
    def morning_planner(self) -> MorningPlannerAgent:
        if self._morning_planner is None:
            self._morning_planner = MorningPlannerAgent()
        return self._morning_planner

    @property
    def nutrition_analyzer(self) -> NutritionAnalyzerAgent:
        if self._nutrition_analyzer is None:
            self._nutrition_analyzer = NutritionAnalyzerAgent()
        return self._nutrition_analyzer

    @property
    def workout_logger(self) -> WorkoutLoggerAgent:
        if self._workout_logger is None:
            self._workout_logger = WorkoutLoggerAgent()
        return self._workout_logger

    @property
    def spending_analyzer(self) -> SpendingAnalyzerAgent:
        if self._spending_analyzer is None:
            self._spending_analyzer = SpendingAnalyzerAgent()
        return self._spending_analyzer

    @property
    def debt_strategist(self) -> DebtStrategistAgent:
        if self._debt_strategist is None:
            self._debt_strategist = DebtStrategistAgent()
        return self._debt_strategist

    @property
    def study_balancer(self) -> StudyBalancerAgent:
        if self._study_balancer is None:
            self._study_balancer = StudyBalancerAgent()
        return self._study_balancer

    # ==================== CONTEXTO ====================

    async def get_context(self, force_refresh: bool = False) -> UserContext:
        """
        Obtiene el contexto actual del usuario.

        Args:
            force_refresh: Forzar actualización del cache

        Returns:
            UserContext con información actualizada
        """
        now = datetime.now()

        # Verificar cache
        if (
            not force_refresh
            and self._context_cache is not None
            and self._context_cache_time is not None
            and (now - self._context_cache_time) < self._context_cache_ttl
        ):
            return self._context_cache

        # Construir contexto nuevo
        notion = get_notion_service()

        try:
            # Obtener datos en paralelo
            tasks_today = await notion.get_tasks_for_today()
            tasks_pending = await notion.get_pending_tasks(limit=30)
            active_projects = await notion.get_projects(active_only=True)
            debt_summary = await notion.get_debt_summary()

            # Calcular tareas vencidas
            tasks_overdue = []
            for task in tasks_pending:
                fecha_due = task.get("properties", {}).get("Fecha Due", {}).get("date")
                if fecha_due and fecha_due.get("start"):
                    due_date = datetime.strptime(fecha_due["start"], "%Y-%m-%d").date()
                    if due_date < now.date():
                        tasks_overdue.append(task)

            context = UserContext(
                current_datetime=now,
                tasks_today=tasks_today,
                tasks_overdue=tasks_overdue,
                tasks_pending=tasks_pending,
                active_projects=active_projects,
                total_debt=debt_summary.get("total_deuda", 0),
            )

            # Cachear
            self._context_cache = context
            self._context_cache_time = now

            return context

        except Exception as e:
            self.logger.error(f"Error obteniendo contexto: {e}")
            # Retornar contexto básico
            return UserContext(current_datetime=now)

    # ==================== PROCESAMIENTO DE MENSAJES ====================

    async def process_message(
        self,
        message: str,
        user_id: int,
        conversation_context: str = "",
    ) -> dict[str, Any]:
        """
        Procesa un mensaje del usuario y coordina la respuesta.

        Args:
            message: Mensaje del usuario
            user_id: ID del usuario de Telegram
            conversation_context: Contexto de conversación anterior

        Returns:
            Dict con response, intent, actions, y metadata
        """
        self.logger.info(f"Procesando mensaje: {message[:50]}...")

        # 1. Clasificar intención
        intent_result = await self.intent_router.execute(
            message=message,
            conversation_context=conversation_context,
        )

        # 2. Obtener contexto del usuario
        context = await self.get_context()

        # 3. Enriquecer con análisis adicional según intención
        result = {
            "intent": intent_result.intent.value,
            "confidence": intent_result.confidence,
            "entities": intent_result.entities,
            "context": {
                "is_weekend": context.is_weekend,
                "is_work_hours": context.is_work_hours,
                "tasks_today_count": len(context.tasks_today),
                "tasks_overdue_count": len(context.tasks_overdue),
            },
            "response": None,
            "actions": [],
            "enrichment": {},
        }

        # 4. Procesar según intención
        if intent_result.intent == UserIntent.TASK_CREATE:
            result["enrichment"] = await self._enrich_task_creation(
                message, intent_result.entities, context
            )

        elif intent_result.intent == UserIntent.EXPENSE_ANALYZE:
            result["enrichment"] = await self._enrich_expense_analysis(
                message, intent_result.entities, context
            )

        elif intent_result.intent == UserIntent.GYM_LOG:
            result["enrichment"] = await self._enrich_workout_log(
                message, intent_result.entities, context
            )

        elif intent_result.intent == UserIntent.NUTRITION_LOG:
            result["enrichment"] = await self._enrich_nutrition_log(
                message, intent_result.entities, context
            )

        elif intent_result.intent == UserIntent.STUDY_SESSION:
            result["enrichment"] = await self._enrich_study_session(
                message, intent_result.entities, context
            )

        elif intent_result.intent == UserIntent.PROJECT_CREATE:
            result["enrichment"] = await self._enrich_project_creation(
                message, intent_result.entities, context
            )

        return result

    # ==================== ENRIQUECIMIENTO POR TIPO ====================

    async def _enrich_task_creation(
        self,
        message: str,
        entities: dict,
        context: UserContext,
    ) -> dict[str, Any]:
        """Enriquece la creación de una tarea con análisis de complejidad y contexto."""

        task_title = entities.get("task", message)

        # 1. Analizar complejidad
        complexity_result = await self.complexity_analyzer.analyze_task(task_title)

        # 2. Detectar urgencia del mensaje
        urgency_score = self._calculate_urgency_score(message)

        # 3. Detectar contexto
        detected_context = self._detect_context(message)

        # 4. Buscar proyecto relacionado
        project_match = await self._find_related_project(message, context.active_projects)

        # 5. Sugerir fechas
        fecha_do, fecha_due = self._suggest_dates(
            urgency_score=urgency_score,
            complexity=complexity_result.complexity.value,
            is_weekend=context.is_weekend,
            context_type=detected_context,
        )

        # 6. Sugerir prioridad
        priority = self._suggest_priority(
            urgency_score=urgency_score,
            has_deadline=fecha_due is not None,
            project_match=project_match,
        )

        # 7. Sugerir bloque de tiempo
        bloque = self._suggest_time_block(
            complexity_result.energy_required.value,
            context.is_work_hours,
        )

        # 8. Generar recordatorios sugeridos
        reminders = self._generate_task_reminders(
            task_title=task_title,
            priority=priority,
            fecha_do=fecha_do,
            fecha_due=fecha_due,
        )

        return {
            "task_title": task_title,
            "complexity": {
                "level": complexity_result.complexity.value,
                "estimated_minutes": complexity_result.estimated_minutes,
                "energy_required": complexity_result.energy_required.value,
                "should_divide": complexity_result.should_divide,
                "subtasks": complexity_result.suggested_subtasks,
                "blockers": complexity_result.potential_blockers,
                "requires_research": complexity_result.requires_research,
            },
            "urgency_score": urgency_score,
            "suggested_context": detected_context.value,
            "suggested_priority": priority.value,
            "suggested_bloque": bloque.value if bloque else None,
            "suggested_fecha_do": fecha_do,
            "suggested_fecha_due": fecha_due,
            "project": {
                "id": project_match.get("id") if project_match else None,
                "name": project_match.get("name") if project_match else None,
            },
            "reminders": reminders,
        }

    async def _enrich_expense_analysis(
        self,
        message: str,
        entities: dict,
        context: UserContext,
    ) -> dict[str, Any]:
        """Enriquece el análisis de un gasto potencial."""

        amount = float(entities.get("amount", 0))
        item = entities.get("item", message)

        # Obtener análisis del SpendingAnalyzer
        analysis = await self.spending_analyzer.analyze_purchase(
            item_description=item,
            price=amount,
            current_debt=context.total_debt,
        )

        return {
            "item": item,
            "amount": amount,
            "analysis": {
                "necessity_score": analysis.necessity_score,
                "budget_impact": analysis.budget_impact,
                "recommendation": analysis.recommendation,
                "honest_questions": analysis.honest_questions,
            },
            "context": {
                "total_debt": context.total_debt,
                "monthly_remaining": context.monthly_budget_remaining,
            },
        }

    async def _enrich_workout_log(
        self,
        message: str,
        entities: dict,
        context: UserContext,
    ) -> dict[str, Any]:
        """Enriquece el registro de un workout."""

        # Parsear ejercicios del mensaje
        workout_result = await self.workout_logger.parse_workout(message)

        return {
            "workout_type": workout_result.workout_type.value,
            "exercises": [
                {
                    "name": ex.name,
                    "sets": [{"reps": s.reps, "weight": s.weight} for s in ex.sets],
                }
                for ex in workout_result.exercises
            ],
            "duration_minutes": workout_result.duration_minutes,
            "rating": workout_result.rating.value,
            "notes": workout_result.notes,
            "prs": workout_result.prs,
        }

    async def _enrich_nutrition_log(
        self,
        message: str,
        entities: dict,
        context: UserContext,
    ) -> dict[str, Any]:
        """Enriquece el registro de nutrición."""

        meal_type = entities.get("meal", "comida")
        food = entities.get("food", message)

        # Analizar nutrición
        analysis = await self.nutrition_analyzer.analyze_meal(food)

        return {
            "meal_type": meal_type,
            "food_description": food,
            "analysis": {
                "calories_estimate": analysis.calories_estimate,
                "protein_estimate": analysis.protein_estimate,
                "category": analysis.category.value,
                "suggestions": analysis.suggestions,
            },
        }

    async def _enrich_study_session(
        self,
        message: str,
        entities: dict,
        context: UserContext,
    ) -> dict[str, Any]:
        """Enriquece una sesión de estudio con sugerencias."""

        # Determinar nivel de energía del mensaje
        energy = StudyEnergyLevel.MEDIUM
        if any(w in message.lower() for w in ["cansado", "bajo", "poco tiempo"]):
            energy = StudyEnergyLevel.LOW
        elif any(w in message.lower() for w in ["motivado", "energía", "deep work"]):
            energy = StudyEnergyLevel.HIGH

        # Obtener sugerencia de estudio
        suggestion = await self.study_balancer.suggest_topic(
            user_preference=message,
            energy_level=energy,
        )

        return {
            "suggested_topic": suggestion.topic,
            "reason": suggestion.reason,
            "alternative": suggestion.alternative,
            "balance_status": suggestion.balance_status,
            "neglected_topics": suggestion.neglected_topics,
            "session_goal": suggestion.session_goal,
            "estimated_duration": suggestion.estimated_duration,
        }

    async def _enrich_project_creation(
        self,
        message: str,
        entities: dict,
        context: UserContext,
    ) -> dict[str, Any]:
        """Enriquece la creación de un proyecto."""

        project_name = entities.get("project_name", "")
        project_type = entities.get("project_type", "personal")

        # Mapear tipo
        type_map = {
            "trabajo": ProjectTipo.TRABAJO,
            "freelance": ProjectTipo.FREELANCE,
            "personal": ProjectTipo.PERSONAL,
            "estudio": ProjectTipo.APRENDIZAJE,
            "side_project": ProjectTipo.SIDE_PROJECT,
        }

        suggested_type = type_map.get(project_type, ProjectTipo.PERSONAL)

        # Detectar si genera dinero
        genera_dinero = project_type in ["trabajo", "freelance"] or any(
            w in message.lower() for w in ["cliente", "pago", "cobrar", "factura"]
        )

        return {
            "project_name": project_name,
            "suggested_type": suggested_type.value,
            "genera_dinero": genera_dinero,
            "en_rotacion_estudio": project_type == "estudio",
        }

    # ==================== FUNCIONES DE PLANIFICACIÓN ====================

    async def plan_task(
        self,
        task_description: str,
        user_provided_deadline: str | None = None,
    ) -> TaskPlanningResult:
        """
        Planifica una tarea completa con todos los análisis.

        Args:
            task_description: Descripción de la tarea
            user_provided_deadline: Deadline proporcionado por usuario (opcional)

        Returns:
            TaskPlanningResult con toda la planificación
        """
        context = await self.get_context()

        # Enriquecer tarea
        enrichment = await self._enrich_task_creation(
            message=task_description,
            entities={"task": task_description},
            context=context,
        )

        # Si el usuario proporcionó deadline, usarlo
        fecha_due = user_provided_deadline or enrichment["suggested_fecha_due"]

        # Mapear complexity string a enum
        complexity_map = {
            "quick": TaskComplejidad.QUICK,
            "standard": TaskComplejidad.STANDARD,
            "heavy": TaskComplejidad.HEAVY,
            "epic": TaskComplejidad.EPIC,
        }

        energy_map = {
            "deep_work": TaskEnergia.DEEP_WORK,
            "medium": TaskEnergia.MEDIUM,
            "low": TaskEnergia.LOW,
        }

        priority_map = {
            "🔥 Urgente": TaskPrioridad.URGENTE,
            "⚡ Alta": TaskPrioridad.ALTA,
            "🔄 Normal": TaskPrioridad.NORMAL,
            "🧊 Baja": TaskPrioridad.BAJA,
        }

        context_map = {
            "PayCash": TaskContexto.PAYCASH,
            "Freelance-PA": TaskContexto.FREELANCE_PA,
            "Freelance-Google": TaskContexto.FREELANCE_GOOGLE,
            "Personal": TaskContexto.PERSONAL,
            "Workana": TaskContexto.WORKANA,
            "Estudio": TaskContexto.ESTUDIO,
        }

        bloque_map = {
            "🌅 Morning": TaskBloque.MORNING,
            "☀️ Afternoon": TaskBloque.AFTERNOON,
            "🌆 Evening": TaskBloque.EVENING,
        }

        return TaskPlanningResult(
            task_title=enrichment["task_title"],
            suggested_priority=priority_map.get(
                enrichment["suggested_priority"],
                TaskPrioridad.NORMAL
            ),
            suggested_complexity=complexity_map.get(
                enrichment["complexity"]["level"],
                TaskComplejidad.STANDARD
            ),
            suggested_energy=energy_map.get(
                enrichment["complexity"]["energy_required"],
                TaskEnergia.MEDIUM
            ),
            suggested_context=context_map.get(
                enrichment["suggested_context"],
                TaskContexto.PERSONAL
            ),
            suggested_bloque=bloque_map.get(enrichment["suggested_bloque"]),
            suggested_fecha_do=enrichment["suggested_fecha_do"],
            suggested_fecha_due=fecha_due,
            project_id=enrichment["project"]["id"],
            project_name=enrichment["project"]["name"],
            subtasks=enrichment["complexity"]["subtasks"],
            blockers=enrichment["complexity"]["blockers"],
            reasoning=self._generate_planning_reasoning(enrichment, context),
            reminders=enrichment["reminders"],
        )

    async def generate_morning_plan(self) -> MorningPlanResult:
        """Genera el plan del día usando el MorningPlannerAgent."""

        context = await self.get_context(force_refresh=True)

        # Formatear tareas pendientes
        pending_tasks = []
        for task in context.tasks_pending[:15]:
            props = task.get("properties", {})
            name = ""
            title = props.get("Tarea", {}).get("title", [])
            if title:
                name = title[0].get("text", {}).get("content", "")

            priority = props.get("Prioridad", {}).get("select", {}).get("name", "Normal")
            contexto = props.get("Contexto", {}).get("select", {}).get("name", "Personal")

            pending_tasks.append({
                "id": task.get("id"),
                "name": name,
                "prioridad": priority,
                "contexto": contexto,
            })

        # Obtener tareas incompletas de ayer
        yesterday_incomplete = []
        for task in context.tasks_overdue[:5]:
            props = task.get("properties", {})
            name = ""
            title = props.get("Tarea", {}).get("title", [])
            if title:
                name = title[0].get("text", {}).get("content", "")
            yesterday_incomplete.append({"name": name, "id": task.get("id")})

        # Generar plan
        plan = await self.morning_planner.create_morning_plan(
            pending_tasks=pending_tasks,
            calendar_events=None,  # TODO: Integrar calendario
            yesterday_incomplete=yesterday_incomplete,
        )

        return plan

    # ==================== NOTIFICACIONES PROACTIVAS ====================

    async def check_for_notifications(self) -> list[ProactiveNotification]:
        """
        Verifica si hay notificaciones proactivas que enviar.

        Returns:
            Lista de notificaciones a enviar
        """
        notifications = []
        context = await self.get_context()
        now = context.current_datetime

        # 1. Tareas vencidas
        for task in context.tasks_overdue:
            props = task.get("properties", {})
            name = ""
            title = props.get("Tarea", {}).get("title", [])
            if title:
                name = title[0].get("text", {}).get("content", "")

            notifications.append(ProactiveNotification(
                type="deadline",
                priority="high",
                title="Tarea vencida",
                message=f"La tarea '{name}' está vencida. ¿Qué hacemos?",
                related_task_id=task.get("id"),
                action_buttons=[
                    {"text": "Completar", "callback": f"task_complete:{task.get('id')}"},
                    {"text": "Reprogramar", "callback": f"task_reschedule:{task.get('id')}"},
                    {"text": "Cancelar", "callback": f"task_cancel:{task.get('id')}"},
                ],
            ))

        # 2. Recordatorio de tareas para hoy (si es horario laboral)
        if context.is_work_hours and len(context.tasks_today) > 0:
            pending_today = [
                t for t in context.tasks_today
                if t.get("properties", {}).get("Estado", {}).get("select", {}).get("name")
                not in [TaskEstado.DONE.value, TaskEstado.CANCELLED.value]
            ]

            if pending_today:
                task_names = []
                for t in pending_today[:3]:
                    props = t.get("properties", {})
                    title = props.get("Tarea", {}).get("title", [])
                    if title:
                        task_names.append(title[0].get("text", {}).get("content", ""))

                notifications.append(ProactiveNotification(
                    type="check_in",
                    priority="medium",
                    title="Check-in de tareas",
                    message=f"Tienes {len(pending_today)} tareas para hoy:\n" +
                            "\n".join(f"• {n}" for n in task_names),
                    action_buttons=[
                        {"text": "Ver tareas", "callback": "show_today_tasks"},
                        {"text": "Estoy en ello", "callback": "acknowledge"},
                    ],
                ))

        # 3. Recordatorio de gym (si es día de gym y hora apropiada)
        if not context.is_weekend and 6 <= now.hour < 8 and not context.gym_today:
            notifications.append(ProactiveNotification(
                type="reminder",
                priority="low",
                title="Gym",
                message="¿Vas al gym hoy?",
                action_buttons=[
                    {"text": "Sí, voy", "callback": "gym_confirm"},
                    {"text": "Hoy no", "callback": "gym_skip"},
                ],
            ))

        # 4. Alerta de deuda alta (si está cerca de quincena)
        if now.day in [13, 14, 28, 29, 30] and context.total_debt > 50000:
            notifications.append(ProactiveNotification(
                type="alert",
                priority="high",
                title="Alerta de deudas",
                message=f"Tu deuda total es ${context.total_debt:,.0f}. " +
                        "Revisa tu estrategia de pago.",
                action_buttons=[
                    {"text": "Ver estrategia", "callback": "debt_strategy"},
                    {"text": "Registrar pago", "callback": "debt_payment"},
                ],
            ))

        return notifications

    async def get_workload_summary(self) -> dict[str, Any]:
        """
        Genera un resumen de carga de trabajo para el lunes.

        Returns:
            Dict con resumen de la semana
        """
        context = await self.get_context(force_refresh=True)

        # Contar tareas por prioridad
        by_priority = {
            "urgente": 0,
            "alta": 0,
            "normal": 0,
            "baja": 0,
        }

        # Contar tareas por contexto
        by_context = {}

        for task in context.tasks_pending:
            props = task.get("properties", {})

            priority = props.get("Prioridad", {}).get("select", {}).get("name", "")
            if "Urgente" in priority:
                by_priority["urgente"] += 1
            elif "Alta" in priority:
                by_priority["alta"] += 1
            elif "Baja" in priority:
                by_priority["baja"] += 1
            else:
                by_priority["normal"] += 1

            contexto = props.get("Contexto", {}).get("select", {}).get("name", "Personal")
            by_context[contexto] = by_context.get(contexto, 0) + 1

        # Calcular deadlines de la semana
        deadlines_this_week = []
        week_end = context.current_datetime + timedelta(days=7)

        for task in context.tasks_pending:
            props = task.get("properties", {})
            fecha_due = props.get("Fecha Due", {}).get("date")
            if fecha_due and fecha_due.get("start"):
                due_date = datetime.strptime(fecha_due["start"], "%Y-%m-%d")
                if due_date <= week_end:
                    name = ""
                    title = props.get("Tarea", {}).get("title", [])
                    if title:
                        name = title[0].get("text", {}).get("content", "")
                    deadlines_this_week.append({
                        "name": name,
                        "due": fecha_due["start"],
                        "id": task.get("id"),
                    })

        return {
            "total_pending": len(context.tasks_pending),
            "overdue": len(context.tasks_overdue),
            "by_priority": by_priority,
            "by_context": by_context,
            "deadlines_this_week": sorted(
                deadlines_this_week,
                key=lambda x: x["due"]
            ),
            "active_projects": len(context.active_projects),
            "total_debt": context.total_debt,
        }

    # ==================== HELPERS PRIVADOS ====================

    def _calculate_urgency_score(self, message: str) -> int:
        """Calcula score de urgencia basado en keywords (0-10)."""
        message_lower = message.lower()
        score = 0

        for keyword, points in self.urgency_keywords.items():
            if keyword in message_lower:
                score += points

        return min(score, 10)

    def _detect_context(self, message: str) -> TaskContexto:
        """Detecta el contexto de trabajo del mensaje."""
        message_lower = message.lower()

        for contexto, keywords in self.context_keywords.items():
            if any(kw in message_lower for kw in keywords):
                return contexto

        return TaskContexto.PERSONAL

    async def _find_related_project(
        self,
        message: str,
        projects: list[dict],
    ) -> dict | None:
        """Busca un proyecto relacionado con el mensaje."""
        message_lower = message.lower()

        for project in projects:
            props = project.get("properties", {})
            name = ""
            title = props.get("Proyecto", {}).get("title", [])
            if title:
                name = title[0].get("text", {}).get("content", "")

            if name and name.lower() in message_lower:
                return {"id": project.get("id"), "name": name}

        return None

    def _suggest_dates(
        self,
        urgency_score: int,
        complexity: str,
        is_weekend: bool,
        context_type: TaskContexto,
    ) -> tuple[str | None, str | None]:
        """Sugiere fechas de ejecución y deadline."""
        now = datetime.now()

        # Calcular próximo día laboral
        if is_weekend:
            # Si es sábado, próximo lunes
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            next_workday = now + timedelta(days=days_until_monday)
        else:
            next_workday = now

        # Sugerir fecha_do basada en urgencia
        if urgency_score >= 7:
            # Muy urgente: hoy o próximo día laboral
            fecha_do = next_workday.strftime("%Y-%m-%d")
            fecha_due = (next_workday + timedelta(days=1)).strftime("%Y-%m-%d")
        elif urgency_score >= 4:
            # Urgente: dentro de 2-3 días
            fecha_do = (next_workday + timedelta(days=1)).strftime("%Y-%m-%d")
            fecha_due = (next_workday + timedelta(days=3)).strftime("%Y-%m-%d")
        elif complexity in ["heavy", "epic"]:
            # Tarea compleja: dar más tiempo
            fecha_do = (next_workday + timedelta(days=2)).strftime("%Y-%m-%d")
            fecha_due = (next_workday + timedelta(days=7)).strftime("%Y-%m-%d")
        else:
            # Normal: sin fechas específicas
            fecha_do = None
            fecha_due = None

        return fecha_do, fecha_due

    def _suggest_priority(
        self,
        urgency_score: int,
        has_deadline: bool,
        project_match: dict | None,
    ) -> TaskPrioridad:
        """Sugiere prioridad basada en múltiples factores."""

        if urgency_score >= 7:
            return TaskPrioridad.URGENTE
        elif urgency_score >= 4 or has_deadline:
            return TaskPrioridad.ALTA
        elif project_match:
            # Tareas con proyecto tienen prioridad normal-alta
            return TaskPrioridad.NORMAL
        else:
            return TaskPrioridad.NORMAL

    def _suggest_time_block(
        self,
        energy_required: str,
        is_work_hours: bool,
    ) -> TaskBloque | None:
        """Sugiere bloque de tiempo basado en energía requerida."""

        if energy_required == "deep_work":
            return TaskBloque.MORNING
        elif energy_required == "medium":
            return TaskBloque.AFTERNOON
        elif energy_required == "low":
            return TaskBloque.EVENING

        return None

    def _generate_task_reminders(
        self,
        task_title: str,
        priority: TaskPrioridad,
        fecha_do: str | None,
        fecha_due: str | None,
    ) -> list[dict]:
        """Genera recordatorios sugeridos para una tarea."""
        reminders = []

        if fecha_due:
            due_date = datetime.strptime(fecha_due, "%Y-%m-%d")

            # Recordatorio un día antes del deadline
            reminder_date = due_date - timedelta(days=1)
            reminders.append({
                "datetime": reminder_date.strftime("%Y-%m-%d 09:00"),
                "message": f"Mañana vence: {task_title}",
            })

            # Para tareas urgentes, recordatorio adicional
            if priority in [TaskPrioridad.URGENTE, TaskPrioridad.ALTA]:
                reminders.append({
                    "datetime": due_date.strftime("%Y-%m-%d 07:00"),
                    "message": f"HOY vence: {task_title}",
                })

        return reminders

    def _generate_planning_reasoning(
        self,
        enrichment: dict,
        context: UserContext,
    ) -> str:
        """Genera explicación del razonamiento de planificación."""

        reasons = []

        # Explicar prioridad
        urgency = enrichment["urgency_score"]
        if urgency >= 7:
            reasons.append(f"Prioridad urgente por keywords detectados (score: {urgency})")
        elif urgency >= 4:
            reasons.append(f"Prioridad alta por indicadores de urgencia (score: {urgency})")

        # Explicar contexto
        ctx = enrichment["suggested_context"]
        reasons.append(f"Contexto detectado: {ctx}")

        # Explicar proyecto
        if enrichment["project"]["name"]:
            reasons.append(f"Proyecto relacionado: {enrichment['project']['name']}")

        # Explicar fechas
        if context.is_weekend:
            reasons.append("Es fin de semana, fechas programadas para el lunes")

        # Explicar complejidad
        complexity = enrichment["complexity"]
        if complexity["should_divide"]:
            reasons.append(f"Tarea compleja ({complexity['level']}), dividir en {len(complexity['subtasks'])} subtareas")

        return " | ".join(reasons)


# Singleton
_orchestrator: AgentOrchestrator | None = None


def get_orchestrator() -> AgentOrchestrator:
    """Obtiene la instancia del orquestador."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator
