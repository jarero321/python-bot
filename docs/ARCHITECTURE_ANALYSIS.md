# Análisis Arquitectónico - Carlos Command Bot

**Fecha:** 2024-11-29
**Versión:** 1.1
**Estado:** ✅ Fase 1 Completada

---

## Resumen Ejecutivo

El proyecto tiene una arquitectura funcional pero con **deuda técnica significativa**. Los problemas principales son:

1. **Monolitos críticos** - handlers.py (2,785 líneas) y orchestrator.py (1,086 líneas)
2. **Acoplamiento fuerte** - 13 archivos acceden directamente a NotionService
3. **Sin diferenciación de modelos LLM** - Todo usa Gemini Flash
4. **Sin RAG/embeddings** - No hay búsqueda semántica
5. **Código duplicado** - Parsing replicado en 10+ agentes

---

## 1. Estructura Actual

```
app/
├── agents/                    # 8,060 líneas totales
│   ├── __init__.py           # 220 líneas - 60+ exports
│   ├── base.py               # 354 líneas - DSPy setup + BaseAgent
│   ├── intent_router.py      # 506 líneas - 30+ intents
│   ├── orchestrator.py       # 1,086 líneas - MONOLITO
│   ├── conversational_orchestrator.py  # 821 líneas
│   ├── planning_assistant.py # 751 líneas
│   ├── task_planner.py       # 681 líneas
│   ├── morning_planner.py    # 359 líneas
│   ├── complexity_analyzer.py
│   ├── nutrition_analyzer.py # 353 líneas
│   ├── workout_logger.py     # 535 líneas
│   ├── spending_analyzer.py  # 293 líneas
│   ├── debt_strategist.py    # 456 líneas
│   ├── study_balancer.py     # 462 líneas
│   ├── jira_helper.py        # 335 líneas
│   ├── inbox_processor.py
│   └── conversation_context.py # 386 líneas
│
├── bot/
│   ├── handlers.py           # 2,785 líneas - MONOLITO CRÍTICO
│   ├── keyboards.py
│   └── conversations.py
│
├── services/
│   ├── notion.py             # 80+ métodos, 8 enums
│   ├── telegram.py
│   └── reminder_service.py
│
├── scheduler/
│   ├── setup.py
│   └── jobs/                 # 7 archivos
│
├── db/
│   ├── database.py
│   ├── models.py
│   └── repositories/
│
└── api/
    └── telegram_webhook.py
```

---

## 2. Problemas Identificados

### 2.1 CRÍTICO: Monolito handlers.py (2,785 líneas)

**Ubicación:** `app/bot/handlers.py`

**Síntomas:**
```python
async def route_by_intent(update, context, intent_result):
    if intent == UserIntent.GREETING:           # Línea 440
        ...
    if intent == UserIntent.HELP:               # Línea 445
        ...
    if intent == UserIntent.TASK_CREATE:        # Línea 454
        ...
    # ... 27 más if/elif
```

**Conteo:**
- 30 branches `if intent ==`
- 21 funciones async
- Mezcla de: routing, validación, formateo, lógica de negocio, acceso a BD

**Impacto:**
- Imposible de testear unitariamente
- Cambios frecuentes = alto riesgo de regresión
- Difícil de extender con nuevos intents

---

### 2.2 CRÍTICO: Monolito orchestrator.py (1,086 líneas)

**Ubicación:** `app/agents/orchestrator.py`

**Síntomas:**
```python
class AgentOrchestrator:
    def __init__(self):
        # Instancia TODOS los agentes
        self.intent_router = IntentRouterAgent()
        self.complexity_analyzer = ComplexityAnalyzerAgent()
        self.morning_planner = MorningPlannerAgent()
        self.nutrition_analyzer = NutritionAnalyzerAgent()
        self.workout_logger = WorkoutLoggerAgent()
        self.spending_analyzer = SpendingAnalyzerAgent()
        self.debt_strategist = DebtStrategistAgent()
        self.study_balancer = StudyBalancerAgent()
        self.jira_helper = JiraHelperAgent()
```

