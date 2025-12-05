# Carlos Command - AI Personal Assistant

Un sistema de gestión de vida personal potenciado por IA, accesible via Telegram.

## Descripción

Carlos Command es un bot de Telegram que actúa como un "Project Manager" personal, integrando:

- **Gestión de Tareas** - Captura, organización y seguimiento de tareas
- **Gestión de Proyectos** - Tracking de proyectos con progreso y deadlines
- **Salud y Fitness** - Registro de entrenamientos (rutina PPL) y nutrición
- **Finanzas Personales** - Análisis de gastos y estrategias de pago de deudas
- **Recordatorios Inteligentes** - Sistema proactivo con escalación
- **Planificación** - Morning briefings y revisiones semanales con IA

## Stack Tecnológico

| Componente | Tecnología |
|------------|------------|
| Backend | FastAPI (Python 3.11+) |
| AI/Agentes | DSPy + Google Gemini 2.0 Flash |
| Base de datos | Notion (8 DBs) + SQLite local |
| Bot | python-telegram-bot |
| Scheduling | APScheduler |
| Deployment | Docker + Docker Compose |

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                         Docker Container                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                      FastAPI App                          │  │
│  │                                                           │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │  │
│  │  │  Telegram   │  │ APScheduler │  │   DSPy Agents   │   │  │
│  │  │  Webhook    │  │   (Crons)   │  │  (18 agentes)   │   │  │
│  │  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘   │  │
│  │         │                │                   │            │  │
│  │         └────────────────┼───────────────────┘            │  │
│  │                          ▼                                │  │
│  │                  ┌───────────────┐                        │  │
│  │                  │   Services    │                        │  │
│  │                  │ Notion/SQLite │                        │  │
│  │                  └───────────────┘                        │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Requisitos

- Docker y Docker Compose
- Cuenta de Telegram con bot creado
- Notion API key con acceso a las bases de datos
- Google Gemini API key

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/your-username/carlos-command.git
cd carlos-command
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` con tus credenciales:

```env
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
DATABASE_URL=sqlite+aiosqlite:///data/carlos_command.db

# Timezone
TZ=America/Mexico_City
```

### 3. Iniciar con Docker

```bash
# Desarrollo
docker-compose up --build

# Producción
docker-compose -f docker-compose.prod.yml up -d
```

### 4. Configurar webhook de Telegram

```bash
python scripts/setup_telegram_webhook.py
```

## Estructura del Proyecto

```
carlos-command/
├── app/
│   ├── main.py                 # FastAPI app
│   ├── config.py               # Configuración
│   ├── agents/                 # 18 agentes DSPy
│   │   ├── orchestrator.py     # Coordinador principal
│   │   ├── intent_router.py    # Router de intenciones
│   │   ├── spending_analyzer.py
│   │   ├── morning_planner.py
│   │   └── ...
│   ├── bot/
│   │   ├── handlers.py         # Handlers de Telegram
│   │   ├── keyboards.py        # Teclados inline
│   │   └── conversations.py    # Flujos conversacionales
│   ├── services/
│   │   ├── notion.py           # Cliente de Notion
│   │   └── telegram.py         # Cliente de Telegram
│   ├── scheduler/
│   │   ├── setup.py            # Configuración APScheduler
│   │   └── jobs/               # Jobs programados
│   ├── domain/
│   │   ├── entities/           # Modelos de dominio
│   │   ├── repositories/       # Repositorios
│   │   └── services/           # Servicios de dominio
│   ├── core/
│   │   ├── llm/                # Proveedor LLM
│   │   ├── rag/                # Sistema RAG
│   │   └── routing/            # Sistema de routing
│   ├── db/
│   │   ├── database.py         # Conexión SQLite
│   │   └── models.py           # Modelos SQLAlchemy
│   └── utils/
│       ├── errors.py           # Manejo de errores
│       ├── alerts.py           # Sistema de alertas
│       └── metrics.py          # Métricas y profiling
├── tests/
│   ├── test_agents/
│   ├── test_services/
│   ├── test_handlers/
│   └── test_scheduler/
├── scripts/                    # Utilidades
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Comandos del Bot

| Comando | Descripción |
|---------|-------------|
| `/start` | Bienvenida e inicialización |
| `/help` | Ayuda y comandos disponibles |
| `/status` | Estado del sistema |
| `/today` | Tareas de hoy |
| `/add [tarea]` | Agregar tarea rápida |
| `/doing` | Marcar tarea en progreso |
| `/done` | Completar tarea actual |
| `/projects` | Ver proyectos activos |
| `/gym` | Registrar entrenamiento |
| `/food` | Registrar comida |
| `/deepwork` | Iniciar sesión de deep work |

## Flujos Conversacionales

El bot entiende lenguaje natural:

- **Tareas**: "Crear tarea: revisar el reporte"
- **Compras**: "Quiero comprar unos AirPods por $3000" → Análisis de impacto
- **Gym**: "Fui al gym, hice pecho: banca 60kg 3x8"
- **Recordatorios**: "Recuérdame llamar al doctor en 2 horas"
- **Planificación**: "¿Qué hago mañana?"
- **Deudas**: "¿Cuánto debo en total?"

## Jobs Programados

| Job | Horario | Descripción |
|-----|---------|-------------|
| Morning Briefing | 6:30 AM | Plan del día con IA |
| Hourly Check-in | 9-18h L-V | Verificación de progreso |
| Gym Reminders | 7:15/7:30/7:45 | Escalación de gym |
| Nutrition Reminder | 9:00 PM | Registro de comidas |
| Weekly Review | Domingo 10 AM | Resumen semanal |
| Pre-Payday | Días 13, 28 | Planificación financiera |

## API Endpoints

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/health` | GET | Health check básico |
| `/health/detailed` | GET | Health check con servicios |
| `/webhook/telegram` | POST | Webhook de Telegram |
| `/admin/reindex` | POST | Reindexar RAG |
| `/admin/metrics` | GET | Ver métricas |
| `/admin/stats` | GET | Estadísticas del sistema |

## Desarrollo

### Ejecutar tests

```bash
# Todos los tests
pytest

# Con coverage
pytest --cov=app --cov-report=html

# Tests específicos
pytest tests/test_agents/
pytest tests/test_services/
```

### Lint y formato

```bash
# Formatear código
black app/

# Lint
ruff check app/
```

## Bases de Datos de Notion

El sistema usa 8 bases de datos en Notion:

1. **Inbox** - Captura rápida
2. **Tasks** - Tareas con estados (Backlog → Today → Doing → Done)
3. **Projects** - Proyectos (Work, Freelance, Learning, Personal)
4. **Knowledge** - Base de conocimiento personal
5. **Daily Nutrition** - Registro de comidas
6. **Workouts** - Entrenamientos (rutina PPL)
7. **Transactions** - Gastos e ingresos
8. **Debts** - Deudas activas

## Contribuir

1. Fork el repositorio
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## Licencia

MIT

## Autor

Carlos - [@carlos](https://github.com/carlos)

---

*Desarrollado con IA usando Claude + DSPy + Gemini*
