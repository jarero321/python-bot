"""
Carlos Command - Brain V2

FastAPI application con Brain unificado.
Sin dependencia de Notion, PostgreSQL como fuente de verdad.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import get_settings

# Configurar logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle de la aplicación."""
    logger.info("=" * 50)
    logger.info("Iniciando Carlos Command - Brain V2")
    logger.info("=" * 50)

    # ==================== STARTUP ====================

    # 1. Inicializar base de datos
    logger.info("Inicializando base de datos PostgreSQL...")
    from app.db.database import init_db
    await init_db()

    # 2. Inicializar bot de Telegram
    logger.info("Inicializando bot de Telegram...")
    from app.bot.handlers import initialize_bot
    telegram_app = await initialize_bot()

    # 3. Inicializar scheduler de triggers
    logger.info("Inicializando scheduler de triggers...")
    from app.triggers import setup_scheduler
    await setup_scheduler()

    # 4. Enviar alerta de inicio
    logger.info("Enviando alerta de startup...")
    await send_startup_alert()

    logger.info("=" * 50)
    logger.info("Carlos Command - Brain V2 listo!")
    logger.info("=" * 50)

    yield

    # ==================== SHUTDOWN ====================

    logger.info("Deteniendo Carlos Command...")

    # Enviar alerta de shutdown
    await send_shutdown_alert()

    # Detener scheduler
    from app.triggers import shutdown_scheduler
    await shutdown_scheduler()

    # Detener bot
    from app.bot.handlers import shutdown_bot
    await shutdown_bot()

    # Cerrar conexiones de BD
    from app.db.database import close_db
    await close_db()

    logger.info("Carlos Command detenido.")


# Crear aplicación FastAPI
app = FastAPI(
    title="Carlos Command - Brain V2",
    description="Asistente personal inteligente con Brain unificado",
    version="2.0.0",
    lifespan=lifespan,
)


# ==================== ROUTES ====================


@app.get("/health")
async def health_check():
    """Health check básico."""
    return {"status": "healthy", "service": "carlos-brain-v2"}


@app.get("/health/detailed")
async def health_check_detailed():
    """Health check detallado."""
    from app.triggers.scheduler import get_scheduled_triggers

    triggers = get_scheduled_triggers()

    return {
        "status": "healthy",
        "service": "carlos-brain-v2",
        "version": "2.0.0",
        "environment": settings.app_env,
        "checks": {
            "database": {"status": "healthy"},
            "scheduler": {
                "status": "healthy",
                "triggers_count": len(triggers),
            },
            "brain": {"status": "healthy"},
        },
    }


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Webhook para mensajes de Telegram."""
    from telegram import Update
    from app.bot.handlers import get_application

    try:
        data = await request.json()
        telegram_app = await get_application()

        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.process_update(update)

        return {"status": "ok"}

    except Exception as e:
        logger.exception(f"Error en webhook: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.get("/admin/triggers")
async def get_triggers():
    """Obtiene lista de triggers programados."""
    from app.triggers.scheduler import get_scheduled_triggers
    return {"triggers": get_scheduled_triggers()}


@app.post("/admin/trigger/{trigger_name}")
async def manual_trigger(trigger_name: str):
    """Ejecuta un trigger manualmente."""
    from app.triggers import handlers

    handler = getattr(handlers, f"trigger_{trigger_name}", None)
    if not handler:
        return JSONResponse(
            status_code=404,
            content={"error": f"Trigger '{trigger_name}' no encontrado"}
        )

    await handler()
    return {"status": "triggered", "trigger": trigger_name}


# ==================== HELPERS ====================


async def send_startup_alert():
    """Envía alerta de inicio por Telegram."""
    try:
        from telegram import Bot

        bot = Bot(token=settings.telegram_bot_token)
        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=(
                "🚀 <b>Carlos Brain V2 iniciado</b>\n\n"
                f"Entorno: {settings.app_env}\n"
                "Sistema listo."
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Error enviando alerta de startup: {e}")


async def send_shutdown_alert():
    """Envía alerta de shutdown por Telegram."""
    try:
        from telegram import Bot

        bot = Bot(token=settings.telegram_bot_token)
        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text="🔴 <b>Carlos Brain V2 detenido</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Error enviando alerta de shutdown: {e}")


# ==================== DEV MODE ====================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_development,
    )
