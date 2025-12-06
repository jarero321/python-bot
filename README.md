# Carlos Command - Brain V2

Asistente personal inteligente con arquitectura Brain unificada.

## Arquitectura

```
Usuario → Telegram → Brain (Gemini 2.0 Flash)
                          ↓
                    Tools Registry
                          ↓
               PostgreSQL + pgvector
```

### Componentes

| Componente | Tecnologia |
|------------|------------|
| Backend | FastAPI (Python 3.11+) |
| LLM | Google Gemini 2.0 Flash |
| Database | PostgreSQL + pgvector |
| Bot | python-telegram-bot |
| Scheduler | APScheduler (triggers) |
| Deployment | Docker + Docker Compose |

## Estructura

```
app/
├── main.py              # FastAPI app
├── config.py            # Configuracion
├── brain/               # Brain unificado
│   ├── core.py          # CarlosBrain
│   ├── memory.py        # Sistema de memoria
│   ├── tools.py         # Registry de herramientas
│   ├── prompts.py       # System prompts
│   └── embeddings.py    # Generacion de embeddings
├── bot/
│   └── handlers.py      # Telegram handlers
├── db/
│   ├── database.py      # PostgreSQL connection
│   └── models.py        # SQLAlchemy models
└── triggers/
    ├── scheduler.py     # APScheduler config
    └── handlers.py      # Trigger handlers
```

## Instalacion

### 1. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env`:

```env
# App
APP_ENV=development
DEBUG=true
LOG_LEVEL=INFO

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_WEBHOOK_URL=https://your-domain.com/telegram/webhook
TELEGRAM_CHAT_ID=your_chat_id

# Gemini
GEMINI_API_KEY=your_gemini_api_key

# PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=carlos_brain
POSTGRES_USER=carlos
POSTGRES_PASSWORD=your_password

# Timezone
TZ=America/Mexico_City
```

### 2. Iniciar con Docker

```bash
# Desarrollo (con ngrok)
docker-compose up --build

# Produccion
docker-compose -f docker-compose.prod.yml up -d
```

### 3. Configurar webhook

```bash
python scripts/setup_telegram_webhook.py
```

## Comandos del Bot

| Comando | Descripcion |
|---------|-------------|
| `/start` | Bienvenida |
| `/help` | Ayuda |
| `/today` | Tareas de hoy |
| `/plan` | Planificar dia |
| `/status` | Estado del sistema |

## Lenguaje Natural

El Brain entiende lenguaje natural:

- **Tareas**: "Crear tarea revisar el reporte"
- **Finanzas**: "Gaste $500 en comida"
- **Gym**: "Fui al gym, hice push"
- **Recordatorios**: "Recuerdame llamar al doctor en 2 horas"
- **Consultas**: "Que tareas tengo pendientes?"

## Triggers Programados

| Trigger | Horario | Descripcion |
|---------|---------|-------------|
| morning_briefing | 6:30 AM | Plan del dia |
| gym_check | 7:15/7:30/7:45 L-V | Recordatorio gym |
| hourly_pulse | 9-18h L-V | Check-in |
| evening_reflection | 9:00 PM | Reflexion |
| weekly_review | Domingo 10 AM | Resumen semanal |
| reminder_check | cada 2 min | Verificar reminders |
| deadline_check | 9 AM, 3 PM | Verificar deadlines |
| payday_alert | Dias 13, 28 | Alerta de quincena |

## API Endpoints

