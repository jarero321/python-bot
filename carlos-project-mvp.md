# 🎮 Carlos Command - Plan de Implementación

## 📋 Resumen del Proyecto

**Objetivo:** Bot de Telegram con AI agents para gestión integral de vida (productividad, salud, finanzas).

**Stack Tecnológico:**
- **Runtime:** Docker + Docker Compose
- **Backend:** FastAPI (Python 3.11+)
- **AI Framework:** DSPy + Gemini API
- **Bot:** python-telegram-bot (webhooks)
- **Scheduler:** APScheduler (cron jobs)
- **Base de Datos:** SQLite (estado, métricas, reminders)
- **External API:** Notion API
- **Hosting:** VPS propio

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                         VPS (Docker)                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                      FastAPI App                          │  │
│  │                                                           │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │  │
│  │  │  Telegram   │  │ APScheduler │  │   DSPy Agents   │   │  │
│  │  │  Webhook    │  │   (Crons)   │  │                 │   │  │
│  │  │  Handler    │  │             │  │  - Inbox        │   │  │
│  │  └──────┬──────┘  └──────┬──────┘  │  - Spending     │   │  │
│  │         │                │         │  - Morning      │   │  │
│  │         │                │         │  - Nutrition    │   │  │
│  │         └────────┬───────┘         │  - Workout      │   │  │
│  │                  │                 │  - etc...       │   │  │
│  │                  ▼                 └────────┬────────┘   │  │
│  │         ┌───────────────┐                   │            │  │
│  │         │   Services    │◄──────────────────┘            │  │
│  │         │               │                                │  │
│  │         │ - Notion SDK  │                                │  │
│  │         │ - Telegram    │                                │  │
│  │         │ - Gemini LLM  │                                │  │
│  │         └───────┬───────┘                                │  │
│  │                 │                                        │  │
│  └─────────────────┼────────────────────────────────────────┘  │
│                    │                                           │
│  ┌─────────────────▼────────────────────────────────────────┐  │
│  │                    SQLite Database                        │  │
│  │  - conversation_state    - scheduled_reminders            │  │
│  │  - agent_metrics         - user_preferences               │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │        External APIs          │
              │  - Notion API                 │
              │  - Telegram Bot API           │
              │  - Google Gemini API          │
              └───────────────────────────────┘
```

---

## 📁 Estructura del Proyecto

```
carlos-command/
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── .env
├── requirements.txt
├── pyproject.toml
├── README.md
│
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app + startup/shutdown
│   ├── config.py                   # Settings con Pydantic
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── telegram_webhook.py     # POST /webhook/telegram
│   │   ├── health.py               # GET /health
│   │   └── debug.py                # Endpoints de debug (opcional)
│   │
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── handlers.py             # Command handlers (/start, /help, etc)
│   │   ├── conversations.py        # Flujos conversacionales
│   │   ├── keyboards.py            # Inline keyboards
│   │   └── messages.py             # Templates de mensajes
│   │
│   ├── scheduler/
│   │   ├── __init__.py
│   │   ├── setup.py                # APScheduler config
│   │   └── jobs/
│   │       ├── __init__.py
│   │       ├── morning_briefing.py     # 6:30 AM
│   │       ├── hourly_checkin.py       # Cada hora 9-18
│   │       ├── gym_reminder.py         # 7:15, 7:30, 7:45
│   │       ├── nutrition_reminder.py   # 21:00
│   │       ├── pre_payday.py           # Día 13 y 28
│   │       ├── weekly_review.py        # Domingo 10:00
│   │       └── persistent_reminders.py # Check cada 30 min
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py                 # DSPy config + LLM setup
│   │   ├── inbox_processor.py      # Clasificar mensajes
│   │   ├── complexity_analyzer.py  # Analizar complejidad
│   │   ├── spending_analyzer.py    # Analizar compras
│   │   ├── morning_planner.py      # Plan del día
│   │   ├── checkin_agent.py        # Preguntar status
│   │   ├── jira_helper.py          # Ayuda documentación
│   │   ├── nutrition_analyzer.py   # Analizar comidas
│   │   ├── workout_logger.py       # Registrar gym
│   │   ├── progress_analyzer.py    # Progreso semanal
│   │   ├── payday_planner.py       # Distribuir quincena
│   │   ├── debt_strategist.py      # Optimizar deudas
│   │   ├── study_balancer.py       # Sugerir estudio
│   │   └── persistent_reminder.py  # Gestionar recordatorios
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── notion.py               # Notion SDK wrapper
│   │   ├── telegram.py             # Telegram bot client
│   │   ├── gemini.py               # Gemini API client
│   │   └── cache.py                # Cache en memoria
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py             # SQLite connection
│   │   ├── models.py               # SQLAlchemy models
│   │   └── repositories/
│   │       ├── __init__.py
│   │       ├── reminders.py
│   │       ├── conversation_state.py
│   │       └── metrics.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── datetime_mx.py          # Timezone México
│       ├── formatters.py           # Formateo de mensajes
│       └── validators.py           # Validaciones
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_agents/
│   ├── test_services/
│   └── test_handlers/
│
├── scripts/
│   ├── setup_telegram_webhook.py
│   ├── test_notion_connection.py
│   └── seed_initial_data.py
│
└── data/
    └── carlos_command.db           # SQLite database
