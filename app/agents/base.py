"""Configuración base de DSPy con Gemini."""

import logging
import time
from functools import wraps
from typing import Any, Callable

import dspy
import google.generativeai as genai

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Flag para saber si DSPy está configurado
_dspy_configured = False


def setup_dspy() -> None:
    """Configura DSPy con Gemini como LLM."""
    global _dspy_configured

    if _dspy_configured:
        return

    # Configurar Gemini API
    genai.configure(api_key=settings.gemini_api_key)

    # Configurar DSPy con Gemini
    lm = dspy.LM(
        model="gemini/gemini-1.5-flash",
        api_key=settings.gemini_api_key,
        temperature=0.7,
        max_tokens=1024,
    )
    dspy.configure(lm=lm)

    _dspy_configured = True
    logger.info("DSPy configurado con Gemini")


def ensure_dspy_configured(func: Callable) -> Callable:
    """Decorador que asegura que DSPy esté configurado."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        setup_dspy()
        return await func(*args, **kwargs)
    return wrapper


class BaseAgent:
    """Clase base para todos los agents."""

    name: str = "BaseAgent"

    def __init__(self):
        setup_dspy()
        self.logger = logging.getLogger(f"agents.{self.name}")

    async def execute(self, *args, **kwargs) -> Any:
        """Ejecuta el agent y retorna el resultado."""
        raise NotImplementedError("Subclases deben implementar execute()")

    async def execute_with_metrics(self, *args, **kwargs) -> tuple[Any, dict]:
        """Ejecuta el agent y retorna resultado + métricas."""
        start_time = time.time()
        error_message = None
        result = None

        try:
            result = await self.execute(*args, **kwargs)
            success = True
        except Exception as e:
            success = False
            error_message = str(e)
            self.logger.error(f"Error en {self.name}: {e}")
            raise

        finally:
            execution_time = int((time.time() - start_time) * 1000)

            metrics = {
                "agent_name": self.name,
                "execution_time_ms": execution_time,
                "success": success,
                "error_message": error_message,
            }

        return result, metrics


# ==================== SIGNATURES COMUNES ====================


class ClassifyMessage(dspy.Signature):
    """Clasifica un mensaje del usuario en una categoría."""

    message: str = dspy.InputField(desc="El mensaje del usuario a clasificar")
    context: str = dspy.InputField(
        desc="Contexto adicional sobre el usuario o la conversación",
        default="",
    )

    category: str = dspy.OutputField(
        desc="Categoría: task, idea, event, note, question, expense, gym, food"
    )
    confidence: float = dspy.OutputField(
        desc="Nivel de confianza de 0.0 a 1.0"
    )
    reasoning: str = dspy.OutputField(
        desc="Breve explicación del razonamiento"
    )


class ExtractTaskInfo(dspy.Signature):
    """Extrae información de una tarea de un mensaje."""

    message: str = dspy.InputField(desc="El mensaje que contiene la tarea")

    title: str = dspy.OutputField(desc="Título conciso de la tarea")
    description: str = dspy.OutputField(
        desc="Descripción más detallada si aplica"
    )
    priority: str = dspy.OutputField(desc="Prioridad: High, Medium, Low")
    due_date: str = dspy.OutputField(
        desc="Fecha límite en formato YYYY-MM-DD o 'none' si no se menciona"
    )
    project_hint: str = dspy.OutputField(
        desc="Posible proyecto relacionado basado en el contenido"
    )


class AnalyzeComplexity(dspy.Signature):
    """Analiza la complejidad de una tarea."""

    task_description: str = dspy.InputField(desc="Descripción de la tarea")

    complexity: str = dspy.OutputField(desc="Complejidad: simple, medium, complex")
    estimated_minutes: int = dspy.OutputField(
        desc="Estimación de tiempo en minutos"
    )
    subtasks: str = dspy.OutputField(
        desc="Lista de subtareas sugeridas separadas por '|' si es compleja"
    )
    blockers: str = dspy.OutputField(
        desc="Posibles bloqueadores o dependencias"
    )


class AnalyzeSpending(dspy.Signature):
    """Analiza una compra potencial."""

    purchase_description: str = dspy.InputField(
        desc="Descripción del item y precio"
    )
    monthly_budget: float = dspy.InputField(
        desc="Presupuesto mensual disponible"
    )
    current_debt: float = dspy.InputField(
        desc="Deuda actual total"
    )

    necessity_score: int = dspy.OutputField(
        desc="Puntuación de necesidad de 1-10"
    )
    budget_impact: str = dspy.OutputField(
        desc="Impacto en el presupuesto: minimal, moderate, significant, critical"
    )
    recommendation: str = dspy.OutputField(
        desc="Recomendación: buy, wait, wishlist, skip"
    )
    honest_questions: str = dspy.OutputField(
        desc="2-3 preguntas honestas para reflexionar sobre la compra"
    )


class GenerateMorningPlan(dspy.Signature):
    """Genera el plan del día."""

    pending_tasks: str = dspy.InputField(desc="Lista de tareas pendientes")
    calendar_events: str = dspy.InputField(
        desc="Eventos del calendario de hoy"
    )
    yesterday_incomplete: str = dspy.InputField(
        desc="Tareas incompletas de ayer"
    )

    top_priorities: str = dspy.OutputField(
        desc="Las 3 prioridades principales del día"
    )
    suggested_schedule: str = dspy.OutputField(
        desc="Horario sugerido para las tareas principales"
    )
    motivation_message: str = dspy.OutputField(
        desc="Mensaje motivacional breve y personalizado"
    )


class AnalyzeNutrition(dspy.Signature):
    """Analiza la nutrición del día."""

    meals_description: str = dspy.InputField(
        desc="Descripción de todas las comidas del día"
    )
    fitness_goal: str = dspy.InputField(
        desc="Objetivo de fitness: lose_weight, maintain, gain_muscle"
    )

    calories_estimate: int = dspy.OutputField(
        desc="Estimación de calorías totales"
    )
    protein_estimate: int = dspy.OutputField(
        desc="Estimación de proteína en gramos"
    )
    day_rating: str = dspy.OutputField(
        desc="Calificación del día: poor, okay, good, excellent"
    )
    suggestions: str = dspy.OutputField(
        desc="Sugerencias para mejorar"
    )


# ==================== MÓDULOS DSPy ====================


class MessageClassifier(dspy.Module):
    """Módulo para clasificar mensajes."""

    def __init__(self):
        super().__init__()
        self.classify = dspy.ChainOfThought(ClassifyMessage)

    def forward(self, message: str, context: str = "") -> dspy.Prediction:
        return self.classify(message=message, context=context)


class TaskExtractor(dspy.Module):
    """Módulo para extraer información de tareas."""

    def __init__(self):
        super().__init__()
        self.extract = dspy.ChainOfThought(ExtractTaskInfo)

    def forward(self, message: str) -> dspy.Prediction:
        return self.extract(message=message)


class ComplexityAnalyzer(dspy.Module):
    """Módulo para analizar complejidad de tareas."""

    def __init__(self):
        super().__init__()
        self.analyze = dspy.ChainOfThought(AnalyzeComplexity)

    def forward(self, task_description: str) -> dspy.Prediction:
        return self.analyze(task_description=task_description)


class SpendingAnalyzer(dspy.Module):
    """Módulo para analizar compras."""

    def __init__(self):
        super().__init__()
        self.analyze = dspy.ChainOfThought(AnalyzeSpending)

    def forward(
        self,
        purchase_description: str,
        monthly_budget: float,
        current_debt: float,
    ) -> dspy.Prediction:
        return self.analyze(
            purchase_description=purchase_description,
            monthly_budget=monthly_budget,
            current_debt=current_debt,
        )


class MorningPlanner(dspy.Module):
    """Módulo para generar el plan del día."""

    def __init__(self):
        super().__init__()
        self.plan = dspy.ChainOfThought(GenerateMorningPlan)

    def forward(
        self,
        pending_tasks: str,
        calendar_events: str,
        yesterday_incomplete: str,
    ) -> dspy.Prediction:
        return self.plan(
            pending_tasks=pending_tasks,
            calendar_events=calendar_events,
            yesterday_incomplete=yesterday_incomplete,
        )


class NutritionAnalyzer(dspy.Module):
    """Módulo para analizar nutrición."""

    def __init__(self):
        super().__init__()
        self.analyze = dspy.ChainOfThought(AnalyzeNutrition)

    def forward(
        self,
        meals_description: str,
        fitness_goal: str = "maintain",
    ) -> dspy.Prediction:
        return self.analyze(
            meals_description=meals_description,
            fitness_goal=fitness_goal,
        )
