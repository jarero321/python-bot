"""Intent Router Agent - Clasifica intención del usuario y enruta al flujo correcto."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import dspy

from app.agents.base import BaseAgent, setup_dspy

logger = logging.getLogger(__name__)


class UserIntent(str, Enum):
    """Intenciones posibles del usuario."""

    # Tareas y productividad
    TASK_CREATE = "task_create"      # Crear nueva tarea
    TASK_UPDATE = "task_update"      # Actualizar tarea existente
    TASK_DELETE = "task_delete"      # Eliminar/completar tarea
    TASK_QUERY = "task_query"        # Preguntar sobre tareas
    TASK_STATUS_CHANGE = "task_status_change"  # Cambiar estado de tarea

    # Ideas y captura
    IDEA = "idea"                    # Capturar una idea
    NOTE = "note"                    # Guardar una nota

    # Recordatorios
    REMINDER_CREATE = "reminder_create"  # Crear un recordatorio
    REMINDER_QUERY = "reminder_query"    # Consultar recordatorios

    # Planificación
    PLAN_TODAY = "plan_today"            # Planificar hoy
    PLAN_TOMORROW = "plan_tomorrow"      # Planificar mañana
    PLAN_WEEK = "plan_week"              # Ver/planificar semana
    PRIORITIZE = "prioritize"            # Ayuda a priorizar tareas
    RESCHEDULE = "reschedule"            # Reprogramar una tarea
    WORKLOAD_CHECK = "workload_check"    # Revisar carga de trabajo

    # Finanzas
    EXPENSE_LOG = "expense_log"      # Registrar un gasto
    EXPENSE_ANALYZE = "expense_analyze"  # Analizar compra potencial
    DEBT_QUERY = "debt_query"        # Preguntar sobre deudas

    # Salud y fitness
    GYM_LOG = "gym_log"              # Registrar workout
    GYM_QUERY = "gym_query"          # Preguntar sobre entrenamientos
    NUTRITION_LOG = "nutrition_log"  # Registrar comida
    NUTRITION_QUERY = "nutrition_query"  # Preguntar sobre nutrición

    # Proyectos y estudio
    PROJECT_CREATE = "project_create"  # Crear nuevo proyecto
    PROJECT_UPDATE = "project_update"  # Actualizar proyecto existente
    PROJECT_DELETE = "project_delete"  # Eliminar/cerrar proyecto
    PROJECT_QUERY = "project_query"  # Preguntar sobre proyectos
    STUDY_SESSION = "study_session"  # Iniciar sesión de estudio

    # General
    GREETING = "greeting"            # Saludo
    HELP = "help"                    # Pedir ayuda
    STATUS = "status"                # Estado del sistema
    UNKNOWN = "unknown"              # No se pudo clasificar


class ClassifyIntent(dspy.Signature):
    """Clasifica la intención del usuario basándose en su mensaje."""

    message: str = dspy.InputField(
        desc="El mensaje del usuario en español"
    )
    conversation_context: str = dspy.InputField(
        desc="Contexto de mensajes anteriores si existe",
        default=""
    )

    intent: str = dspy.OutputField(
        desc="""La intención del usuario. Debe ser una de:
        - task_create: quiere crear/agregar una tarea o algo que hacer
        - task_update: quiere actualizar o modificar una tarea existente
        - task_delete: quiere eliminar, completar o marcar como hecha una tarea
        - task_query: pregunta sobre sus tareas pendientes
        - idea: tiene una idea que quiere guardar
        - note: quiere guardar una nota o información
        - reminder_create: quiere crear un RECORDATORIO (ej: "recuérdame X", "ponme un recordatorio")
        - reminder_query: pregunta sobre sus recordatorios
        - plan_today: quiere planificar HOY (ej: "planifica mi día", "qué hago hoy", "organiza mi día", "ayúdame a planificar")
        - plan_tomorrow: quiere planificar MAÑANA específicamente (ej: "qué hago mañana", "planifica mañana")
        - plan_week: quiere ver o planificar su semana (ej: "cómo va mi semana", "qué tengo esta semana")
        - prioritize: necesita ayuda para priorizar entre tareas (ej: "qué hago primero", "X o Y primero")
        - reschedule: quiere mover/reprogramar una tarea (ej: "mueve X para mañana", "necesito más tiempo")
        - workload_check: quiere revisar su carga de trabajo (ej: "cuánto tengo pendiente", "estoy sobrecargado")
        - expense_log: quiere registrar un gasto que ya hizo
        - expense_analyze: menciona algo que QUIERE comprar (con precio $)
        - debt_query: pregunta sobre sus deudas
        - gym_log: quiere registrar su entrenamiento de hoy
        - gym_query: pregunta sobre su historial de gym o pesos levantados
        - nutrition_log: quiere registrar lo que comió (desayuno, comida, cena)
        - nutrition_query: pregunta sobre su alimentación
        - project_create: quiere CREAR un nuevo proyecto
        - project_update: quiere modificar o actualizar un proyecto existente
        - project_delete: quiere eliminar, cerrar o archivar un proyecto
        - project_query: pregunta sobre sus proyectos existentes
        - study_session: quiere estudiar o hacer deep work
        - greeting: es un saludo simple
        - help: pide ayuda sobre el bot
        - status: pregunta por el estado del sistema
        - unknown: no encaja en ninguna categoría
        """
    )
    confidence: float = dspy.OutputField(
        desc="Confianza de 0.0 a 1.0 en la clasificación"
    )
    entities: str = dspy.OutputField(
        desc="""Entidades extraídas del mensaje en formato key:value separados por |
        Ejemplos:
        - 'amount:3000|item:airpods' para compras
        - 'task:terminar reporte|date:mañana|priority:normal' para tareas
        - 'task:llamar al cliente|priority:urgent' para tareas urgentes
        - 'meal:desayuno|food:huevos con pan' para nutrición

        Para tareas, SIEMPRE extraer priority si se menciona:
        - urgent: "urgente", "crítico", "inmediato", "ASAP", "ya"
        - high: "alta prioridad", "importante", "pronto"
        - normal: sin indicador especial (default)
        - low: "baja prioridad", "cuando pueda", "sin prisa"

        Dejar vacío si no hay entidades claras."""
    )
    suggested_response: str = dspy.OutputField(
        desc="Respuesta sugerida corta si la intención es simple (greeting, help)"
    )


@dataclass
class IntentResult:
    """Resultado del análisis de intención."""

    intent: UserIntent
    confidence: float
    entities: dict[str, str]
    suggested_response: str | None
    raw_message: str

    @property
    def is_high_confidence(self) -> bool:
        """Retorna True si la confianza es alta (>0.7)."""
        return self.confidence >= 0.7

    @property
    def needs_confirmation(self) -> bool:
        """Retorna True si debería confirmar con el usuario."""
        return 0.4 <= self.confidence < 0.7


class IntentClassifier(dspy.Module):
    """Módulo DSPy para clasificar intenciones."""

    def __init__(self):
        super().__init__()
        self.classify = dspy.ChainOfThought(ClassifyIntent)

    def forward(self, message: str, conversation_context: str = "") -> dspy.Prediction:
        return self.classify(
            message=message,
            conversation_context=conversation_context
        )


class IntentRouterAgent(BaseAgent):
    """
    Agent que analiza mensajes del usuario y determina la intención.

    Uso:
        router = IntentRouterAgent()
        result = await router.execute("me quiero comprar unos airpods por $3000")
        print(result.intent)  # UserIntent.EXPENSE_ANALYZE
        print(result.entities)  # {'amount': '3000', 'item': 'airpods'}
    """

    name = "IntentRouter"

    def __init__(self):
        super().__init__()
        self.classifier = IntentClassifier()

    def _parse_entities(self, entities_str: str) -> dict[str, str]:
        """Parsea el string de entidades a diccionario."""
        if not entities_str or entities_str.lower() in ["none", "vacío", ""]:
            return {}

        entities = {}
        try:
            pairs = entities_str.split("|")
            for pair in pairs:
                if ":" in pair:
                    key, value = pair.split(":", 1)
                    entities[key.strip().lower()] = value.strip()
        except Exception as e:
            self.logger.warning(f"Error parseando entidades '{entities_str}': {e}")

        return entities

    def _normalize_intent(self, intent_str: str) -> UserIntent:
        """Normaliza el string de intent al enum."""
        intent_str = intent_str.lower().strip()

        # Mapeo de variaciones comunes
        intent_map = {
            # Tareas
            "task_create": UserIntent.TASK_CREATE,
            "task create": UserIntent.TASK_CREATE,
            "create_task": UserIntent.TASK_CREATE,
            "nueva_tarea": UserIntent.TASK_CREATE,
            "task_update": UserIntent.TASK_UPDATE,
            "task update": UserIntent.TASK_UPDATE,
            "task_delete": UserIntent.TASK_DELETE,
            "task delete": UserIntent.TASK_DELETE,
            "task_query": UserIntent.TASK_QUERY,
            "task query": UserIntent.TASK_QUERY,
            "task_status_change": UserIntent.TASK_STATUS_CHANGE,
            "task status change": UserIntent.TASK_STATUS_CHANGE,
            # Ideas y notas
            "idea": UserIntent.IDEA,
            "note": UserIntent.NOTE,
            "nota": UserIntent.NOTE,
            # Recordatorios
            "reminder_create": UserIntent.REMINDER_CREATE,
            "reminder create": UserIntent.REMINDER_CREATE,
            "create_reminder": UserIntent.REMINDER_CREATE,
            "recordatorio": UserIntent.REMINDER_CREATE,
            "reminder_query": UserIntent.REMINDER_QUERY,
            "reminder query": UserIntent.REMINDER_QUERY,
            # Finanzas
            "expense_log": UserIntent.EXPENSE_LOG,
            "expense log": UserIntent.EXPENSE_LOG,
            "expense_analyze": UserIntent.EXPENSE_ANALYZE,
            "expense analyze": UserIntent.EXPENSE_ANALYZE,
            "compra": UserIntent.EXPENSE_ANALYZE,
            "debt_query": UserIntent.DEBT_QUERY,
            "debt query": UserIntent.DEBT_QUERY,
            # Gym
            "gym_log": UserIntent.GYM_LOG,
            "gym log": UserIntent.GYM_LOG,
            "gym_query": UserIntent.GYM_QUERY,
            "gym query": UserIntent.GYM_QUERY,
            # Nutrición
            "nutrition_log": UserIntent.NUTRITION_LOG,
            "nutrition log": UserIntent.NUTRITION_LOG,
            "nutrition_query": UserIntent.NUTRITION_QUERY,
            "nutrition query": UserIntent.NUTRITION_QUERY,
            # Proyectos
            "project_create": UserIntent.PROJECT_CREATE,
            "project create": UserIntent.PROJECT_CREATE,
            "create_project": UserIntent.PROJECT_CREATE,
            "nuevo_proyecto": UserIntent.PROJECT_CREATE,
            "project_update": UserIntent.PROJECT_UPDATE,
            "project update": UserIntent.PROJECT_UPDATE,
            "project_delete": UserIntent.PROJECT_DELETE,
            "project delete": UserIntent.PROJECT_DELETE,
            "project_query": UserIntent.PROJECT_QUERY,
            "project query": UserIntent.PROJECT_QUERY,
            # Estudio
            "study_session": UserIntent.STUDY_SESSION,
            "study session": UserIntent.STUDY_SESSION,
            # Planificación
            "plan_tomorrow": UserIntent.PLAN_TOMORROW,
            "plan tomorrow": UserIntent.PLAN_TOMORROW,
            "planificar_manana": UserIntent.PLAN_TOMORROW,
            "plan_week": UserIntent.PLAN_WEEK,
            "plan week": UserIntent.PLAN_WEEK,
            "planificar_semana": UserIntent.PLAN_WEEK,
            "prioritize": UserIntent.PRIORITIZE,
            "priorizar": UserIntent.PRIORITIZE,
            "reschedule": UserIntent.RESCHEDULE,
            "reprogramar": UserIntent.RESCHEDULE,
            "workload_check": UserIntent.WORKLOAD_CHECK,
            "workload check": UserIntent.WORKLOAD_CHECK,
            "carga_trabajo": UserIntent.WORKLOAD_CHECK,
            # General
            "greeting": UserIntent.GREETING,
            "saludo": UserIntent.GREETING,
            "help": UserIntent.HELP,
            "ayuda": UserIntent.HELP,
            "status": UserIntent.STATUS,
            "estado": UserIntent.STATUS,
        }

        return intent_map.get(intent_str, UserIntent.UNKNOWN)

    async def execute(
        self,
        message: str,
        conversation_context: str = ""
    ) -> IntentResult:
        """
        Analiza un mensaje y determina la intención del usuario.

        Args:
            message: El mensaje del usuario
            conversation_context: Contexto de mensajes anteriores

        Returns:
            IntentResult con la intención, confianza y entidades
        """
        self.logger.info(f"Clasificando mensaje: {message[:50]}...")
        print(f"[INTENT] Ejecutando classifier...")

        try:
            # Ejecutar clasificación con DSPy
            result = self.classifier(
                message=message,
                conversation_context=conversation_context
            )
            print(f"[INTENT] Resultado raw: {result}")

            # Parsear resultados
            intent = self._normalize_intent(result.intent)

            # Manejar confianza
            try:
                confidence = float(result.confidence)
                confidence = max(0.0, min(1.0, confidence))  # Clamp 0-1
            except (ValueError, TypeError):
                confidence = 0.5

            entities = self._parse_entities(result.entities)

            # Si es TASK_CREATE y no hay prioridad, intentar extraerla por keywords
            if intent == UserIntent.TASK_CREATE and "priority" not in entities:
                detected_priority = self._extract_priority(message)
                if detected_priority:
                    entities["priority"] = detected_priority
                    self.logger.info(f"Prioridad detectada por keywords: {detected_priority}")

            suggested_response = result.suggested_response
            if suggested_response and suggested_response.lower() in ["none", "n/a", ""]:
                suggested_response = None

            self.logger.info(
                f"Intent: {intent.value}, Confidence: {confidence:.2f}, "
                f"Entities: {entities}"
            )

            return IntentResult(
                intent=intent,
                confidence=confidence,
                entities=entities,
                suggested_response=suggested_response,
                raw_message=message,
            )

        except Exception as e:
            print(f"[INTENT] ERROR en clasificación: {e}")
            import traceback
            traceback.print_exc()
            self.logger.error(f"Error clasificando mensaje: {e}")
            # Fallback a UNKNOWN con baja confianza
            return IntentResult(
                intent=UserIntent.UNKNOWN,
                confidence=0.0,
                entities={},
                suggested_response=None,
                raw_message=message,
            )

    async def get_fallback_intent(self, message: str) -> IntentResult:
        """
        Clasificación de fallback basada en reglas simples.
        Útil cuando el LLM falla o para mensajes muy simples.
        """
        text_lower = message.lower().strip()

        # Saludos
        greetings = ["hola", "hey", "hi", "buenos", "buenas", "qué tal", "que tal"]
        if any(g in text_lower for g in greetings):
            return IntentResult(
                intent=UserIntent.GREETING,
                confidence=0.9,
                entities={},
                suggested_response="¡Hola! ¿En qué te puedo ayudar?",
                raw_message=message,
            )

        # Ayuda
        if "ayuda" in text_lower or "help" in text_lower:
            return IntentResult(
                intent=UserIntent.HELP,
                confidence=0.9,
                entities={},
                suggested_response=None,
                raw_message=message,
            )

        # Compras (precio detectado)
        if "$" in message or "pesos" in text_lower:
            return IntentResult(
                intent=UserIntent.EXPENSE_ANALYZE,
                confidence=0.8,
                entities=self._extract_price(message),
                suggested_response=None,
                raw_message=message,
            )

        # Gym
        gym_words = ["gym", "entreno", "entrenamiento", "workout", "ejercicio", "pesas"]
        if any(w in text_lower for w in gym_words):
            return IntentResult(
                intent=UserIntent.GYM_LOG,
                confidence=0.7,
                entities={},
                suggested_response=None,
                raw_message=message,
            )

        # Comida
        food_words = ["comí", "desayuné", "almorcé", "cené", "comida", "desayuno", "cena"]
        if any(w in text_lower for w in food_words):
            return IntentResult(
                intent=UserIntent.NUTRITION_LOG,
                confidence=0.7,
                entities={},
                suggested_response=None,
                raw_message=message,
            )

        # Proyectos
        project_words = ["crear proyecto", "nuevo proyecto", "project", "iniciar proyecto"]
        if any(p in text_lower for p in project_words):
            return IntentResult(
                intent=UserIntent.PROJECT_CREATE,
                confidence=0.8,
                entities=self._extract_project_info(message),
                suggested_response=None,
                raw_message=message,
            )

        # Default: probablemente una tarea o nota
        task_indicators = ["tengo que", "debo", "necesito", "hacer", "terminar", "completar", "tarea", "crear tarea"]
        if any(t in text_lower for t in task_indicators):
            entities = {}
            # Extraer prioridad si existe
            detected_priority = self._extract_priority(message)
            if detected_priority:
                entities["priority"] = detected_priority
            return IntentResult(
                intent=UserIntent.TASK_CREATE,
                confidence=0.6,
                entities=entities,
                suggested_response=None,
                raw_message=message,
            )

        # Unknown
        return IntentResult(
            intent=UserIntent.UNKNOWN,
            confidence=0.3,
            entities={},
            suggested_response=None,
            raw_message=message,
        )

    def _extract_priority(self, message: str) -> str | None:
        """Extrae prioridad del mensaje basado en keywords."""
        text_lower = message.lower()

        # Urgente
        urgent_keywords = [
            "urgente", "crítico", "critico", "inmediato", "asap",
            "ya mismo", "ahora", "cuanto antes", "emergencia"
        ]
        if any(kw in text_lower for kw in urgent_keywords):
            return "urgent"

        # Alta
        high_keywords = [
            "importante", "alta prioridad", "prioridad alta",
            "pronto", "lo antes posible"
        ]
        if any(kw in text_lower for kw in high_keywords):
            return "high"

        # Baja
        low_keywords = [
            "baja prioridad", "prioridad baja", "cuando pueda",
            "sin prisa", "no urgente", "algún día", "algun dia"
        ]
        if any(kw in text_lower for kw in low_keywords):
            return "low"

        return None

    def _extract_price(self, message: str) -> dict[str, str]:
        """Extrae precio del mensaje."""
        import re

        entities = {}

        # Buscar patrones de precio
        patterns = [
            r'\$\s*([\d,]+(?:\.\d{2})?)',  # $3000 o $3,000.00
            r'([\d,]+)\s*pesos',            # 3000 pesos
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                amount = match.group(1).replace(",", "")
                entities["amount"] = amount
                break

        return entities

    def _extract_project_info(self, message: str) -> dict[str, str]:
        """Extrae información del proyecto del mensaje."""
        import re

        entities = {}
        text_lower = message.lower()

        # Patrones para extraer nombre del proyecto
        # "crear proyecto PayCash" -> project_name: "PayCash"
        # "nuevo proyecto API Integration - trabajo" -> project_name: "API Integration", type: "trabajo"
        patterns = [
            r'(?:crear|nuevo|iniciar)\s+proyecto\s+["\']?([^"\',-]+)["\']?',
            r'proyecto\s+["\']?([^"\',-]+)["\']?',
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                entities["project_name"] = match.group(1).strip()
                break

        # Detectar tipo de proyecto
        type_keywords = {
            "trabajo": ["trabajo", "work", "paycash", "oficina"],
            "freelance": ["freelance", "cliente", "workana"],
            "personal": ["personal", "casa", "propio"],
            "estudio": ["estudio", "aprender", "curso", "estudiar"],
            "side_project": ["side project", "hobby", "experimento"],
        }

        for project_type, keywords in type_keywords.items():
            if any(kw in text_lower for kw in keywords):
                entities["project_type"] = project_type
                break

        return entities


# Singleton
_intent_router: IntentRouterAgent | None = None


def get_intent_router() -> IntentRouterAgent:
    """Obtiene la instancia del IntentRouter."""
    global _intent_router
    if _intent_router is None:
        _intent_router = IntentRouterAgent()
    return _intent_router
