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

#### 0.1 Infraestructura Base
- [ ] Crear repositorio Git
- [ ] Crear estructura de carpetas
- [ ] Configurar `.gitignore`
- [ ] Crear `requirements.txt` con dependencias
- [ ] Crear `pyproject.toml` para configuración del proyecto
- [ ] Crear `.env.example` con todas las variables necesarias

#### 0.2 Docker Setup
- [ ] Crear `Dockerfile` para la aplicación
- [ ] Crear `docker-compose.yml` con servicios
- [ ] Configurar volúmenes para SQLite y logs
- [ ] Configurar health checks
- [ ] Test: `docker-compose up` funciona

#### 0.3 FastAPI Base
- [ ] Crear `app/main.py` con FastAPI app
- [ ] Configurar CORS
- [ ] Configurar logging
- [ ] Crear endpoint `/health`
- [ ] Crear `app/config.py` con Pydantic Settings
- [ ] Test: API responde en localhost

#### 0.4 Telegram Bot Setup
- [ ] Crear bot en BotFather
- [ ] Obtener token
- [ ] Crear `app/services/telegram.py`
- [ ] Crear `app/api/telegram_webhook.py`
- [ ] Configurar webhook URL
- [ ] Test: Bot responde a `/start`

#### 0.5 Notion Connection
- [ ] Verificar API key existente
- [ ] Crear `app/services/notion.py` con SDK
- [ ] Implementar funciones CRUD básicas
- [ ] Mapear IDs de databases
- [ ] Test: Leer/escribir en Notion funciona

#### 0.6 SQLite Setup
- [ ] Crear `app/db/database.py`
- [ ] Crear `app/db/models.py` con tablas:
  - `conversation_state`
  - `scheduled_reminders`
  - `agent_metrics`
  - `user_preferences`
- [ ] Implementar migrations básicas
- [ ] Test: CRUD en SQLite funciona

---

### Fase 1: Core Bot (Día 3-5)

#### 1.1 Handlers Básicos
- [ ] Implementar `/start` - Bienvenida
- [ ] Implementar `/help` - Lista de comandos
- [ ] Implementar `/status` - Estado actual
- [ ] Implementar `/today` - Tareas de hoy
- [ ] Crear `app/bot/keyboards.py` con inline keyboards

#### 1.2 Captura Rápida (Inbox)
- [ ] Crear flujo: mensaje → clasificación → confirmación
- [ ] Implementar detección de contexto básico
- [ ] Guardar en Notion Inbox
- [ ] Test: Capturar tarea desde Telegram

#### 1.3 Comandos de Tareas
- [ ] Implementar `/add [tarea]` - Agregar tarea rápida
- [ ] Implementar `/doing` - Marcar tarea en progreso
- [ ] Implementar `/done` - Completar tarea
- [ ] Implementar `/block [razón]` - Marcar bloqueada
- [ ] Test: Ciclo completo de tarea

---

### Fase 2: DSPy Agents (Día 6-10)

#### 2.1 Setup DSPy + Gemini
- [ ] Crear `app/agents/base.py`
- [ ] Configurar Gemini como LLM
- [ ] Implementar retry logic
- [ ] Implementar caching de respuestas
- [ ] Test: Llamada básica a Gemini funciona

#### 2.2 InboxProcessor Agent
- [ ] Definir Signature DSPy
- [ ] Implementar clasificación de mensajes
- [ ] Implementar sugerencia de proyecto/contexto
- [ ] Implementar nivel de confianza
- [ ] Implementar preguntas de clarificación
- [ ] Test: Clasificación precisa >80%

#### 2.3 ComplexityAnalyzer Agent
- [ ] Definir Signature DSPy
- [ ] Implementar análisis de complejidad
- [ ] Implementar sugerencia de división
- [ ] Implementar estimación de tiempo
- [ ] Test: Estimaciones razonables

#### 2.4 SpendingAnalyzer Agent
- [ ] Definir Signature DSPy
- [ ] Implementar análisis de compra
- [ ] Implementar impacto en presupuesto
- [ ] Implementar impacto en deuda
- [ ] Implementar preguntas honestas
- [ ] Test: Análisis de compra $2,500

---

### Fase 3: Scheduler & Crons (Día 11-14)

#### 3.1 APScheduler Setup
- [ ] Crear `app/scheduler/setup.py`
- [ ] Configurar AsyncIOScheduler
- [ ] Configurar timezone México
- [ ] Integrar con FastAPI startup/shutdown
- [ ] Test: Job simple ejecuta correctamente

#### 3.2 Morning Briefing (6:30 AM)
- [ ] Crear `app/scheduler/jobs/morning_briefing.py`
- [ ] Obtener tareas pendientes de Notion
- [ ] Obtener tareas incompletas de ayer
- [ ] Generar plan del día con MorningPlanner agent
- [ ] Enviar mensaje a Telegram
- [ ] Test: Mensaje de prueba enviado

#### 3.3 Hourly Check-in (9-18h)
- [ ] Crear `app/scheduler/jobs/hourly_checkin.py`
- [ ] Verificar si hay tarea activa
- [ ] Preguntar status si no hay update en 1h
- [ ] Manejar respuestas (bien/trabado/cambio)
- [ ] Test: Check-in cada hora

#### 3.4 Gym Reminders (7:15, 7:30, 7:45)
- [ ] Crear `app/scheduler/jobs/gym_reminder.py`
- [ ] Verificar si ya confirmó gym
- [ ] Escalación: gentle → normal → insistente
- [ ] Permitir reprogramar/skip
- [ ] Test: Secuencia de recordatorios