**Problemas:**
- Tight coupling con 9 agentes
- 10+ métodos `_enrich_*` con lógica similar
- Mapeos de enums duplicados

---

### 2.3 ALTO: Acoplamiento a NotionService

**Archivos que acceden directamente a Notion (13 total):**

| Archivo | Llamadas a get_notion_service() |
|---------|--------------------------------|
| orchestrator.py | 15+ |
| planning_assistant.py | 8+ |
| conversational_orchestrator.py | 5+ |
| handlers.py | 20+ |
| morning_briefing.py | 3+ |
| hourly_checkin.py | 2+ |
| proactive_tracker.py | 5+ |
| conversations.py | 4+ |
| ... | ... |

**Impacto:**
- Cambiar de Notion = modificar 13 archivos
- Testing requiere mock en múltiples lugares
- Sin abstracción de repositorio

---

### 2.4 ALTO: setup_dspy() Llamado 15 Veces

**Ubicación:** `app/agents/base.py:20-55`

```python
def setup_dspy() -> None:
    global _dspy_configured
    if _dspy_configured:
        return

    lm = dspy.LM(
        model="gemini/gemini-2.0-flash",  # HARDCODED
        api_key=settings.gemini_api_key,
        temperature=0.7,                   # HARDCODED
        max_tokens=1024,                   # HARDCODED
    )
    dspy.configure(lm=lm)
```

**Archivos que llaman setup_dspy():**
1. BaseAgent.__init__()
2. MorningPlannerAgent.__init__()
3. NutritionAnalyzerAgent.__init__()
4. ComplexityAnalyzerAgent.__init__()
5. DebtStrategistAgent.__init__()
6. StudyBalancerAgent.__init__()
7. WorkoutLoggerAgent.__init__()
8. JiraHelperAgent.__init__()
9. IntentRouterAgent.__init__()
10. ConversationalOrchestrator.__init__()
11. PlanningAssistant.__init__()
12. TaskPlannerAgent.__init__()
13. handlers.py (route_by_intent)
14. InboxProcessorAgent.__init__()
15. SpendingAnalyzerAgent.__init__()

**Problemas:**
- No hay diferenciación Flash vs Pro
- Parámetros hardcodeados
- Ineficiente (aunque protegido con flag)

---

### 2.5 ALTO: Código de Parsing Duplicado

**Método `_parse_list()` idéntico en:**
- morning_planner.py
- complexity_analyzer.py
- workout_logger.py
- nutrition_analyzer.py
- debt_strategist.py
- study_balancer.py

```python
# DUPLICADO EN 6+ ARCHIVOS
def _parse_list(self, items_str: str | list) -> list[str]:
    if isinstance(items_str, list):
        return [str(item) for item in items_str]
    if not items_str:
        return []
    return [s.strip() for s in str(items_str).split("|")]
```

**Mapeos de enum duplicados en:**
- orchestrator.py
- task_planner.py
- planning_assistant.py
- handlers.py

```python
# DUPLICADO EN 4+ ARCHIVOS
priority_map = {
    "urgente": TaskPrioridad.URGENTE,
    "alta": TaskPrioridad.ALTA,
    "normal": TaskPrioridad.NORMAL,
    "baja": TaskPrioridad.BAJA,
}
```

---

### 2.6 MEDIO: Inconsistencia en Herencia BaseAgent

| Agente | Hereda BaseAgent | Tiene execute() |
|--------|------------------|-----------------|
| InboxProcessorAgent | ✅ | ✅ |
| SpendingAnalyzerAgent | ✅ | ✅ |
| IntentRouterAgent | ✅ | ✅ |
| ComplexityAnalyzerAgent | ❌ | ❌ |
| MorningPlannerAgent | ❌ | ❌ |
| NutritionAnalyzerAgent | ❌ | ❌ |
| WorkoutLoggerAgent | ❌ | ❌ |
| DebtStrategistAgent | ❌ | ❌ |
| StudyBalancerAgent | ❌ | ❌ |
| JiraHelperAgent | ❌ | ❌ |
| TaskPlannerAgent | ❌ | ❌ |
| PlanningAssistant | ❌ | ❌ |

