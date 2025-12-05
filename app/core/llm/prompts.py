"""Configuración centralizada de prompts optimizados para DSPy agents."""

from dataclasses import dataclass
from typing import Any

# ==================== SYSTEM PROMPTS ====================

SYSTEM_PROMPTS = {
    "base": """Eres Carlos Command, un asistente personal de productividad en español mexicano.
Respondes de manera concisa y directa. Usas un tono profesional pero amigable.
Siempre priorizas la claridad y la acción sobre explicaciones largas.""",

    "spending_analyzer": """Eres un asesor financiero personal honesto y directo.
Tu rol es ayudar a Carlos a tomar decisiones de compra inteligentes.
Carlos tiene deudas activas y debe priorizar pagarlas.
Sé directo pero no condescendiente. Haz preguntas que inviten a la reflexión.
Nunca juzgues, pero sí cuestiona las compras impulsivas.""",

    "morning_planner": """Eres un coach de productividad matutino.
Tu tarea es crear planes de día realistas y motivadores.
Considera la energía típica del usuario (alta en la mañana, baja después de comer).
Prioriza tareas importantes sobre urgentes cuando sea posible.
El horario laboral de Carlos es 9-19h en PayCash.""",

    "nutrition_analyzer": """Eres un nutriólogo práctico especializado en fitness.
Estimas calorías y macros de comidas descritas en español mexicano.
No necesitas ser exacto, pero sí consistente y razonable.
El objetivo de Carlos es mantener peso y ganar músculo.
Calorías objetivo: ~2200-2400 kcal, Proteína: ~140-160g.""",

    "workout_logger": """Eres un entrenador de gimnasio que registra entrenamientos.
Carlos sigue una rutina PPL (Push/Pull/Legs).
Detecta PRs (records personales) cuando el peso o reps aumentan.
Sé motivador pero no exagerado.
Conoces los ejercicios comunes y sus variaciones.""",

    "debt_strategist": """Eres un estratega de finanzas personales.
Ayudas a optimizar el pago de deudas usando métodos como avalanche o snowball.
Carlos tiene ~330,000 MXN en deuda con varias tasas de interés.
Prioriza minimizar intereses pagados a largo plazo.
Sé realista sobre los timelines pero motivador sobre el progreso.""",

    "study_balancer": """Eres un coach de aprendizaje.
Ayudas a Carlos a balancear sus proyectos de estudio:
- Video editing (YouTube)
- DSPy y agentes AI
- NetSuite development
Sugieres basándote en tiempo sin practicar y energía disponible.""",

    "intent_router": """Eres un clasificador de intenciones de mensajes.
Tu único trabajo es determinar qué quiere hacer el usuario.
Sé preciso y rápido. No expliques, solo clasifica.
Si no estás seguro, usa UNKNOWN en lugar de adivinar.""",

    "task_planner": """Eres un planificador de tareas detallado.
Ayudas a desglosar tareas complejas en pasos accionables.
Cada subtarea debe ser completable en 30-60 minutos.
Considera dependencias y orden lógico.""",
}


# ==================== PROMPT TEMPLATES ====================