#### 3.5 Nutrition Reminder (21:00)
- [ ] Crear `app/scheduler/jobs/nutrition_reminder.py`
- [ ] Preguntar qué comió hoy
- [ ] Parsear respuesta con NutritionAnalyzer
- [ ] Guardar en Notion Daily Nutrition
- [ ] Test: Registro completo de día

#### 3.6 Pre-Payday Alert (Día 13 y 28)
- [ ] Crear `app/scheduler/jobs/pre_payday.py`
- [ ] Calcular gastos fijos del período
- [ ] Calcular pagos de deuda
- [ ] Generar plan con PaydayPlanner
- [ ] Enviar resumen
- [ ] Test: Alerta 2 días antes de quincena

#### 3.7 Weekly Review (Domingo 10:00)
- [ ] Crear `app/scheduler/jobs/weekly_review.py`
- [ ] Recopilar métricas de la semana:
  - Tareas completadas
  - Gym attendance
  - Progreso de peso
  - Gastos vs presupuesto
- [ ] Generar resumen con ProgressAnalyzer
- [ ] Test: Review completo

#### 3.8 Persistent Reminders (cada 30 min)
- [ ] Crear `app/scheduler/jobs/persistent_reminders.py`
- [ ] Leer reminders pendientes de SQLite
- [ ] Aplicar lógica de escalación
- [ ] Respetar horarios (no molestar en comida/noche)
- [ ] Test: Recordatorio persiste hasta resolverse

---

### Fase 4: Agents Avanzados (Día 15-20)

#### 4.1 JiraHelper Agent
- [ ] Definir Signature DSPy
- [ ] Implementar generación de texto para Jira
- [ ] Implementar formato de Historia de Usuario
- [ ] Implementar sugerencia de tiempo
- [ ] Test: Generar update de Jira

#### 4.2 WorkoutLogger Agent
- [ ] Definir Signature DSPy
- [ ] Implementar parsing de ejercicios
- [ ] Implementar comparación con sesión anterior
- [ ] Implementar detección de PRs
- [ ] Guardar en Notion Workouts
- [ ] Test: Registrar sesión de gym

#### 4.3 NutritionAnalyzer Agent
- [ ] Definir Signature DSPy
- [ ] Implementar parsing de comidas
- [ ] Implementar estimación de calorías
- [ ] Implementar evaluación de día
- [ ] Implementar sugerencias
- [ ] Test: Análisis de día completo

#### 4.4 DebtStrategist Agent
- [ ] Definir Signature DSPy
- [ ] Implementar estrategia avalanche
- [ ] Implementar proyección de pagos
- [ ] Implementar cálculo de intereses ahorrados
- [ ] Test: Plan de 10 meses

#### 4.5 StudyBalancer Agent
- [ ] Definir Signature DSPy
- [ ] Implementar rotación de temas
- [ ] Implementar detección de temas descuidados
- [ ] Implementar sugerencia basada en energía
- [ ] Test: Sugerencia balanceada

---

### Fase 5: Flujos Conversacionales (Día 21-25)

#### 5.1 Flujo: Captura Rápida
- [ ] Usuario envía mensaje
- [ ] Bot clasifica con InboxProcessor
- [ ] Si confianza >80%: confirma clasificación
- [ ] Si confianza 50-80%: pregunta específica
- [ ] Si confianza <50%: pide contexto
- [ ] Guardar en Notion

#### 5.2 Flujo: Deep Work
- [ ] Usuario inicia con `/deepwork [tarea]`
- [ ] Bot confirma bloque de tiempo
- [ ] Check-ins cada hora
- [ ] Si bloqueado: ofrecer opciones
- [ ] Al terminar: registrar tiempo real

#### 5.3 Flujo: Análisis de Compra
- [ ] Usuario menciona precio ($X)
- [ ] Bot detecta intención de compra
- [ ] Analiza con SpendingAnalyzer
- [ ] Muestra impacto en presupuesto/deuda
- [ ] Ofrece opciones: comprar/wishlist/skip

#### 5.4 Flujo: Registro de Gym
- [ ] Bot pregunta post-gym (o usuario inicia)
- [ ] Muestra ejercicios de última sesión
- [ ] Usuario actualiza pesos/reps
- [ ] Bot detecta PRs y progreso
- [ ] Guarda en Notion

#### 5.5 Flujo: Registro de Comidas
- [ ] Bot pregunta a las 21:00
- [ ] Usuario describe todo el día
- [ ] Bot parsea y analiza
- [ ] Muestra breakdown y evaluación
- [ ] Guarda en Notion

---

### Fase 6: Polish & Optimización (Día 26-30)

#### 6.1 Error Handling
- [ ] Implementar manejo global de errores
- [ ] Implementar retry con backoff
- [ ] Implementar fallbacks para API failures
- [ ] Logging estructurado
- [ ] Alertas de errores críticos

#### 6.2 Performance
- [ ] Implementar caching de Notion queries
- [ ] Optimizar prompts de DSPy
- [ ] Implementar rate limiting
- [ ] Profiling de endpoints lentos

#### 6.3 Métricas & Monitoring
- [ ] Implementar métricas de agents (accuracy, latency)
- [ ] Implementar métricas de uso
- [ ] Dashboard simple en Notion
- [ ] Health checks detallados

#### 6.4 Testing
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
*Última actualización: {{ fecha_actual }}*