**Solo 3 de 12 agentes heredan de BaseAgent**

---

### 2.7 AUSENTE: RAG y Embeddings

**Estado actual:**
- Sin sistema de embeddings
- Sin búsqueda semántica
- Sin memoria de largo plazo
- Contexto limitado a últimos 5 mensajes

**Oportunidades perdidas:**
- Buscar tareas similares antes de crear
- Sugerir basado en historial
- Detectar duplicados
- Contexto enriquecido para LLM

---

### 2.8 AUSENTE: Multi-Model Strategy

**Estado actual:**
- Todo usa `gemini-2.0-flash`
- Sin diferenciación por complejidad

**Lo ideal:**
| Tarea | Modelo Recomendado |
|-------|-------------------|
| Intent classification | Flash (rápido) |
| Greeting response | Flash |
| Task complexity analysis | Flash |
| Morning planning | **Pro** (razonamiento) |
| Debt strategy | **Pro** (análisis) |
| Spending analysis | **Pro** (juicio) |
| Code generation (Jira) | **Pro** |

---

## 3. Métricas de Complejidad

| Archivo | Líneas | Funciones | Complejidad |
|---------|--------|-----------|-------------|
| handlers.py | 2,785 | 21 | 🔴 Muy Alta |
| orchestrator.py | 1,086 | 18 | 🔴 Alta |
| conversational_orchestrator.py | 821 | 12 | 🟠 Media-Alta |
| planning_assistant.py | 751 | 10 | 🟠 Media |
| task_planner.py | 681 | 8 | 🟠 Media |
| notion.py | ~800 | 80+ | 🟠 Media (pero bien organizado) |

---

## 4. Dependencias Circulares Potenciales

```
handlers.py
    └─> orchestrator.py
            └─> intent_router.py
            └─> task_planner.py
                    └─> notion.py
            └─> planning_assistant.py
                    └─> task_planner.py (circular!)
                    └─> notion.py
    └─> conversational_orchestrator.py
            └─> orchestrator.py (circular!)
            └─> intent_router.py
```

---

## 5. Plan de Refactorización

### Fase 1: CRÍTICO ✅ COMPLETADA

#### 1.1 Intent Handler Registry ✅
- ~~Eliminar 30 if/elif de handlers.py~~
- ✅ Creado `IntentHandlerRegistry` con patrón Strategy
- ✅ Cada intent en su propio handler
- **Archivos creados:**
  - `app/core/routing/registry.py` - Registry y BaseIntentHandler
  - `app/core/routing/dispatcher.py` - dispatch_intent()
  - `app/agents/handlers/` - 7 archivos de handlers por dominio:
    - `general_handlers.py` - Greeting, Help, Status
    - `task_handlers.py` - Task CRUD
    - `planning_handlers.py` - Planificación y recordatorios
    - `finance_handlers.py` - Gastos y deudas
    - `fitness_handlers.py` - Gym y nutrición
    - `project_handlers.py` - Proyectos y estudio
    - `capture_handlers.py` - Ideas, notas, fallback

#### 1.2 LLM Provider Multi-Model ✅
- ✅ Centralizada configuración de LLM
- ✅ Soporte para Flash y Pro
- ✅ Selección automática por complejidad de tarea
- **Archivos creados:**
  - `app/core/llm/provider.py` - LLMProvider con ModelType
  - Context manager `use_model()` y `for_task()`
  - TASK_MODEL_MAP para selección automática

#### 1.3 Parsing Utilities ✅
- ✅ Creado `app/core/parsing/dspy_parser.py`
- ✅ Centralizado `parse_list`, `parse_enum`, `parse_json`
- ✅ Añadidos `parse_date`, `parse_int`, `parse_float`, `parse_bool`
- ✅ Método `clean_llm_output` para sanitizar respuestas