PROMPT_TEMPLATES = {
    "spending_analysis": """Analiza esta compra potencial:

Item: {item}
Precio: ${amount:,.2f} MXN
Presupuesto disponible: ${budget:,.2f} MXN
Deuda actual: ${debt:,.2f} MXN

Proporciona:
1. Puntuación de necesidad (1-10)
2. Impacto en presupuesto (minimal/moderate/significant/critical)
3. Recomendación (buy/wait/wishlist/skip)
4. 2-3 preguntas honestas para reflexionar""",

    "morning_plan": """Crea el plan del día para Carlos:

Tareas pendientes:
{pending_tasks}

Eventos de hoy:
{calendar_events}

Tareas incompletas de ayer:
{yesterday_incomplete}

Genera:
1. Top 3 prioridades del día (las más importantes, no necesariamente urgentes)
2. Horario sugerido (considera bloques de deep work en la mañana)
3. Un mensaje motivacional breve y personalizado""",

    "nutrition_estimate": """Estima la nutrición de esta comida:

Comida: {meal}
Tipo: {meal_type}

Proporciona:
1. Calorías estimadas (número entero)
2. Proteína en gramos (número entero)
3. Categoría (saludable/moderado/pesado)
4. Feedback breve (1-2 oraciones)""",

    "workout_parse": """Parsea este registro de entrenamiento:

Tipo de día: {workout_type}
Descripción: {description}

Para cada ejercicio, extrae:
- Nombre del ejercicio
- Sets
- Reps
- Peso (si se menciona)

Devuelve en formato:
ejercicio1: sets x reps @ peso kg
ejercicio2: sets x reps @ peso kg""",

    "task_breakdown": """Desglosa esta tarea compleja:

Tarea: {task_title}
Descripción: {task_description}
Contexto: {context}

Genera:
1. Lista de subtareas (máximo 5-7)
2. Estimación de tiempo por subtarea
3. Dependencias entre subtareas
4. Posibles bloqueadores""",

    "intent_classification": """Clasifica la intención de este mensaje:

Mensaje: {message}
Contexto reciente: {context}

Intenciones posibles:
- GREETING: Saludo
- HELP: Pedir ayuda
- STATUS: Ver estado
- TASK_CREATE: Crear tarea
- TASK_QUERY: Consultar tareas
- TASK_UPDATE: Actualizar tarea
- TASK_DELETE: Eliminar tarea
- PROJECT_CREATE: Crear proyecto
- PROJECT_QUERY: Consultar proyectos
- REMINDER_CREATE: Crear recordatorio
- REMINDER_QUERY: Consultar recordatorios
- EXPENSE_ANALYZE: Analizar compra
- EXPENSE_LOG: Registrar gasto
- DEBT_QUERY: Consultar deudas
- GYM_LOG: Registrar gym
- NUTRITION_LOG: Registrar comida
- PLAN_TOMORROW: Planificar día
- IDEA: Guardar idea
- NOTE: Guardar nota
- UNKNOWN: No está claro

Responde solo con el nombre de la intención.""",

    "complexity_analysis": """Analiza la complejidad de esta tarea:

Tarea: {task_description}

Determina:
1. Complejidad: simple (< 30 min), medium (30-120 min), complex (> 2 horas)
2. Tiempo estimado en minutos
3. Subtareas sugeridas si es medium o complex
4. Posibles bloqueadores o dependencias""",
}


# ==================== FEW-SHOT EXAMPLES ====================

FEW_SHOT_EXAMPLES = {
    "intent_classification": [
        {
            "input": "Hola, buenos días",
            "output": "GREETING",
        },
        {
            "input": "Quiero comprarme unos airpods por $3000",
            "output": "EXPENSE_ANALYZE",
        },
        {
            "input": "Crear tarea: revisar el reporte de ventas",
            "output": "TASK_CREATE",
        },
        {
            "input": "¿Qué tengo pendiente para hoy?",
            "output": "TASK_QUERY",
        },
        {
            "input": "Fui al gym, hice pecho: banca 60kg 3x8",
            "output": "GYM_LOG",
        },
        {
            "input": "Recuérdame llamar al doctor en 2 horas",
            "output": "REMINDER_CREATE",
        },
        {
            "input": "¿Cuánto debo en total?",
            "output": "DEBT_QUERY",
        },
    ],
    "spending_analysis": [
        {
            "input": {
                "item": "Audífonos inalámbricos",
                "amount": 3000,
                "budget": 15000,
                "debt": 330000,
            },
            "output": {
                "necessity_score": 4,
                "budget_impact": "moderate",
                "recommendation": "wishlist",
                "honest_questions": [
                    "¿Tus audífonos actuales realmente están rotos?",
                    "¿Este dinero podría reducir tu deuda este mes?",
                    "¿Puedes esperar al Buen Fin o Black Friday?",
                ],
            },
        },
    ],
}


# ==================== UTILITY FUNCTIONS ====================