```

---

## ✅ Lista de Tareas

### Fase 0: Setup Inicial (Día 1-2)

#### 0.1 Infraestructura Base ✅ COMPLETADA
- [x] Crear repositorio Git
- [x] Crear estructura de carpetas
- [x] Configurar `.gitignore`
- [x] Crear `requirements.txt` con dependencias
- [x] Crear `pyproject.toml` para configuración del proyecto
- [x] Crear `.env.example` con todas las variables necesarias

#### 0.2 Docker Setup ✅ COMPLETADA
- [x] Crear `Dockerfile` para la aplicación
- [x] Crear `docker-compose.yml` con servicios (app + ngrok)
- [x] Configurar volúmenes para SQLite y logs
- [x] Configurar health checks
- [x] Test: `docker-compose up` funciona

#### 0.3 FastAPI Base ✅ COMPLETADA
- [x] Crear `app/main.py` con FastAPI app
- [x] Configurar CORS
- [x] Configurar logging
- [x] Crear endpoint `/health`
- [x] Crear `app/config.py` con Pydantic Settings
- [x] Test: API responde en localhost

#### 0.4 Telegram Bot Setup ✅ COMPLETADA
- [x] Crear bot en BotFather
- [x] Obtener token
- [x] Crear `app/services/telegram.py`
- [x] Crear `app/api/telegram_webhook.py`
- [x] Configurar webhook URL (ngrok)
- [x] Test: Bot responde a `/start`

#### 0.5 Notion Connection ✅ COMPLETADA
- [x] Verificar API key existente
- [x] Crear `app/services/notion.py` con SDK
- [x] Implementar funciones CRUD básicas
- [x] Mapear IDs de databases
- [x] Test: Leer/escribir en Notion funciona

#### 0.6 SQLite Setup ✅ COMPLETADA
- [x] Crear `app/db/database.py`
- [x] Crear `app/db/models.py` con tablas:
  - `conversation_state`
  - `scheduled_reminders`
  - `agent_metrics`
  - `user_preferences`
  - `daily_logs`
- [x] Implementar repositories (conversation_state, reminders, metrics)
- [x] Test: CRUD en SQLite funciona

---

### Fase 1: Core Bot (Día 3-5) ✅ COMPLETADA

#### 1.1 Handlers Básicos ✅
- [x] Implementar `/start` - Bienvenida
- [x] Implementar `/help` - Lista de comandos
- [x] Implementar `/status` - Estado actual
- [x] Implementar `/today` - Tareas de hoy
- [x] Crear `app/bot/keyboards.py` con inline keyboards

#### 1.2 Captura Rápida (Inbox) ✅
- [x] Crear flujo: mensaje → clasificación → confirmación
- [x] Implementar detección de contexto básico
- [x] Guardar en Notion Inbox
- [x] Test: Capturar tarea desde Telegram

#### 1.3 Comandos de Tareas ✅
- [x] Implementar `/add [tarea]` - Agregar tarea rápida
- [x] Implementar `/doing` - Marcar tarea en progreso
- [x] Implementar `/done` - Completar tarea
- [x] Implementar `/block [razón]` - Marcar bloqueada
- [x] Test: Ciclo completo de tarea

---

### Fase 2: DSPy Agents (Día 6-10) ✅ COMPLETADA

#### 2.1 Setup DSPy + Gemini ✅
- [x] Crear `app/agents/base.py`
- [x] Configurar Gemini como LLM
- [x] Implementar Signatures DSPy (ClassifyMessage, ExtractTaskInfo, etc.)
- [x] Implementar Modules DSPy (MessageClassifier, TaskExtractor, etc.)
- [x] Test: Llamada básica a Gemini funciona

#### 2.2 InboxProcessor Agent ✅
- [x] Definir Signature DSPy
- [x] Implementar clasificación de mensajes
- [x] Implementar sugerencia de proyecto/contexto
- [x] Implementar nivel de confianza
- [x] Implementar preguntas de clarificación
- [x] Test: Clasificación precisa >80%

#### 2.3 ComplexityAnalyzer Agent ✅
- [x] Definir Signature DSPy
- [x] Implementar análisis de complejidad
- [x] Implementar sugerencia de división
- [x] Implementar estimación de tiempo
- [x] Test: Estimaciones razonables

#### 2.4 SpendingAnalyzer Agent ✅
- [x] Definir Signature DSPy
- [x] Implementar análisis de compra
- [x] Implementar impacto en presupuesto
- [x] Implementar impacto en deuda
- [x] Implementar preguntas honestas
- [x] Test: Análisis de compra $2,500

---

### Fase 3: Scheduler & Crons (Día 11-14) ✅ COMPLETADA

> **Nota:** Todos los jobs implementados y registrados en `app/scheduler/setup.py`

#### 3.1 APScheduler Setup ✅
- [x] Crear `app/scheduler/setup.py`
- [x] Configurar AsyncIOScheduler
- [x] Configurar timezone México
- [x] Integrar con FastAPI startup/shutdown
- [x] Test: Job simple ejecuta correctamente

#### 3.2 Morning Briefing (6:30 AM) ✅
- [x] Crear `app/scheduler/jobs/morning_briefing.py`
- [x] Obtener tareas pendientes de Notion
- [x] Obtener tareas incompletas de ayer
- [x] Generar plan del día con MorningPlanner agent
- [x] Enviar mensaje a Telegram
- [x] Test: Mensaje de prueba enviado

#### 3.3 Hourly Check-in (9-18h) ✅
- [x] Crear `app/scheduler/jobs/hourly_checkin.py`
- [x] Verificar si hay tarea activa
- [x] Preguntar status si no hay update en 1h
- [x] Manejar respuestas (bien/trabado/cambio)
- [x] Test: Check-in cada hora

#### 3.4 Gym Reminders (7:15, 7:30, 7:45) ✅
- [x] Crear `app/scheduler/jobs/gym_reminder.py`
- [x] Verificar si ya confirmó gym
- [x] Escalación: gentle → normal → insistente
- [x] Permitir reprogramar/skip
- [x] Test: Secuencia de recordatorios

#### 3.5 Nutrition Reminder (21:00) ✅
- [x] Crear `app/scheduler/jobs/nutrition_reminder.py`
- [x] Preguntar qué comió hoy
- [x] Parsear respuesta con NutritionAnalyzer
- [x] Guardar en Notion Daily Nutrition
- [x] Test: Registro completo de día

#### 3.6 Pre-Payday Alert (Día 13 y 28) ✅
- [x] Crear `app/scheduler/jobs/payday_alert.py`
- [x] Calcular gastos fijos del período
- [x] Calcular pagos de deuda
- [x] Generar plan de distribución
- [x] Enviar resumen con keyboard de acciones
- [x] Test: Alerta 2 días antes de quincena

#### 3.7 Weekly Review (Domingo 10:00) ✅
- [x] Crear `app/scheduler/jobs/weekly_review.py`
- [x] Recopilar métricas de la semana:
  - Tareas completadas
  - Gym attendance
  - Progreso de nutrición
  - Gastos vs ingresos
- [x] Generar resumen formateado
- [x] Test: Review completo

#### 3.8 Persistent Reminders (cada 30 min) ✅
- [x] Crear `app/scheduler/jobs/persistent_reminders.py`
- [x] Leer reminders pendientes de SQLite
- [x] Aplicar lógica de escalación
- [x] Respetar horarios (no molestar en comida/noche)
- [x] Test: Recordatorio persiste hasta resolverse

---

### Fase 4: Agents Avanzados (Día 15-20) ✅ COMPLETADA

#### 4.1 JiraHelper Agent ✅
- [x] Definir Signature DSPy (GenerateJiraContent, GenerateUserStory)
- [x] Implementar generación de texto para Jira
- [x] Implementar formato de Historia de Usuario
- [x] Implementar sugerencia de story points
- [x] Test: Generar update de Jira

#### 4.2 WorkoutLogger Agent ✅
- [x] Definir Signature DSPy (ParseWorkoutInput)
- [x] Implementar parsing de ejercicios (JSON y manual)
- [x] Implementar comparación con sesión anterior
- [x] Implementar detección de PRs
- [x] Guardar en Notion Workouts
- [x] Test: Registrar sesión de gym

#### 4.3 NutritionAnalyzer Agent ✅
- [x] Definir Signature DSPy
- [x] Implementar parsing de comidas
- [x] Implementar estimación de calorías
- [x] Implementar evaluación de día
- [x] Implementar sugerencias
- [x] Test: Análisis de día completo

#### 4.4 DebtStrategist Agent ✅
- [x] Definir Signature DSPy (AnalyzeDebtStrategy)
- [x] Implementar estrategia avalanche/snowball/hybrid
- [x] Implementar proyección de pagos
- [x] Implementar cálculo de intereses ahorrados
- [x] Implementar milestones
- [x] Test: Plan de pago completo

#### 4.5 StudyBalancer Agent ✅
- [x] Definir Signature DSPy (SuggestStudyTopic)
- [x] Implementar rotación de temas
- [x] Implementar detección de temas descuidados
- [x] Implementar sugerencia basada en energía
- [x] Implementar análisis de balance
- [x] Test: Sugerencia balanceada

---

### Fase 5: Flujos Conversacionales (Día 21-25) ✅ COMPLETADA

#### 5.1 Flujo: Captura Rápida ✅
- [x] Usuario envía mensaje
- [x] Bot clasifica con InboxProcessor
- [x] Si confianza >80%: confirma clasificación
- [x] Si confianza 50-80%: pregunta específica
- [x] Si confianza <50%: pide contexto
- [x] Guardar en Notion (Task o Inbox)

#### 5.2 Flujo: Deep Work ✅
- [x] Usuario inicia con `/deepwork [tarea]`
- [x] Bot confirma bloque de tiempo (1h/2h/3h)
- [x] Actualiza tarea a "Doing"
- [x] Si bloqueado: registra blocker
- [x] Al terminar: registrar tiempo real

#### 5.3 Flujo: Análisis de Compra ✅
- [x] Usuario menciona precio ($X o X pesos)
- [x] Bot detecta intención de compra
- [x] Analiza con SpendingAnalyzer
- [x] Muestra impacto en presupuesto/deuda
- [x] Ofrece opciones: comprar/wishlist/freelance/skip

#### 5.4 Flujo: Registro de Gym ✅
- [x] Usuario inicia con `/gym` o `/workout`
- [x] Selecciona tipo (Push/Pull/Legs/Cardio/Rest)
- [x] Usuario describe ejercicios
- [x] Bot parsea con WorkoutLogger
- [x] Bot detecta PRs y progreso
- [x] Guarda en Notion

#### 5.5 Flujo: Registro de Comidas ✅
- [x] Usuario inicia con `/food` o `/nutrition`
- [x] Usuario describe todo el día
- [x] Bot parsea y analiza con NutritionAnalyzer
- [x] Muestra breakdown y evaluación
- [x] Guarda en Notion

---

### Fase 6: Polish & Optimización (Día 26-30) 🔄 EN PROGRESO

#### 6.1 Error Handling ✅
- [x] Implementar manejo global de errores (`app/utils/errors.py`)
- [x] Implementar retry con backoff (tenacity)
- [x] Implementar fallbacks para API failures
- [x] Logging estructurado con contexto
- [ ] Alertas de errores críticos (Telegram)

#### 6.2 Performance ✅
- [x] Implementar caching de Notion queries (`app/utils/cache.py`)
- [x] Cache con TTL configurable por tipo de dato
- [x] Invalidación automática de cache en updates
- [ ] Optimizar prompts de DSPy
- [ ] Profiling de endpoints lentos

#### 6.3 Métricas & Monitoring ✅
- [x] Health check básico (`/health`)
- [x] Health check detallado (`/health/detailed`)
- [x] Estadísticas de cache
- [x] Estado del scheduler
- [ ] Métricas de agents (accuracy, latency)
- [ ] Dashboard simple en Notion

#### 6.4 Testing ⏸️ (Pausado por usuario)
- [ ] Tests unitarios para agents
- [ ] Tests de integración para flujos
- [ ] Tests de scheduler jobs
- [ ] Coverage >70%

#### 6.5 Documentación
- [ ] README completo
- [ ] Documentación de API
- [ ] Guía de deployment
- [ ] Guía de troubleshooting

---

## 📊 IDs de Notion (Referencia)

```python
NOTION_IDS = {
    "databases": {
        "inbox": "6a4c92f0fa26438186a51b456b6ac63c",
        "tasks": "bbfd07401cb146e286132fb36dd22501",
        "projects": "00ddf18ff47d44999d2f8587b248500f",
        "knowledge": "66367a534704483fac8ddd5256759f26",
        "nutrition": "56325465fd88435aa98ec6230735e567",
        "workouts": "8f2df8b8b657489498cf22fced671de1",
        "transactions": "5dc7d2d251e94bd1ae38095a853c74b7",
        "debts": "c7d0902e9cf04a339aaea353ec2cd803",
    },
    "data_sources": {
        "inbox": "8f8d2bce-c4c5-4686-acc1-521a33bf0c94",
        "tasks": "cd69aad8-c271-4dff-8fa0-f1ec6182868a",
        "projects": "7ba78cea-3852-4f8f-8bae-24f9e76dcfee",
        "knowledge": "b330a8f9-0f8d-483f-9d54-3b1bd6c9f927",
        "nutrition": "977eaacc-b1ef-4298-9ffd-39315d2c6b7f",
        "workouts": "ff7dd165-58e1-4c92-9e05-bdb8025d4f8c",
        "transactions": "3461869f-c4c1-42de-8fba-7f2f208e5565",
        "debts": "0062ec3e-818f-4b95-b5c4-a531b043299c",
    },
    "main_page": "2b89fe93-ba02-81a4-8626-c8849150b4f5",
}
```

---

## ⏰ Schedule de Cron Jobs

| Job | Cron | Descripción |
|-----|------|-------------|
| Morning Briefing | `30 6 * * *` | Plan del día |
| Gym Reminder 1 | `15 7 * * 1-5` | Gentle reminder |
| Gym Reminder 2 | `30 7 * * 1-5` | Normal reminder |
| Gym Reminder 3 | `45 7 * * 1-5` | Insistent reminder |
| Hourly Check-in | `30 9-18 * * 1-5` | Status check |
| Study Suggestion | `30 17 * * 1-5` | Qué estudiar |
| Nutrition Log | `0 21 * * *` | Registro comidas |
| Pre-Payday | `0 10 13,28 * *` | Alerta quincena |
| Weekly Review | `0 10 * * 0` | Review domingo |
| Persistent Check | `*/30 * * * *` | Reminders pendientes |

---

## 🔐 Variables de Entorno

```bash
# .env.example