| Endpoint | Metodo | Descripcion |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/health/detailed` | GET | Health check detallado |
| `/telegram/webhook` | POST | Webhook Telegram |
| `/admin/triggers` | GET | Ver triggers |
| `/admin/trigger/{name}` | POST | Ejecutar trigger manual |

## Tools Disponibles

### Tareas
- `get_tasks_for_today` - Tareas de hoy
- `create_task` - Crear tarea
- `update_task_status` - Actualizar status
- `complete_task` - Completar tarea
- `search_tasks` - Buscar tareas
- `get_blocked_tasks` - Tareas bloqueadas

### Proyectos
- `get_active_projects` - Proyectos activos
- `get_project_tasks` - Tareas de proyecto

### Recordatorios
- `create_reminder` - Crear recordatorio
- `get_pending_reminders` - Reminders pendientes
- `snooze_reminder` - Posponer reminder

### Finanzas
- `log_expense` - Registrar gasto
- `get_spending_summary` - Resumen de gastos
- `get_debt_status` - Estado de deudas

### Salud
- `log_workout` - Registrar entrenamiento
- `get_workout_history` - Historial de gym
- `log_meal` - Registrar comida
- `check_gym_today` - Verificar gym hoy

## Persistencia de Datos

PostgreSQL usa un **volumen nombrado** de Docker:

```yaml
volumes:
  postgres_data:  # Volumen persistente
```

### Datos seguros con:
- `docker-compose down` - Contenedores se detienen, datos persisten
- `docker-compose up -d` - Datos siguen ahi
- Reinicio del servidor - Datos persisten

### Datos se pierden con:
- `docker volume rm postgres_data` - Elimina datos
- `docker-compose down -v` - El flag `-v` elimina volumenes

### Backup y Recuperacion

```bash
# Backup manual
./scripts/backup.sh

# Restaurar backup
./scripts/restore.sh /opt/backups/carlos-command/carlos_brain_20240115_030000.sql.gz
```

**Backup automatico con cron** (recomendado en produccion):
```bash
# Editar crontab
crontab -e

# Agregar linea (backup diario a las 3am)
0 3 * * * /opt/carlos-command/scripts/backup.sh >> /var/log/carlos-backup.log 2>&1
```

**Estrategia de backups:**
- Backups diarios automaticos
- Retencion de 7 dias (configurable con `RETENTION_DAYS`)
- Almacenados en `/opt/backups/carlos-command/`
- Comprimidos con gzip

**Para maxima seguridad**, copia los backups a otro servidor/cloud:
```bash
# Ejemplo: sync a S3
aws s3 sync /opt/backups/carlos-command/ s3://tu-bucket/backups/
```

### Migraciones (Alembic)

Las migraciones se ejecutan como servicio **one-shot** separado del app, no en cada restart.

```bash
# Ver estado de migraciones
docker exec carlos-command-app alembic current

# Ver historial
docker exec carlos-command-app alembic history

# Crear nueva migracion
alembic revision -m "add_new_column"

# Aplicar migraciones manualmente
docker-compose -f docker-compose.prod.yml run --rm migrations

# Revertir ultima migracion
docker exec carlos-command-app alembic downgrade -1
```

**Flujo para cambios de schema:**

1. Modifica `app/db/models.py`
2. Crea migracion: `alembic revision -m "descripcion"`
3. Edita el archivo generado en `alembic/versions/`
4. Commit y deploy con `./scripts/deploy.sh`

## Deploy Produccion

```bash
# Deploy completo (build + migraciones + app + webhook)
./scripts/deploy.sh
```

El script de deploy:
1. Valida variables de entorno
2. Build de imagenes
3. Inicia PostgreSQL y espera healthy
4. Ejecuta migraciones (one-shot, no se repite en restarts)
5. Inicia app y espera health check
6. Configura webhook de Telegram

**Importante**: Las migraciones solo corren durante el deploy, NO en cada restart del contenedor. Esto evita problemas de crash-loops.

## Estructura Docker

| Archivo | Uso |
|---------|-----|
| `docker-compose.yml` | Desarrollo (con ngrok) |
| `docker-compose.prod.yml` | Produccion |
| `start.sh` | Inicia desarrollo |
| `scripts/deploy.sh` | Deploy produccion seguro |

## Desarrollo

```bash
# Formatear
black app/

# Lint
ruff check app/
```

## Licencia

MIT