### Fase 2: ALTO (Semana 2)

#### 2.1 Repository Pattern
- Crear `ITaskRepository`, `IProjectRepository`
- Implementar `NotionTaskRepository`
- Desacoplar agentes de NotionService

#### 2.2 RAG con Embeddings
- Implementar embedding de tareas
- Búsqueda semántica para contexto
- Detección de duplicados

### Fase 3: Consolidación (Semana 3)

#### 3.1 Estandarizar Agentes
- Todos heredan BaseAgent
- Método `execute()` consistente
- Métricas automáticas

#### 3.2 Dependency Injection
- Container de DI
- Testing simplificado
- Configuración por ambiente

---

## 6. Arquitectura Propuesta

```
app/
├── core/                              # NUEVO
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── provider.py               # Multi-model provider
│   │   └── models.py                 # Model configs
│   ├── routing/
│   │   ├── __init__.py
│   │   ├── registry.py               # Handler registry
│   │   └── dispatcher.py             # Intent dispatcher
│   └── parsing/
│       ├── __init__.py
│       └── dspy_parser.py            # Centralized parsing
│
├── domain/                            # NUEVO
│   ├── entities/
│   │   ├── task.py
│   │   ├── project.py
│   │   └── reminder.py
│   └── repositories/
│       ├── base.py                   # Interface
│       └── notion_repositories.py    # Implementation
│
├── agents/
│   ├── base.py                       # Mejorado
│   ├── handlers/                     # NUEVO - Intent handlers
│   │   ├── __init__.py
│   │   ├── base.py                   # BaseIntentHandler
│   │   ├── task_handlers.py
│   │   ├── project_handlers.py
│   │   ├── planning_handlers.py
│   │   ├── finance_handlers.py
│   │   ├── fitness_handlers.py
│   │   └── general_handlers.py
│   └── [agentes existentes refactorizados]
│
├── bot/
│   ├── handlers.py                   # Reducido a ~300 líneas
│   └── ...
│
└── [resto igual]
```

---

## 7. Beneficios Esperados

| Métrica | Actual | Post-Refactor |
|---------|--------|---------------|
| handlers.py líneas | 2,785 | ~300 |
| Archivos que acceden Notion | 13 | 3 |
| setup_dspy() calls | 15 | 1 |
| Código duplicado parsing | 60+ líneas x 6 | 0 |
| Cobertura de tests posible | ~10% | ~70% |
| Tiempo agregar nuevo intent | ~30 min | ~5 min |

---

## 8. Riesgos de No Refactorizar

1. **Deuda técnica creciente** - Cada feature nueva aumenta complejidad
2. **Bugs difíciles de trackear** - handlers.py es caja negra
3. **Onboarding lento** - Nuevo desarrollador necesita semanas
4. **Testing imposible** - Sin tests = sin confianza en cambios
5. **Escalabilidad limitada** - No se puede agregar RAG/embeddings fácilmente

---

## Anexo: Comandos Útiles para Análisis

```bash
# Contar líneas por archivo
find app -name "*.py" -exec wc -l {} + | sort -n

# Buscar if intent ==
grep -rn "if intent ==" app/bot/handlers.py | wc -l

# Buscar setup_dspy calls
grep -rn "setup_dspy()" app/ | wc -l

# Buscar get_notion_service calls
grep -rn "get_notion_service()" app/ | wc -l

# Buscar _parse_list duplicados
grep -rn "def _parse_list" app/
```

---

*Documento generado como parte del proceso de refactorización de Carlos Command Bot.*

---

## 9. Fase 1 - Detalle de Implementación

### Estructura Creada