# App
APP_ENV=development
DEBUG=true
LOG_LEVEL=INFO

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_WEBHOOK_URL=https://your-domain.com/webhook/telegram
TELEGRAM_CHAT_ID=your_chat_id

# Notion
NOTION_API_KEY=your_notion_api_key

# Gemini
GEMINI_API_KEY=your_gemini_api_key

# Database
DATABASE_URL=sqlite:///data/carlos_command.db

# Timezone
TZ=America/Mexico_City
```

---

## 📦 Dependencias Principales

```txt
# requirements.txt

# Web Framework
fastapi==0.109.0
uvicorn[standard]==0.27.0
python-multipart==0.0.6

# Telegram
python-telegram-bot==20.7

# AI
dspy-ai==2.4.0
google-generativeai==0.3.2

# Notion
notion-client==2.2.1

# Scheduler
apscheduler==3.10.4

# Database
sqlalchemy==2.0.25
aiosqlite==0.19.0

# Utils
python-dotenv==1.0.0
pydantic==2.5.3
pydantic-settings==2.1.0
httpx==0.26.0
tenacity==8.2.3

# Dev
pytest==7.4.4
pytest-asyncio==0.23.3
black==23.12.1
ruff==0.1.11
```

---

## 🚀 Comandos de Deploy

```bash
# Desarrollo local
docker-compose up --build