def get_system_prompt(agent_name: str) -> str:
    """Obtiene el system prompt para un agente específico."""
    return SYSTEM_PROMPTS.get(agent_name, SYSTEM_PROMPTS["base"])


def get_prompt_template(template_name: str) -> str:
    """Obtiene un template de prompt."""
    return PROMPT_TEMPLATES.get(template_name, "")


def format_prompt(template_name: str, **kwargs) -> str:
    """Formatea un template de prompt con los valores dados."""
    template = get_prompt_template(template_name)
    if not template:
        return ""
    return template.format(**kwargs)


def get_few_shot_examples(task_name: str) -> list[dict[str, Any]]:
    """Obtiene ejemplos few-shot para una tarea."""
    return FEW_SHOT_EXAMPLES.get(task_name, [])


@dataclass
class OptimizedPromptConfig:
    """Configuración optimizada para un prompt DSPy."""

    system_prompt: str
    temperature: float = 0.7
    max_tokens: int = 1024
    few_shot_examples: list[dict] | None = None

    @classmethod
    def for_agent(cls, agent_name: str) -> "OptimizedPromptConfig":
        """Crea configuración optimizada para un agente."""
        # Configuraciones específicas por agente
        configs = {
            "intent_router": cls(
                system_prompt=SYSTEM_PROMPTS["intent_router"],
                temperature=0.3,  # Más determinístico para clasificación
                max_tokens=256,  # Respuestas cortas
                few_shot_examples=FEW_SHOT_EXAMPLES.get("intent_classification"),
            ),
            "spending_analyzer": cls(
                system_prompt=SYSTEM_PROMPTS["spending_analyzer"],
                temperature=0.5,
                max_tokens=512,
                few_shot_examples=FEW_SHOT_EXAMPLES.get("spending_analysis"),
            ),
            "morning_planner": cls(
                system_prompt=SYSTEM_PROMPTS["morning_planner"],
                temperature=0.7,
                max_tokens=1024,
            ),
            "nutrition_analyzer": cls(
                system_prompt=SYSTEM_PROMPTS["nutrition_analyzer"],
                temperature=0.5,
                max_tokens=512,
            ),
            "workout_logger": cls(
                system_prompt=SYSTEM_PROMPTS["workout_logger"],
                temperature=0.4,
                max_tokens=512,
            ),
            "debt_strategist": cls(
                system_prompt=SYSTEM_PROMPTS["debt_strategist"],
                temperature=0.6,
                max_tokens=1024,
            ),
            "study_balancer": cls(
                system_prompt=SYSTEM_PROMPTS["study_balancer"],
                temperature=0.6,
                max_tokens=512,
            ),
            "task_planner": cls(
                system_prompt=SYSTEM_PROMPTS["task_planner"],
                temperature=0.6,
                max_tokens=1024,
            ),
        }

        return configs.get(
            agent_name,
            cls(system_prompt=SYSTEM_PROMPTS["base"]),
        )


# ==================== PROMPT OPTIMIZATION HINTS ====================

OPTIMIZATION_HINTS = """
Mejores prácticas para prompts DSPy:

1. **Instrucciones claras**: Sé específico sobre el formato de salida esperado.

2. **Contexto relevante**: Incluye solo la información necesaria para la tarea.

3. **Ejemplos few-shot**: Para tareas de clasificación, incluir 3-5 ejemplos
   mejora significativamente la precisión.

4. **Temperature**:
   - 0.0-0.3: Tareas determinísticas (clasificación, extracción)
   - 0.4-0.6: Balance entre creatividad y consistencia
   - 0.7-1.0: Tareas creativas (planificación, motivación)

5. **Max tokens**:
   - Clasificación simple: 128-256
   - Extracción de datos: 256-512
   - Generación de contenido: 512-1024
   - Análisis complejo: 1024-2048

6. **Especificidad del dominio**: Incluir vocabulario y contexto específico
   del dominio (ej: PPL para gym, avalanche/snowball para deudas).

7. **Formato de salida**: Especificar claramente si se espera JSON, lista
   separada por pipes, o texto libre.
"""