```
app/core/                              # ✅ NUEVO
├── __init__.py                        # initialize_core()
├── llm/
│   ├── __init__.py
│   └── provider.py                    # LLMProvider, ModelType, TASK_MODEL_MAP
├── routing/
│   ├── __init__.py
│   ├── registry.py                    # IntentHandlerRegistry, BaseIntentHandler
│   └── dispatcher.py                  # dispatch_intent(), handle_message_with_registry()
└── parsing/
    ├── __init__.py
    └── dspy_parser.py                 # DSPyParser con 15+ métodos

app/agents/handlers/                   # ✅ NUEVO
├── __init__.py                        # register_all_handlers()
├── general_handlers.py                # 3 handlers
├── task_handlers.py                   # 4 handlers
├── planning_handlers.py               # 7 handlers
├── finance_handlers.py                # 3 handlers
├── fitness_handlers.py                # 4 handlers
├── project_handlers.py                # 5 handlers
└── capture_handlers.py                # 3 handlers + FallbackHandler
```

### Uso del Nuevo Sistema

```python
# Inicialización (en main.py lifespan)
from app.core import initialize_core
initialize_core()  # Configura LLM + registra handlers

# En handler de mensajes (opción nueva)
from app.core.routing import handle_message_with_registry
await handle_message_with_registry(update, context)

# Uso de modelo Pro para tareas complejas
from app.core.llm import get_llm_provider, ModelType

provider = get_llm_provider()
with provider.for_task("morning_planning"):  # Usa PRO
    result = planning_module(tasks)

# Parsing centralizado
from app.core.parsing import DSPyParser

items = DSPyParser.parse_list(result.subtasks)
priority = DSPyParser.parse_enum(result.priority, TaskPrioridad)
date = DSPyParser.parse_date("mañana")  # -> "2024-11-30"
```

### Handlers Registrados (26 total)

| Dominio | Handler | Intent |
|---------|---------|--------|
| General | GreetingHandler | GREETING |
| General | HelpHandler | HELP |
| General | StatusHandler | STATUS |
| Tasks | TaskCreateHandler | TASK_CREATE |
| Tasks | TaskQueryHandler | TASK_QUERY |
| Tasks | TaskUpdateHandler | TASK_UPDATE |
| Tasks | TaskDeleteHandler | TASK_DELETE |
| Planning | PlanTomorrowHandler | PLAN_TOMORROW |
| Planning | PlanWeekHandler | PLAN_WEEK |
| Planning | WorkloadCheckHandler | WORKLOAD_CHECK |
| Planning | PrioritizeHandler | PRIORITIZE |
| Planning | RescheduleHandler | RESCHEDULE |
| Planning | ReminderCreateHandler | REMINDER_CREATE |
| Planning | ReminderQueryHandler | REMINDER_QUERY |
| Finance | ExpenseAnalyzeHandler | EXPENSE_ANALYZE |
| Finance | ExpenseLogHandler | EXPENSE_LOG |
| Finance | DebtQueryHandler | DEBT_QUERY |
| Fitness | GymLogHandler | GYM_LOG |
| Fitness | GymQueryHandler | GYM_QUERY |
| Fitness | NutritionLogHandler | NUTRITION_LOG |
| Fitness | NutritionQueryHandler | NUTRITION_QUERY |
| Projects | ProjectCreateHandler | PROJECT_CREATE |
| Projects | ProjectQueryHandler | PROJECT_QUERY |
| Projects | ProjectUpdateHandler | PROJECT_UPDATE |
| Projects | ProjectDeleteHandler | PROJECT_DELETE |
| Projects | StudySessionHandler | STUDY_SESSION |
| Capture | IdeaHandler | IDEA |
| Capture | NoteHandler | NOTE |
| Capture | UnknownHandler | UNKNOWN |

### Próximos Pasos (Fase 2)

1. **Migrar handlers.py a usar dispatch_intent()** - Reemplazar route_by_intent()
2. **Repository Pattern** - Desacoplar de NotionService
3. **RAG con Embeddings** - Búsqueda semántica para contexto
4. **Eliminar código duplicado** - Usar DSPyParser en todos los agentes