# Producción
docker-compose -f docker-compose.prod.yml up -d

# Ver logs
docker-compose logs -f app

# Restart
docker-compose restart app

# Setup webhook (una vez)
python scripts/setup_telegram_webhook.py
```

---

## 📈 Métricas de Éxito

| Métrica | Semana 1 | Mes 1 | Mes 3 |
|---------|----------|-------|-------|
| Tareas capturadas/día | 3+ | 5+ | 10+ |
| % Clasificación correcta | 70% | 85% | 95% |
| Gym días/semana | 3/5 | 4/5 | 5/5 |
| Comidas registradas | 3/7 | 5/7 | 7/7 |
| Tiempo respuesta bot | <5s | <3s | <2s |
| Uptime | 95% | 99% | 99.9% |

---

## 🔄 Próximos Pasos Inmediatos

1. **Hoy:** Crear repo + estructura base
2. **Mañana:** Docker + FastAPI funcionando
3. **Día 3:** Telegram webhook respondiendo
4. **Día 4:** Notion CRUD funcionando
5. **Día 5:** Primer agent (InboxProcessor) clasificando

---

*Documento creado: Noviembre 2025*
*Última actualización: 28 Noviembre 2025*

---

## 📈 Estado Actual del Proyecto

| Fase | Estado | Progreso |
|------|--------|----------|
| Fase 0: Setup Inicial | ✅ Completada | 100% |
| Fase 1: Core Bot | ✅ Completada | 100% |
| Fase 2: DSPy Agents | ✅ Completada | 100% |
| Fase 3: Scheduler & Crons | ✅ Completada | 100% |
| Fase 4: Agents Avanzados | ✅ Completada | 100% |
| Fase 5: Flujos Conversacionales | ✅ Completada | 100% |
| Fase 6: Polish & Optimización | 🔄 En progreso | ~70% |

**Próximos pasos prioritarios:**
1. ~~Implementar manejo global de errores~~ ✅
2. ~~Implementar caching de Notion queries~~ ✅
3. ~~Health checks detallados~~ ✅
4. Alertas de errores críticos a Telegram
5. README y documentación de deployment
6. Tests unitarios (cuando se reactive)
