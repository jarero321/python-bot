# 🎮 Carlos Command - Sistema de Vida Integral

## Documentación Técnica v1.0

**Autor:** Carlos + Claude  
**Fecha:** Noviembre 2025  
**Propósito:** Sistema personal de productividad, salud y finanzas con AI Agents

---

## 📋 Tabla de Contenidos

1. [Visión General](#1-visión-general)
2. [Arquitectura del Sistema](#2-arquitectura-del-sistema)
3. [Bases de Datos Notion](#3-bases-de-datos-notion)
4. [AI Agents (DSPy)](#4-ai-agents-dspy)
5. [Flujos de Telegram](#5-flujos-de-telegram)
6. [API Endpoints (FastAPI)](#6-api-endpoints-fastapi)
7. [Configuración de N8N](#7-configuración-de-n8n)
8. [Datos del Usuario](#8-datos-del-usuario)
9. [Plan de Implementación](#9-plan-de-implementación)
10. [Anexos](#10-anexos)

---

## 1. Visión General

### 1.1 ¿Qué es Carlos Command?

Un sistema integral que funciona como **Project Manager personal** a través de Telegram, conectado a Notion como base de datos y potenciado por AI Agents para:

- Gestión de tareas y proyectos con time blocking
- Tracking de salud (gym PPL, nutrición, peso)
- Control financiero (deudas, ingresos, gastos)
- Aprendizaje con rotación balanceada
- Recordatorios persistentes e inteligentes

### 1.2 Filosofía del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                    PRINCIPIOS CORE                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. El bot te BUSCA, no tú a él                            │
│  2. Pregunta cuando no entiende, no inventa                │
│  3. Insiste hasta que respondas o reprogrames              │
│  4. Sin juicio, pero con honestidad brutal                 │
│  5. Cada decisión se muestra con su impacto real           │
│  6. Protege tu tiempo de deep work                         │
│  7. Celebra victorias, confronta excusas                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 Stack Tecnológico

| Componente | Tecnología | Propósito |
|------------|------------|-----------|
| Frontend/UI | Telegram Bot | Interfaz conversacional |
| Orquestador | N8N (self-hosted) | Cron jobs, webhooks, flujos |
| Backend | FastAPI (Python) | Lógica de negocio, endpoints |
| AI Framework | DSPy + Gemini | Agentes inteligentes |
| Base de Datos | Notion API | Almacenamiento estructurado |
| Cache/State | SQLite/Redis | Sesiones, métricas DSPy |
| Hosting | VPS propio (Docker) | Todo el sistema |

### 1.4 Costos Estimados

| Servicio | Costo Mensual |
|----------|---------------|
| VPS (existente) | $0 |
| Gemini API | $5-15 USD |
| Notion | Gratis |
| Telegram | Gratis |
| **Total** | **~$5-15 USD/mes** |

---

## 2. Arquitectura del Sistema

### 2.1 Diagrama General

```
┌─────────────────────────────────────────────────────────────────┐
│                           VPS                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────┐         ┌─────────────────────────────────┐  │
│   │  TELEGRAM   │◄───────►│            N8N                  │  │
│   │    BOT      │         │   ┌─────────────────────────┐   │  │
│   └─────────────┘         │   │ Workflows:              │   │  │
│                           │   │ • Morning Briefing      │   │  │
│                           │   │ • Hourly Check-ins      │   │  │
│                           │   │ • Pre-Payday Alert      │   │  │
│                           │   │ • Weekly Review         │   │  │
│                           │   │ • Gym Reminder          │   │  │
│                           │   └─────────────────────────┘   │  │
│                           └──────────────┬──────────────────┘  │
│                                          │                      │
│                                          ▼                      │
│                           ┌─────────────────────────────────┐  │
│                           │          FASTAPI                │  │
│                           │  ┌───────────────────────────┐  │  │
│                           │  │ Endpoints:                │  │  │
│                           │  │ • POST /inbox             │  │  │
│                           │  │ • POST /task/status       │  │  │
│                           │  │ • GET  /morning-plan      │  │  │
│                           │  │ • POST /meal/log          │  │  │
│                           │  │ • POST /workout/log       │  │  │
│                           │  │ • GET  /finance/summary   │  │  │
│                           │  │ • POST /purchase/analyze  │  │  │
│                           │  └───────────────────────────┘  │  │
│                           │              │                  │  │
│                           │              ▼                  │  │
│                           │  ┌───────────────────────────┐  │  │
│                           │  │     DSPy Agents           │  │  │
│                           │  │ • InboxProcessor          │  │  │
│                           │  │ • ComplexityAnalyzer      │  │  │
│                           │  │ • TimeBlockGuardian       │  │  │
│                           │  │ • NutritionAnalyzer       │  │  │
│                           │  │ • WorkoutLogger           │  │  │
│                           │  │ • SpendingAnalyzer        │  │  │
│                           │  │ • (+ 6 más)               │  │  │
│                           │  └───────────────────────────┘  │  │
│                           │              │                  │  │
│                           │              ▼                  │  │
│                           │  ┌───────────────────────────┐  │  │
│                           │  │      Gemini API           │  │  │
│                           │  │   ($300 crédito)          │  │  │
│                           │  └───────────────────────────┘  │  │
│                           └──────────────┬──────────────────┘  │
│                                          │                      │
│                                          ▼                      │
│                           ┌─────────────────────────────────┐  │
│                           │        NOTION API               │  │
│                           │   (8 Databases)                 │  │
│                           └─────────────────────────────────┘  │
│                                                                 │
│   ┌─────────────┐                                              │
│   │   SQLite    │  ← Historial conversaciones + Métricas DSPy  │
│   └─────────────┘                                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Flujo de Datos

```
Usuario (Telegram)
       │
       ▼
   N8N Webhook ───────────────────┐
       │                          │
       ▼                          ▼
   FastAPI                   Cron Jobs
       │                     (Scheduled)
       ▼                          │
   DSPy Agent ◄───────────────────┘
       │
       ├──► Gemini (LLM)
       │
       ▼
   Notion API
       │
       ▼
   Response ──► N8N ──► Telegram
```

---

## 3. Bases de Datos Notion

### 3.1 Overview

| # | Database | Propósito | Relaciones |
|---|----------|-----------|------------|
| 1 | 📥 Inbox | Captura rápida | → Tasks, Knowledge |
| 2 | ✅ Tasks | Gestión de tareas | → Projects, Inbox |
| 3 | 📁 Projects | Proyectos y metas | → Tasks, Finance |
| 4 | 📚 Knowledge | Base de conocimiento | → Tasks, Projects |
| 5 | 🍽️ Daily Nutrition | Comidas diarias | - |
| 6 | 🏋️ Workouts | Sesiones de gym | → Exercises |
| 7 | 💰 Transactions | Movimientos de dinero | → Projects |
| 8 | 💳 Debts | Deudas activas | → Transactions |

### 3.2 📥 Inbox Database

**Propósito:** Captura rápida de cualquier cosa que llegue

| Campo | Tipo | Descripción | Requerido |
|-------|------|-------------|-----------|
| `Contenido` | Title | Lo que capturaste | ✅ |
| `Fuente` | Select | Telegram, Manual, Voz | ✅ |
| `Fecha` | Date | Timestamp automático | ✅ |
| `Procesado` | Checkbox | ¿Ya clasificado? | ✅ |
| `Confianza AI` | Number | 0-100% del clasificador | - |
| `Proyecto Sugerido` | Relation | Sugerencia del AI | - |
| `Notas` | Text | Contexto adicional | - |

**Vistas:**
- `Sin Procesar` - Filter: Procesado = false
- `Hoy` - Filter: Fecha = Today
- `Por Proyecto` - Group by: Proyecto Sugerido

### 3.3 ✅ Tasks Database

**Propósito:** Todas las tareas unificadas (trabajo, freelance, personal)

| Campo | Tipo | Opciones/Descripción | Requerido |
|-------|------|---------------------|-----------|
| `Tarea` | Title | Nombre de la tarea | ✅ |
| `Proyecto` | Relation | → Projects | - |
| `Contexto` | Select | PayCash, Freelance-PA, Freelance-Google, Personal, Workana, Estudio | ✅ |
| `Estado` | Select | 📥 Backlog, 📋 Planned, 🎯 Today, ⚡ Doing, ⏸️ Paused, ✅ Done, ❌ Cancelled | ✅ |
| `Prioridad` | Select | 🔥 Urgente, ⚡ Alta, 🔄 Normal, 🧊 Baja | - |
| `Complejidad` | Select | 🟢 Quick (<30m), 🟡 Standard (30m-2h), 🔴 Heavy (2-4h), ⚫ Epic (4h+) | - |
| `Energía` | Select | 🧠 Deep Work, 💪 Medium, 😴 Low | - |
| `Tiempo Est.` | Select | 15m, 30m, 1h, 2h, 4h, 8h | - |
| `Tiempo Real` | Number | Minutos reales | - |
| `Bloque` | Select | 🌅 Morning, ☀️ Afternoon, 🌆 Evening | - |
| `Daily Slot` | Select | Morning-1, Morning-2, Noon-1, Evening-1, etc. | - |
| `Fecha Do` | Date | Cuándo hacerla | - |
| `Fecha Due` | Date | Deadline | - |
| `Fecha Done` | Date | Cuándo se completó | - |
| `En Jira` | Checkbox | ¿Documentada en Jira? | - |
| `Bloqueada` | Checkbox | ¿Tiene blocker? | - |
| `Blocker` | Text | Descripción del blocker | - |
| `Recordatorio` | Date | Fecha/hora de reminder | - |
| `From Inbox` | Relation | → Inbox | - |
| `Subtareas` | Relation | → Tasks (self) | - |
| `Notas` | Text | Contexto adicional | - |

**Vistas:**
- `Hoy` - Filter: Estado = Today OR Doing, Sort: Prioridad
- `Esta Semana` - Filter: Fecha Do = This Week
- `Por Proyecto` - Group by: Proyecto
- `Backlog` - Filter: Estado = Backlog
- `Deep Work` - Filter: Energía = Deep Work, Estado != Done
- `Quick Wins` - Filter: Complejidad = Quick, Estado != Done

### 3.4 📁 Projects Database

**Propósito:** Todos los proyectos (trabajo, freelance, aprendizaje, personal, financieros)

| Campo | Tipo | Opciones/Descripción | Requerido |
|-------|------|---------------------|-----------|
| `Proyecto` | Title | Nombre | ✅ |
| `Tipo` | Select | 💼 Trabajo, 💰 Freelance, 📚 Aprendizaje, 🚀 Side Project, 🏠 Personal, 🎯 Hobby, 💳 Financiero, 🔍 Búsqueda | ✅ |
| `Estado` | Select | 💡 Idea, 📝 Planning, 🟢 Activo, 🟡 Esperando, ⏸️ Pausado, ✅ Completado, ❌ Cancelado | ✅ |
| `Objetivo` | Text | Meta final del proyecto | - |
| `Hito Actual` | Text | Milestone en progreso | - |
| `Progreso Hito` | Number | % del hito (0-100) | - |
| `Genera Dinero` | Checkbox | ¿Produce ingresos? | - |
| `Ingreso Potencial` | Number | $ estimado | - |
| `Genera Bienestar` | Multi-select | Relajación, Mental, Social, Creativo, Físico | - |
| `Costo` | Number | $ si tiene costo | - |
| `Cliente` | Text | Nombre del cliente | - |
| `Deadline` | Date | Fecha límite | - |
| `Última Actividad` | Date | Auto-update | - |
| `Días Sin Actividad` | Formula | `dateBetween(now(), prop("Última Actividad"), "days")` | - |
| `En Rotación Estudio` | Checkbox | Si es de aprendizaje | - |
| `Prioridad Financiera` | Number | 1-10 para metas de dinero | - |
| `Tasks` | Relation | → Tasks | - |
| `Transactions` | Relation | → Transactions | - |
| `Notas` | Text | Contexto | - |

**Vistas:**
- `Activos` - Filter: Estado = Activo
- `Por Tipo` - Group by: Tipo
- `Necesitan Atención` - Filter: Días Sin Actividad > 5, Estado = Activo
- `Financieros` - Filter: Tipo = Financiero
- `Estudio (Rotación)` - Filter: En Rotación Estudio = true

### 3.5 📚 Knowledge Database

**Propósito:** Base de conocimiento personal

| Campo | Tipo | Opciones/Descripción | Requerido |
|-------|------|---------------------|-----------|
| `Título` | Title | Nombre del conocimiento | ✅ |
| `Contenido` | Text | El conocimiento en sí | ✅ |
| `Tipo` | Select | 📝 Nota, 💡 Idea, 📰 Artículo, 🎥 Video, 📚 Libro, 💻 Código, 🔧 Solución | - |
| `Topic` | Multi-select | JavaScript, Python, NetSuite, AI/ML, Business, Edición Video, Finanzas | - |
| `Fuente` | Select | Personal, Web, Curso, Libro, Conversación, Estudio | - |
| `Valor` | Select | ⭐⭐⭐⭐⭐, ⭐⭐⭐⭐, ⭐⭐⭐, ⭐⭐, ⭐ | - |
| `Proyecto` | Relation | → Projects | - |
| `Task` | Relation | → Tasks | - |
| `Evergreen` | Checkbox | ¿Conocimiento atemporal? | - |
| `Fecha` | Date | Cuándo se capturó | ✅ |

### 3.6 🍽️ Daily Nutrition Database

**Propósito:** Tracking de comidas (registro al final del día)

| Campo | Tipo | Opciones/Descripción | Requerido |
|-------|------|---------------------|-----------|
| `Fecha` | Title | Día (YYYY-MM-DD) | ✅ |
| `Desayuno` | Text | Descripción | - |
| `Desayuno Cal` | Number | Calorías estimadas | - |
| `Desayuno Cat` | Select | 🟢 Saludable, 🟡 Moderado, 🔴 Pesado | - |
| `Comida` | Text | Descripción | - |
| `Comida Cal` | Number | Calorías estimadas | - |
| `Comida Cat` | Select | 🟢 Saludable, 🟡 Moderado, 🔴 Pesado | - |
| `Cena` | Text | Descripción | - |
| `Cena Cal` | Number | Calorías estimadas | - |
| `Cena Cat` | Select | 🟢 Saludable, 🟡 Moderado, 🔴 Pesado | - |
| `Snacks` | Text | Descripción | - |
| `Snacks Cal` | Number | Calorías estimadas | - |
| `Total Cal` | Formula | Suma de calorías | - |
| `Proteína OK` | Checkbox | ¿Suficiente proteína? | - |
| `Vegetales OK` | Checkbox | ¿Comió vegetales? | - |
| `Evaluación` | Select | 🟢 Buen día, 🟡 Regular, 🔴 Mejorable | - |
| `Notas` | Text | Observaciones | - |

### 3.7 🏋️ Workouts Database

**Propósito:** Sesiones de gym con tracking de progreso PPL

| Campo | Tipo | Opciones/Descripción | Requerido |
|-------|------|---------------------|-----------|
| `Fecha` | Title | Día (YYYY-MM-DD) | ✅ |
| `Tipo` | Select | Push, Pull, Legs, Cardio, Rest | ✅ |
| `Completado` | Checkbox | ¿Fuiste? | ✅ |
| `Ejercicios` | Text | JSON con ejercicios (ver estructura abajo) | - |
| `Sensación` | Select | 💪 Fuerte, 😅 Normal, 😓 Pesado, 🤕 Molestia | - |
| `PRs` | Text | Récords personales del día | - |
| `Peso Corporal` | Number | Kg (solo domingos) | - |
| `Notas` | Text | Observaciones, molestias | - |

**Estructura JSON de Ejercicios:**
```json
{
  "exercises": [
    {
      "name": "Press Banca",
      "sets": [
        {"weight": 62.5, "reps": 8},
        {"weight": 62.5, "reps": 8},
        {"weight": 62.5, "reps": 7}
      ],
      "pr": false
    },
    {
      "name": "Press Militar",
      "sets": [
        {"weight": 35, "reps": 12},
        {"weight": 35, "reps": 10}
      ],
      "pr": true
    }
  ]
}
```

**Vistas:**
- `Esta Semana` - Filter: Fecha = This Week
- `Por Tipo` - Group by: Tipo
- `PRs` - Filter: PRs is not empty
- `Peso Corporal` - Filter: Peso Corporal is not empty, Sort: Fecha desc

### 3.8 💰 Transactions Database

**Propósito:** Todos los movimientos de dinero

| Campo | Tipo | Opciones/Descripción | Requerido |
|-------|------|---------------------|-----------|
| `Concepto` | Title | Descripción | ✅ |
| `Monto` | Number | Cantidad (+ ingreso, - gasto) | ✅ |
| `Tipo` | Select | 💵 Ingreso, 🏠 Gasto Fijo, 🛒 Gasto Variable, 💳 Pago Deuda, 💰 Ahorro | ✅ |
| `Categoría` | Select | Salario, Freelance, Renta, Servicios, Comida, Tech, Entretenimiento, Transporte, Deuda, Otro | ✅ |
| `Fecha` | Date | Cuándo ocurrió | ✅ |
| `Es Esencial` | Checkbox | ¿Necesario o gusto? | - |
| `Proyecto` | Relation | → Projects (si es freelance) | - |
| `Deuda` | Relation | → Debts (si es pago de deuda) | - |
| `Quincena` | Select | Q1-Enero, Q2-Enero, Q1-Febrero... | - |
| `Impulsivo` | Checkbox | ¿Compra impulsiva? | - |
| `Notas` | Text | Contexto | - |

**Vistas:**
- `Este Mes` - Filter: Fecha = This Month
- `Por Categoría` - Group by: Categoría
- `Ingresos` - Filter: Tipo = Ingreso
- `Gastos Variables` - Filter: Tipo = Gasto Variable
- `Pagos Deuda` - Filter: Tipo = Pago Deuda
- `Compras Impulsivas` - Filter: Impulsivo = true

### 3.9 💳 Debts Database

**Propósito:** Tracking de deudas activas

| Campo | Tipo | Opciones/Descripción | Requerido |
|-------|------|---------------------|-----------|
| `Deuda` | Title | Nombre/descripción | ✅ |
| `Acreedor` | Select | Banco, Tienda, Persona, Otro | ✅ |
| `Monto Original` | Number | Cuánto era inicialmente | ✅ |
| `Monto Actual` | Number | Cuánto queda | ✅ |
| `Tasa Interés` | Number | % anual | - |
| `Interés Mensual` | Formula | `prop("Monto Actual") * prop("Tasa Interés") / 100 / 12` | - |
| `Pago Mínimo` | Number | Mensual requerido | ✅ |
| `Prioridad` | Number | 1 = más urgente (por tasa) | - |
| `Fecha Inicio` | Date | Cuándo empezó | - |
| `Fecha Límite` | Date | Si tiene | - |
| `Pagos` | Relation | → Transactions | - |
| `Progreso` | Formula | `(prop("Monto Original") - prop("Monto Actual")) / prop("Monto Original") * 100` | - |
| `Estado` | Select | 🔴 Activa, 🟡 Negociando, ✅ Liquidada | ✅ |
| `Notas` | Text | Historia, contexto | - |

**Datos Iniciales de Carlos:**

| Deuda | Monto | Tasa | Pago Min | Prioridad |
|-------|-------|------|----------|-----------|
| Tarjeta Banco | $80,000 | 60% | $4,000 | 1 |
| Coppel | $30,000 | 50% | $1,800 | 2 |
| Mercado Libre | $20,000 | 40% | $1,500 | 3 |
| Carro | $200,000 | 15% | $12,000 | 4 (fijo) |

---

## 4. AI Agents (DSPy)

### 4.1 Overview de Agentes

| # | Agente | Trigger | Propósito |
|---|--------|---------|-----------|
| 1 | InboxProcessor | Mensaje en Telegram | Clasificar captura rápida |
| 2 | ComplexityAnalyzer | Tarea técnica detectada | Estimar tiempo y dividir |
| 3 | TimeBlockGuardian | Durante deep work | Proteger foco, detectar distracción |
| 4 | MorningPlanner | 6:30 AM diario | Crear plan del día |
| 5 | CheckInAgent | Cada hora / fin de bloque | Preguntar status |
| 6 | JiraIntegrator | Tarea completada | Ayudar a documentar |
| 7 | PersistentReminder | Recordatorios pendientes | Insistir hasta resolver |
| 8 | NutritionAnalyzer | 21:00 diario | Analizar comidas del día |
| 9 | WorkoutLogger | Post-gym | Registrar ejercicios |
| 10 | ProgressAnalyzer | Domingo | Analizar progreso semanal |
| 11 | SpendingAnalyzer | Mención de compra | Analizar impacto financiero |
| 12 | PaydayPlanner | Pre-quincena | Crear plan de distribución |
| 13 | DebtStrategist | Mensual | Optimizar pagos de deuda |
| 14 | StudyBalancer | 17:30 diario | Sugerir tema de estudio |
| 15 | ProjectManager | Crear/consultar proyecto | Gestión de proyectos |

### 4.2 Signatures DSPy

#### 4.2.1 InboxProcessor

```python
import dspy

class InboxProcessor(dspy.Signature):
    """
    Clasifica un mensaje rápido del usuario en una tarea estructurada.
    Si no tiene suficiente contexto, genera pregunta de clarificación.
    """
    
    # Inputs
    raw_input: str = dspy.InputField(
        desc="Mensaje del usuario tal como lo escribió"
    )
    active_projects: list = dspy.InputField(
        desc="Lista de proyectos activos con su tipo y contexto"
    )
    recent_tasks: list = dspy.InputField(
        desc="Últimas 5 tareas para detectar continuidad"
    )
    current_context: str = dspy.InputField(
        desc="Qué está haciendo ahora (deep work, break, etc)"
    )
    
    # Outputs
    confidence: float = dspy.OutputField(
        desc="0.0-1.0 qué tan seguro está de la clasificación"
    )
    task_title: str = dspy.OutputField(
        desc="Título claro y accionable de la tarea"
    )
    suggested_project: str = dspy.OutputField(
        desc="Proyecto sugerido o 'Unknown'"
    )
    suggested_context: str = dspy.OutputField(
        desc="PayCash/Freelance-PA/Freelance-Google/Personal/Workana/Estudio"
    )
    suggested_complexity: str = dspy.OutputField(
        desc="quick/standard/heavy/epic"
    )
    is_subtask: bool = dspy.OutputField(
        desc="¿Es subtarea de algo que está haciendo?"
    )
    needs_clarification: bool = dspy.OutputField(
        desc="¿Necesita preguntar algo para clasificar?"
    )
    clarification_question: str = dspy.OutputField(
        desc="Pregunta específica si needs_clarification=True"
    )
```

#### 4.2.2 ComplexityAnalyzer

```python
class ComplexityAnalyzer(dspy.Signature):
    """
    Analiza complejidad técnica de una tarea y sugiere división.
    """
    
    task_description: str = dspy.InputField()
    user_tech_stack: str = dspy.InputField(
        desc="Stack: Python, JavaScript, NetSuite, Power Automate"
    )
    similar_tasks_history: list = dspy.InputField(
        desc="Tareas similares con tiempo real que tomaron"
    )
    
    complexity: str = dspy.OutputField(
        desc="quick/standard/heavy/epic"
    )
    estimated_minutes: int = dspy.OutputField()
    energy_required: str = dspy.OutputField(
        desc="deep_work/medium/low"
    )
    should_divide: bool = dspy.OutputField(
        desc="¿Debería dividirse en subtareas?"
    )
    suggested_subtasks: list = dspy.OutputField(
        desc="Lista de subtareas si should_divide=True"
    )
    potential_blockers: list = dspy.OutputField(
        desc="Posibles bloqueantes técnicos"
    )
    requires_research: bool = dspy.OutputField()
    research_topics: list = dspy.OutputField(
        desc="Qué investigar si requires_research=True"
    )
```

#### 4.2.3 TimeBlockGuardian

```python
class TimeBlockGuardian(dspy.Signature):
    """
    Protege los bloques de tiempo del usuario.
    Detecta distracciones y sugiere cómo manejarlas.
    """
    
    current_block: str = dspy.InputField(
        desc="deep_work/shallow/break/personal/study"
    )
    block_end_time: str = dspy.InputField(
        desc="HH:MM cuando termina el bloque"
    )
    current_task: str = dspy.InputField(
        desc="Tarea asignada al bloque"
    )
    user_message: str = dspy.InputField(
        desc="Lo que el usuario acaba de decir/pedir"
    )
    
    is_distraction: bool = dspy.OutputField()
    distraction_type: str = dspy.OutputField(
        desc="procrastination/valid_interruption/task_switch/emergency"
    )
    allow_interruption: bool = dspy.OutputField()
    response_tone: str = dspy.OutputField(
        desc="gentle/firm/understanding"
    )
    response_message: str = dspy.OutputField(
        desc="Mensaje para el usuario"
    )
    reschedule_suggestion: str = dspy.OutputField(
        desc="Cuándo hacer lo que pidió si no es ahora"
    )
```

#### 4.2.4 MorningPlanner

```python
class MorningPlanner(dspy.Signature):
    """
    Crea el plan del día basado en tareas, calendario y energía.
    """
    
    pending_tasks: list = dspy.InputField(
        desc="Tareas en backlog/planned/today"
    )
    calendar_events: list = dspy.InputField(
        desc="Reuniones y eventos del día"
    )
    yesterday_incomplete: list = dspy.InputField(
        desc="Tareas que no se completaron ayer"
    )
    blockers_pending: list = dspy.InputField(
        desc="Recordatorios de blockers"
    )
    habits_status: dict = dspy.InputField(
        desc="Estado de hábitos (gym, etc)"
    )
    day_of_week: str = dspy.InputField()
    
    greeting: str = dspy.OutputField()
    top_3_tasks: list = dspy.OutputField(
        desc="Las 3 MITs del día con bloque asignado"
    )
    time_blocks: dict = dspy.OutputField(
        desc="Distribución de bloques del día"
    )
    reminders: list = dspy.OutputField(
        desc="Recordatorios importantes"
    )
    habit_prompts: list = dspy.OutputField(
        desc="Preguntas sobre hábitos (gym, etc)"
    )
    motivation: str = dspy.OutputField(
        desc="Mensaje motivacional contextual"
    )
```

#### 4.2.5 NutritionAnalyzer

```python
class NutritionAnalyzer(dspy.Signature):
    """
    Analiza las comidas del día y da feedback nutricional.
    """
    
    meals_description: str = dspy.InputField(
        desc="Descripción de todo lo que comió en el día"
    )
    user_goals: str = dspy.InputField(
        desc="perder_peso/mantener/ganar_musculo"
    )
    activity_today: str = dspy.InputField(
        desc="gym_day/rest_day/active"
    )
    recent_nutrition_history: list = dspy.InputField(
        desc="Últimos 7 días de nutrición"
    )
    
    meals_breakdown: list = dspy.OutputField(
        desc="Cada comida desglosada con calorías"
    )
    total_calories: int = dspy.OutputField()
    protein_status: str = dspy.OutputField(
        desc="sufficient/low/high"
    )
    vegetables_count: int = dspy.OutputField(
        desc="Número de comidas con vegetales"
    )
    overall_rating: str = dspy.OutputField(
        desc="excellent/good/moderate/poor"
    )
    specific_feedback: str = dspy.OutputField(
        desc="Feedback específico del día"
    )
    pattern_detected: str = dspy.OutputField(
        desc="Patrones vs días anteriores"
    )
    tomorrow_suggestion: str = dspy.OutputField()
```

#### 4.2.6 WorkoutLogger

```python
class WorkoutLogger(dspy.Signature):
    """
    Registra sesión de gym con comparación de progreso.
    """
    
    workout_type: str = dspy.InputField(
        desc="push/pull/legs"
    )
    exercises_input: str = dspy.InputField(
        desc="Lo que el usuario reportó (texto libre)"
    )
    last_session_data: dict = dspy.InputField(
        desc="Ejercicios de última sesión del mismo tipo"
    )
    
    exercises_structured: list = dspy.OutputField(
        desc="Ejercicios en formato estructurado"
    )
    progress_comparison: dict = dspy.OutputField(
        desc="Comparación ejercicio por ejercicio"
    )
    new_prs: list = dspy.OutputField(
        desc="Nuevos récords personales"
    )
    session_rating: str = dspy.OutputField(
        desc="excellent/good/normal/poor"
    )
    improvement_count: int = dspy.OutputField(
        desc="Ejercicios que mejoraron"
    )
    feedback: str = dspy.OutputField(
        desc="Feedback de la sesión"
    )
    next_session_targets: dict = dspy.OutputField(
        desc="Objetivos para próxima sesión igual"
    )
```

#### 4.2.7 SpendingAnalyzer

```python
class SpendingAnalyzer(dspy.Signature):
    """
    Analiza una compra potencial en contexto financiero completo.
    """
    
    purchase_description: str = dspy.InputField()
    purchase_amount: float = dspy.InputField()
    available_budget: float = dspy.InputField(
        desc="Dinero disponible actual"
    )
    days_until_payday: int = dspy.InputField()
    total_debt: float = dspy.InputField()
    monthly_debt_interest: float = dspy.InputField(
        desc="Cuánto paga de intereses mensuales"
    )
    financial_goals: list = dspy.InputField()
    recent_purchases: list = dspy.InputField(
        desc="Compras de esta quincena"
    )
    
    is_essential: bool = dspy.OutputField()
    category: str = dspy.OutputField(
        desc="tech/food/entertainment/education/other"
    )
    impact_on_budget: str = dspy.OutputField(
        desc="low/medium/high/critical"
    )
    impact_on_debt_timeline: str = dspy.OutputField(
        desc="Cómo afecta tiempo para liquidar deuda"
    )
    honest_questions: list = dspy.OutputField(
        desc="Preguntas para reflexión (máx 3)"
    )
    recommendation: str = dspy.OutputField(
        desc="buy/wait/skip/find_alternative"
    )
    alternative_suggestion: str = dspy.OutputField()
    guilt_free_option: str = dspy.OutputField(
        desc="Cómo podría comprarlo sin culpa"
    )
```

#### 4.2.8 PaydayPlanner

```python
class PaydayPlanner(dspy.Signature):
    """
    Crea plan de distribución para la quincena.
    """
    
    income_amount: float = dspy.InputField()
    fixed_expenses: list = dspy.InputField(
        desc="Lista de gastos fijos con montos"
    )
    debt_payments: list = dspy.InputField(
        desc="Deudas con mínimos y recomendación de extra"
    )
    financial_goals: list = dspy.InputField()
    last_period_data: dict = dspy.InputField(
        desc="Cómo le fue la quincena pasada"
    )
    
    fixed_allocation: dict = dspy.OutputField(
        desc="Distribución a gastos fijos"
    )
    debt_allocation: dict = dspy.OutputField(
        desc="Distribución a deudas (mínimo + extra)"
    )
    extra_debt_payment: float = dspy.OutputField(
        desc="Recomendación de pago extra a deuda prioritaria"
    )
    available_for_variable: float = dspy.OutputField(
        desc="Dinero realmente disponible"
    )
    daily_budget: float = dspy.OutputField(
        desc="Presupuesto diario sugerido"
    )
    warnings: list = dspy.OutputField(
        desc="Alertas si hay riesgo"
    )
    debt_progress_projection: str = dspy.OutputField(
        desc="Proyección si sigue el plan"
    )
```

#### 4.2.9 DebtStrategist

```python
class DebtStrategist(dspy.Signature):
    """
    Analiza deudas y crea estrategia óptima de pago.
    """
    
    debts: list = dspy.InputField(
        desc="Lista de deudas con monto, tasa, mínimo"
    )
    monthly_income: float = dspy.InputField()
    monthly_fixed_expenses: float = dspy.InputField()
    available_for_debt: float = dspy.InputField(
        desc="Dinero mensual disponible para deudas"
    )
    
    recommended_strategy: str = dspy.OutputField(
        desc="avalanche/snowball/hybrid"
    )
    strategy_explanation: str = dspy.OutputField()
    payment_order: list = dspy.OutputField(
        desc="Orden de ataque a las deudas"
    )
    monthly_payment_plan: dict = dspy.OutputField(
        desc="Cuánto pagar a cada deuda"
    )
    months_to_debt_free: int = dspy.OutputField()
    total_interest_if_minimum: float = dspy.OutputField()
    total_interest_with_plan: float = dspy.OutputField()
    interest_saved: float = dspy.OutputField()
    milestones: list = dspy.OutputField(
        desc="Fechas clave (primera deuda liquidada, etc)"
    )
```

#### 4.2.10 StudyBalancer

```python
class StudyBalancer(dspy.Signature):
    """
    Sugiere qué estudiar basado en balance y progreso.
    """
    
    study_projects: list = dspy.InputField(
        desc="Proyectos de aprendizaje con hitos"
    )
    recent_sessions: list = dspy.InputField(
        desc="Sesiones de estudio de última semana"
    )
    project_deadlines: list = dspy.InputField()
    user_preference_today: str = dspy.InputField(
        desc="Si pidió algo específico, o vacío"
    )
    energy_level: str = dspy.InputField(
        desc="high/medium/low basado en el día"
    )
    
    suggested_topic: str = dspy.OutputField()
    suggestion_reason: str = dspy.OutputField()
    alternative_topic: str = dspy.OutputField()
    balance_status: str = dspy.OutputField(
        desc="Estado del balance entre temas"
    )
    neglected_topics: list = dspy.OutputField(
        desc="Temas sin estudiar hace tiempo"
    )
    session_goal: str = dspy.OutputField(
        desc="Objetivo específico para la sesión"
    )
```

---

## 5. Flujos de Telegram

### 5.1 Comandos Disponibles

| Comando | Descripción |
|---------|-------------|
| `/start` | Iniciar bot, setup inicial |
| `/plan` | Ver plan del día actual |
| `/task [texto]` | Agregar tarea rápida |
| `/status` | Ver estado general |
| `/gym` | Registrar workout |
| `/food` | Registrar comidas |
| `/money` | Ver resumen financiero |
| `/project` | Gestionar proyectos |
| `/help` | Ver ayuda |

### 5.2 Horarios de Mensajes Proactivos

| Hora | Mensaje | Condición |
|------|---------|-----------|
| 6:30 | Morning Briefing | Siempre |
| 7:15, 7:30, 7:45 | Gym reminder | Si no confirmó gym |
| 9:35 | Post-daily check | Días laborales |
| 10:30, 11:30 | Deep work check-in | Si está en deep work |
| 12:30 | Fin deep work 1 | Días laborales |
| 14:00 | Inicio comida | Siempre |
| 15:30 | Fin comida | Siempre |
| 16:30 | Check-in tarde | Días laborales |
| 17:30 | Hora de estudio | Siempre |
| 18:30 | Cierre laboral | Días laborales |
| 21:00 | Registro nutrición | Siempre |
| Domingo 10:00 | Review semanal | Semanal |
| Día 13, 28 | Pre-quincena | Quincenal |
| Día 15, 30 | Post-quincena | Quincenal |

### 5.3 Flujo de Conversación: Captura Rápida

```
┌──────────────────────────────────────────────────────────────┐
│                    CAPTURA RÁPIDA                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  USER: "agregar endpoint de validación"                      │
│                           │                                  │
│                           ▼                                  │
│                  ┌─────────────────┐                        │
│                  │ InboxProcessor  │                        │
│                  │   confidence?   │                        │
│                  └────────┬────────┘                        │
│                           │                                  │
│           ┌───────────────┼───────────────┐                 │
│           ▼               ▼               ▼                 │
│      conf > 80%      50-80%          < 50%                  │
│           │               │               │                 │
│           ▼               ▼               ▼                 │
│   "✅ Agregado a      "¿Para qué       "No entendí,       │
│    PayCash: Endpoint   proyecto es?"    ¿me explicas       │
│    de validación"                        más?"              │
│           │               │               │                 │
│           ▼               ▼               ▼                 │
│   ┌─────────────┐   USER responde    USER responde         │
│   │ Complexity  │         │               │                 │
│   │  Analyzer   │         ▼               ▼                 │
│   └──────┬──────┘   Clasificar       Clasificar            │
│          │                                                   │
│          ▼                                                   │
│   "🔴 Tarea Heavy                                           │
│    ~2h estimadas                                            │
│    ¿La divido en                                            │
│    subtareas?"                                               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 5.4 Flujo: Deep Work Protection

```
┌──────────────────────────────────────────────────────────────┐
│                 DEEP WORK PROTECTION                         │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  [9:30] BOT: "🧠 DEEP WORK iniciado                         │
│              Tarea: Endpoint de pagos                        │
│              Hasta: 12:30"                                   │
│                                                              │
│  [10:15] USER: "revisa las propuestas de workana"           │
│                           │                                  │
│                           ▼                                  │
│                  ┌─────────────────┐                        │
│                  │ TimeBlockGuard  │                        │
│                  │  is_distraction │                        │
│                  └────────┬────────┘                        │
│                           │                                  │
│                      TRUE │                                  │
│                           ▼                                  │
│         BOT: "⚠️ Estás en Deep Work                         │
│               hasta las 12:30.                               │
│                                                              │
│               Workana está agendado                          │
│               para 16:00-18:00.                              │
│                                                              │
│               ¿Qué prefieres?                                │
│               🧠 Seguir con Deep Work                        │
│               🔄 Cambiar a Workana                           │
│               ⏰ Solo 5 min y vuelvo"                        │
│                                                              │
│  USER: "solo 5 min"                                          │
│                           │                                  │
│                           ▼                                  │
│         BOT: "⏱️ Timer de 5 min activado.                   │
│               Te aviso cuando pasen."                        │
│                           │                                  │
│                    [5 min después]                           │
│                           │                                  │
│                           ▼                                  │
│         BOT: "⏰ ¡5 minutos!                                 │
│               Hora de volver a                               │
│               'Endpoint de pagos'.                           │
│               ¿Listo?"                                       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 5.5 Flujo: Análisis de Compra

```
┌──────────────────────────────────────────────────────────────┐
│                   ANÁLISIS DE COMPRA                         │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  USER: "estoy viendo unos audífonos en 2500"                │
│                           │                                  │
│                           ▼                                  │
│                  ┌─────────────────┐                        │
│                  │ SpendingAnalyzer│                        │
│                  └────────┬────────┘                        │
│                           │                                  │
│                           ▼                                  │
│  BOT: "🛒 Compra potencial: Audífonos $2,500                │
│                                                              │
│        📊 Tu situación:                                      │
│        • Disponible: $3,500                                  │
│        • Días para quincena: 12                              │
│        • Después de compra: $1,000                           │
│                                                              │
│        💳 Impacto en deuda:                                  │
│        Si estos $2,500 van a la tarjeta,                    │
│        reduces 1 semana el tiempo de pago.                   │
│                                                              │
│        🤔 Preguntas honestas:                                │
│        • ¿Los necesitas o los quieres?                       │
│        • ¿Tus audífonos actuales funcionan?                  │
│                                                              │
│        ¿Qué decides?                                         │
│        🛒 Los compro (consciente)                            │
│        📅 Los agrego a wishlist                              │
│        💰 Los compro del próximo freelance                   │
│        ❌ Tienes razón, no los necesito"                     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 6. API Endpoints (FastAPI)

### 6.1 Base URL

```
http://localhost:8000/api/v1
```

### 6.2 Endpoints

#### Health Check
```
GET /health
Response: { "status": "ok", "timestamp": "..." }
```

#### Inbox
```
POST /inbox
Body: {
  "content": "string",
  "source": "telegram" | "manual" | "voice",
  "user_context": "string" (opcional)
}
Response: {
  "id": "uuid",
  "task_title": "string",
  "confidence": 0.0-1.0,
  "suggested_project": "string",
  "needs_clarification": boolean,
  "clarification_question": "string" | null,
  "complexity": "quick" | "standard" | "heavy" | "epic"
}
```

#### Tasks
```
GET /tasks/today
Response: {
  "date": "YYYY-MM-DD",
  "tasks": [...],
  "time_blocks": {...}
}

POST /tasks/{task_id}/status
Body: {
  "status": "doing" | "done" | "blocked" | "paused",
  "notes": "string" (opcional),
  "blocker": "string" (opcional),
  "actual_time": number (opcional)
}
Response: { "updated": true, "follow_up": "string" | null }

POST /tasks/{task_id}/jira-help
Body: {
  "description": "string" (texto o transcripción)
}
Response: {
  "jira_title": "string",
  "jira_description": "string",
  "suggested_labels": [...]
}
```

#### Morning Plan
```
GET /morning-plan
Response: {
  "greeting": "string",
  "date": "YYYY-MM-DD",
  "top_3_tasks": [...],
  "calendar_events": [...],
  "reminders": [...],
  "habits": {
    "gym": { "scheduled": boolean, "time": "HH:MM" },
    "study": { "topic": "string" }
  },
  "financial_alert": "string" | null
}
```

#### Check-in
```
POST /check-in
Body: {
  "type": "hourly" | "block_end" | "deep_work",
  "current_task_id": "uuid" (opcional)
}
Response: {
  "questions": [...],
  "suggestions": [...],
  "next_check_in": "HH:MM"
}
```

#### Nutrition
```
POST /nutrition/log
Body: {
  "date": "YYYY-MM-DD",
  "meals_description": "string"
}
Response: {
  "breakdown": {
    "breakfast": { "description": "...", "calories": N, "category": "..." },
    "lunch": {...},
    "dinner": {...},
    "snacks": {...}
  },
  "total_calories": N,
  "evaluation": "excellent" | "good" | "moderate" | "poor",
  "feedback": "string",
  "protein_ok": boolean,
  "vegetables_ok": boolean
}
```

#### Workouts
```
POST /workout/log
Body: {
  "date": "YYYY-MM-DD",
  "type": "push" | "pull" | "legs",
  "exercises_description": "string"
}
Response: {
  "exercises": [...],
  "comparison": {
    "improved": N,
    "maintained": N,
    "decreased": N
  },
  "prs": [...],
  "rating": "excellent" | "good" | "normal" | "poor",
  "feedback": "string",
  "next_targets": {...}
}

GET /workout/progress
Query: ?weeks=4
Response: {
  "attendance": { "total": N, "completed": N, "rate": 0.0-1.0 },
  "by_type": {
    "push": { "sessions": N, "progress": "..." },
    "pull": {...},
    "legs": {...}
  },
  "weight_trend": [...],
  "prs_this_period": [...]
}
```

#### Finance
```
GET /finance/summary
Query: ?period=current_fortnight | month | year
Response: {
  "period": "string",
  "income": { "total": N, "breakdown": [...] },
  "expenses": { "total": N, "fixed": N, "variable": N, "breakdown": [...] },
  "debt_payments": { "total": N, "breakdown": [...] },
  "available": N,
  "debt_status": {
    "total": N,
    "monthly_interest": N,
    "progress_this_month": N
  }
}

POST /finance/purchase/analyze
Body: {
  "description": "string",
  "amount": number
}
Response: {
  "is_essential": boolean,
  "category": "string",
  "impact": "low" | "medium" | "high" | "critical",
  "honest_questions": [...],
  "recommendation": "buy" | "wait" | "skip" | "alternative",
  "debt_impact": "string",
  "alternative": "string" | null
}

GET /finance/payday-plan
Query: ?amount=number
Response: {
  "income": N,
  "distribution": {
    "fixed": {...},
    "debt_minimum": {...},
    "debt_extra": {...},
    "available": N
  },
  "daily_budget": N,
  "warnings": [...],
  "debt_projection": "string"
}
```

#### Projects
```
GET /projects
Query: ?type=all | trabajo | freelance | aprendizaje | ...
Response: {
  "projects": [...],
  "needs_attention": [...]
}

POST /projects
Body: {
  "name": "string",
  "type": "string",
  "objective": "string" (opcional),
  "generates_money": boolean,
  "potential_income": number (opcional),
  "generates_wellbeing": [...] (opcional),
  "cost": number (opcional)
}
Response: { "id": "uuid", "created": true }

GET /projects/{id}/status
Response: {
  "project": {...},
  "tasks": [...],
  "progress": {...},
  "days_since_activity": N
}
```

#### Study
```
GET /study/suggestion
Response: {
  "suggested_topic": "string",
  "reason": "string",
  "alternative": "string",
  "balance_status": "string",
  "session_goal": "string"
}

POST /study/session
Body: {
  "topic": "string",
  "duration_minutes": number,
  "notes": "string" (opcional),
  "progress_update": "string" (opcional)
}
Response: { "logged": true, "streak": N }
```

---

## 7. Configuración de N8N

### 7.1 Workflows Principales

#### 7.1.1 Morning Briefing (Cron: 6:30 AM)
```
[Cron Trigger 6:30]
       │
       ▼
[HTTP Request: GET /morning-plan]
       │
       ▼
[Format Message]
       │
       ▼
[Telegram: Send Message]
       │
       ▼
[Wait for Reply]
       │
       ▼
[HTTP Request: POST /inbox or /tasks/status]
```

#### 7.1.2 Hourly Check-in (Cron: cada hora 9-18)
```
[Cron Trigger hourly]
       │
       ▼
[Check: Is Deep Work?]
       │
   ┌───┴───┐
   │       │
   ▼       ▼
 [Yes]   [No]
   │       │
   ▼       ▼
[Light   [Full
check]   check]
   │       │
   └───┬───┘
       │
       ▼
[Telegram: Send Check-in]
```

#### 7.1.3 Telegram Message Handler (Webhook)
```
[Telegram Webhook]
       │
       ▼
[Parse Message]
       │
       ▼
[Route by Content]
       │
   ┌───┼───┬───┬───┐
   │   │   │   │   │
   ▼   ▼   ▼   ▼   ▼
[Cmd][Task][Gym][Food][Purchase]
   │   │   │   │   │
   ▼   ▼   ▼   ▼   ▼
[Respective API Endpoint]
       │
       ▼
[Telegram: Send Response]
```

#### 7.1.4 Gym Reminder Loop
```
[Cron 7:15]
       │
       ▼
[Check: Gym confirmed?]
       │
   ┌───┴───┐
   │       │
   ▼       ▼
 [Yes]   [No]
   │       │
   ▼       ▼
[Stop]  [Send Reminder]
           │
           ▼
        [Wait 15 min]
           │
           ▼
        [Check again]
           │
         (loop max 3x)
```

#### 7.1.5 Pre-Payday Alert (Cron: día 13 y 28)
```
[Cron día 13/28]
       │
       ▼
[HTTP Request: GET /finance/payday-plan]
       │
       ▼
[Format Financial Alert]
       │
       ▼
[Telegram: Send with Buttons]
```

### 7.2 Variables de Entorno N8N

```env
FASTAPI_URL=http://fastapi:8000/api/v1
TELEGRAM_BOT_TOKEN=xxx
NOTION_API_KEY=xxx
USER_TELEGRAM_ID=xxx
```

---

## 8. Datos del Usuario

### 8.1 Perfil Carlos

```yaml
personal:
  name: Carlos
  age: 25
  location: México
  partner: Sí (él la apoya económicamente)
  pets: 2 perros

work:
  primary:
    company: PayCash
    role: Fullstack Developer
    type: Remoto
    schedule: "9:00-19:00"
    daily_standup: "9:00 AM"
    tools: [Jira, NetSuite, JavaScript, Python]
  
  freelance:
    platforms: [Workana]
    active_clients: 2
    specialties: [Power Automate, Web Development]
    average_monthly: Variable (~$4,500 MXN primera semana)

schedule:
  wake_up: "6:00-7:00 AM"
  gym_preferred: "7:00-8:00 AM"
  lunch: "14:00-15:30"
  study_hour: "17:30-18:30"
  end_work: "19:00"

goals:
  health:
    - Gym 5 días/semana (PPL)
    - Tracking de peso
    - Alimentación consciente
  
  financial:
    - Liquidar deuda de $330,000 MXN
    - Prioridad: Tarjeta (60% interés)
    - No compras impulsivas
  
  professional:
    - No olvidar actualizar Jira
    - Prospectar clientes freelance
    - Aprender edición de video
  
  personal:
    - No burnout
    - Time blocking efectivo
    - Sistema Second Brain funcional

pain_points:
  - Se le olvida actualizar Jira
  - Comprador compulsivo
  - Ideas/tareas se pierden
  - No tiene bloques claros de trabajo
  - Abrumado con muchas cosas abiertas
```

### 8.2 Datos Financieros Actuales

```yaml
income:
  monthly:
    paycash: 50000  # MXN, quincenal (25K x 2)
    freelance: 4500  # Variable, primera semana
  total: 54500

expenses:
  fixed:
    car_payment: 12000
    starlink: 1000
    gym: 400
    claude_max: 2000
    ps_plus: 150
    food_base: 8000  # 2 personas + 2 perros
    # Notion: 0 (plan gratis)
  total_fixed: 23550

debts:
  - name: "Tarjeta Banco"
    original: 80000
    current: 80000
    interest_rate: 60  # % anual
    monthly_interest: 4000
    minimum_payment: 4000
    priority: 1
    
  - name: "Coppel"
    original: 30000
    current: 30000
    interest_rate: 50
    minimum_payment: 1800
    priority: 2
    
  - name: "Mercado Libre"
    original: 20000
    current: 20000
    interest_rate: 40
    minimum_payment: 1500
    priority: 3
    
  - name: "Carro"
    original: 200000
    current: 200000  # Aproximado
    interest_rate: 15
    monthly_payment: 12000  # Fijo
    priority: 4  # No adelantar

  total_debt: 330000
  total_minimum: 19300
  total_monthly_interest: ~6500

analysis:
  income: 54500
  fixed_expenses: 23550
  debt_minimums: 19300
  remaining: 11650
  
  recommended_extra_debt: 8000
  available_after_plan: 3650
  
  months_to_debt_free:
    aggressive: 10-12  # Si abona $8K extra/mes
    minimum_only: "Nunca"  # Intereses > pagos
```

### 8.3 Rutina de Gym (PPL)

```yaml
schedule:
  monday: Push
  tuesday: Pull
  wednesday: Legs
  thursday: Push
  friday: Pull
  saturday: Rest o Legs opcional
  sunday: Rest

exercises:
  push:
    - name: Press Banca
      target_sets: 3
      target_reps: 8-10
    - name: Press Inclinado
      target_sets: 3
      target_reps: 10-12
    - name: Press Militar
      target_sets: 3
      target_reps: 10-12
    - name: Fondos
      target_sets: 3
      target_reps: 12-15
    - name: Extensiones Tríceps
      target_sets: 3
      target_reps: 12-15
  
  pull:
    - name: Dominadas
      target_sets: 3
      target_reps: 8-10
    - name: Remo con Barra
      target_sets: 3
      target_reps: 8-10
    - name: Remo Mancuerna
      target_sets: 3
      target_reps: 10-12
    - name: Face Pulls
      target_sets: 3
      target_reps: 15-20
    - name: Curl Bíceps
      target_sets: 3
      target_reps: 10-12
  
  legs:
    - name: Sentadilla
      target_sets: 4
      target_reps: 6-8
    - name: Peso Muerto Rumano
      target_sets: 3
      target_reps: 8-10
    - name: Prensa
      target_sets: 3
      target_reps: 10-12
    - name: Curl Femoral
      target_sets: 3
      target_reps: 12-15
    - name: Pantorrillas
      target_sets: 4
      target_reps: 15-20

tracking:
  weight_day: Sunday
  goal: Perder grasa, mantener músculo
```

### 8.4 Proyectos de Estudio

```yaml
study_projects:
  - name: "Edición de Video (Premiere)"
    type: aprendizaje
    current_milestone: "Curso básico"
    progress: 30%
    in_rotation: true
    
  - name: "DSPy / AI Agents"
    type: aprendizaje
    current_milestone: "Implementar primer agente"
    progress: 20%
    in_rotation: true
    
  - name: "NetSuite Avanzado"
    type: aprendizaje
    current_milestone: "SuiteScript 2.0"
    progress: 50%
    in_rotation: true

rotation_rules:
  max_consecutive_days: 3
  priority_on_deadline: true
  balance_technical_creative: true
```

---

## 9. Plan de Implementación

### 9.1 Fases

```
┌─────────────────────────────────────────────────────────────┐
│                 ROADMAP DE IMPLEMENTACIÓN                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  FASE 0: Setup (Semana 1)                                  │
│  ├── Crear databases en Notion                             │
│  ├── Setup proyecto FastAPI                                │
│  ├── Setup bot Telegram                                    │
│  └── Conectar N8N                                          │
│                                                             │
│  FASE 1: Core Productivity (Semana 2-3)                    │
│  ├── InboxProcessor agent                                  │
│  ├── Captura rápida funcional                             │
│  ├── Morning briefing                                      │
│  ├── Hourly check-ins                                      │
│  └── Basic time blocking                                   │
│                                                             │
│  FASE 2: PM Features (Semana 4-5)                          │
│  ├── ComplexityAnalyzer agent                             │
│  ├── TimeBlockGuardian agent                              │
│  ├── JiraIntegrator agent                                 │
│  ├── Project management                                    │
│  └── Persistent reminders                                  │
│                                                             │
│  FASE 3: Health Module (Semana 6-7)                        │
│  ├── NutritionAnalyzer agent                              │
│  ├── WorkoutLogger agent                                  │
│  ├── ProgressAnalyzer agent                               │
│  ├── Gym reminders                                        │
│  └── Weight tracking                                       │
│                                                             │
│  FASE 4: Finance Module (Semana 8-9)                       │
│  ├── SpendingAnalyzer agent                               │
│  ├── PaydayPlanner agent                                  │
│  ├── DebtStrategist agent                                 │
│  ├── Purchase analysis                                     │
│  └── Financial alerts                                      │
│                                                             │
│  FASE 5: Study & Polish (Semana 10-12)                     │
│  ├── StudyBalancer agent                                  │
│  ├── Weekly reviews                                        │
│  ├── Dashboard Notion                                      │
│  ├── DSPy optimization                                     │
│  └── Bug fixes & refinements                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 9.2 Entregables por Fase

#### Fase 0: Setup
- [ ] 8 databases creadas en Notion con schemas correctos
- [ ] Proyecto FastAPI con estructura base
- [ ] Bot Telegram respondiendo a /start
- [ ] N8N conectado a Telegram webhook
- [ ] Docker compose para desarrollo local

#### Fase 1: Core Productivity
- [ ] Endpoint POST /inbox funcional
- [ ] InboxProcessor clasificando con >70% accuracy
- [ ] Morning briefing enviándose 6:30 AM
- [ ] Check-ins cada hora (9-18)
- [ ] Tasks moviéndose entre estados

#### Fase 2: PM Features
- [ ] Tareas dividiéndose automáticamente
- [ ] Deep work protegido
- [ ] Jira updates generándose
- [ ] Proyectos creándose conversacionalmente
- [ ] Recordatorios persistiendo hasta resolverse

#### Fase 3: Health Module
- [ ] Comidas registrándose al final del día
- [ ] Workouts con comparación vs anterior
- [ ] PRs detectándose automáticamente
- [ ] Peso corporal graficándose
- [ ] Gym reminders insistentes

#### Fase 4: Finance Module
- [ ] Compras analizándose en contexto
- [ ] Pre-quincena alertas funcionando
- [ ] Plan de distribución generándose
- [ ] Deudas trackeándose con proyección
- [ ] Compras impulsivas flaggeándose

#### Fase 5: Study & Polish
- [ ] Rotación de estudio balanceada
- [ ] Review semanal completo (domingo)
- [ ] Dashboard Notion con métricas
- [ ] Agents optimizados con ejemplos
- [ ] Sistema estable y usable

---

## 10. Anexos

### 10.1 Estructura de Archivos del Proyecto

```
carlos-command/
├── docker-compose.yml
├── .env
├── README.md
│
├── api/
│   ├── main.py
│   ├── config.py
│   ├── requirements.txt
│   │
│   ├── routers/
│   │   ├── inbox.py
│   │   ├── tasks.py
│   │   ├── projects.py
│   │   ├── nutrition.py
│   │   ├── workouts.py
│   │   ├── finance.py
│   │   └── study.py
│   │
│   ├── agents/
│   │   ├── base.py
│   │   ├── inbox_processor.py
│   │   ├── complexity_analyzer.py
│   │   ├── time_block_guardian.py
│   │   ├── morning_planner.py
│   │   ├── checkin_agent.py
│   │   ├── jira_integrator.py
│   │   ├── nutrition_analyzer.py
│   │   ├── workout_logger.py
│   │   ├── progress_analyzer.py
│   │   ├── spending_analyzer.py
│   │   ├── payday_planner.py
│   │   ├── debt_strategist.py
│   │   └── study_balancer.py
│   │
│   ├── services/
│   │   ├── notion.py
│   │   ├── telegram.py
│   │   └── gemini.py
│   │
│   ├── models/
│   │   ├── task.py
│   │   ├── project.py
│   │   ├── workout.py
│   │   ├── nutrition.py
│   │   └── finance.py
│   │
│   └── utils/
│       ├── date_utils.py
│       └── formatters.py
│
├── bot/
│   ├── main.py
│   ├── handlers/
│   │   ├── commands.py
│   │   ├── messages.py
│   │   └── callbacks.py
│   └── keyboards/
│       └── inline.py
│
├── n8n/
│   └── workflows/
│       ├── morning_briefing.json
│       ├── hourly_checkin.json
│       ├── gym_reminder.json
│       ├── telegram_handler.json
│       └── payday_alert.json
│
└── scripts/
    ├── setup_notion.py
    ├── migrate_data.py
    └── test_agents.py
```

### 10.2 Docker Compose

```yaml
version: '3.8'

services:
  api:
    build: ./api
    ports:
      - "8000:8000"
    environment:
      - NOTION_API_KEY=${NOTION_API_KEY}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - DATABASE_URL=sqlite:///./data/carlos.db
    volumes:
      - ./data:/app/data
    restart: unless-stopped

  bot:
    build: ./bot
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - API_URL=http://api:8000
    depends_on:
      - api
    restart: unless-stopped

  n8n:
    image: n8nio/n8n
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${N8N_USER}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD}
    volumes:
      - ./n8n/data:/home/node/.n8n
    restart: unless-stopped
```

### 10.3 Variables de Entorno

```env
# Notion
NOTION_API_KEY=secret_xxx

# Telegram
TELEGRAM_BOT_TOKEN=xxx:yyy

# Gemini
GEMINI_API_KEY=xxx

# N8N
N8N_USER=carlos
N8N_PASSWORD=xxx

# API
API_SECRET_KEY=xxx
DEBUG=false
```

### 10.4 Métricas de Éxito

| Métrica | Objetivo Mes 1 | Objetivo Mes 3 |
|---------|----------------|----------------|
| Tareas capturadas/día | 5+ | 10+ |
| % Jira actualizado | 70% | 95% |
| Gym días/semana | 4/5 | 5/5 |
| Comidas registradas | 5/7 días | 7/7 días |
| Compras analizadas | 80% | 100% |
| Abono extra a deuda | $8,000/mes | $10,000/mes |
| Horas estudio/semana | 5h | 7h |
| Deep work blocks/día | 1 | 2 |

---

## 📝 Notas Finales

Este documento es la **especificación completa** del sistema Carlos Command. Debe actualizarse conforme se implementen cambios o se descubran nuevos requerimientos.

**Próximo paso:** Crear las 8 databases en Notion con los schemas exactos definidos aquí.

---

*Documento generado: Noviembre 2025*  
*Versión: 1.0*  
*Autor: Claude + Carlos*