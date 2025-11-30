"""Carlos Command - FastAPI Application."""

import logging
import sys
import traceback
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.telegram_webhook import router as telegram_router
from app.config import get_settings
from app.utils.errors import CarlosCommandError, ErrorCategory, log_error

settings = get_settings()


def setup_logging() -> None:
    """Configura el logging estructurado."""
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Reducir ruido de librerías externas
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Maneja el ciclo de vida de la aplicación."""
    setup_logging()
    logger.info("Iniciando Carlos Command...")
    logger.info(f"Entorno: {settings.app_env}")
    logger.info(f"Debug: {settings.debug}")

    # Inicializar Core (LLM + Handlers + RAG opcional)
    from app.core import initialize_core

    # RAG deshabilitado por defecto para arranque rápido
    # Habilitar con: await initialize_core(include_rag=True)
    await initialize_core(include_rag=False)
    logger.info("Core inicializado (LLM + Handlers)")

    # Inicializar base de datos
    from app.db.database import init_db, close_db

    await init_db()
    logger.info("Base de datos inicializada")

    # Inicializar scheduler
    from app.scheduler.setup import setup_scheduler, shutdown_scheduler

    await setup_scheduler()
    logger.info("Scheduler inicializado")

    yield

    # Detener scheduler
    await shutdown_scheduler()

    # Cerrar conexiones
    await close_db()
    logger.info("Cerrando Carlos Command...")


app = FastAPI(
    title="Carlos Command",
    description="Bot de Telegram con AI agents para gestión integral de vida",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Routers
app.include_router(telegram_router)


# Middleware de manejo global de errores
@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    """Middleware para capturar errores no manejados."""
    try:
        response = await call_next(request)
        return response
    except CarlosCommandError as e:
        log_error(e, f"request:{request.url.path}", e.category)
        return JSONResponse(
            status_code=500,
            content={
                "error": e.category.value,
                "message": str(e),
                "path": request.url.path,
            },
        )
    except Exception as e:
        log_error(e, f"request:{request.url.path}", ErrorCategory.UNKNOWN)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": "Error interno del servidor",
                "path": request.url.path,
            },
        )


@app.get("/health")
async def health_check():
    """Health check básico."""
    return {
        "status": "healthy",
        "service": "carlos-command",
        "version": "0.1.0",
        "environment": settings.app_env,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/health/detailed")
async def health_check_detailed():
    """Health check detallado con estado de servicios."""
    from app.services.notion import get_notion_service
    from app.scheduler.setup import get_scheduler, get_job_status
    from app.utils.cache import get_cache

    health = {
        "status": "healthy",
        "service": "carlos-command",
        "version": "0.1.0",
        "environment": settings.app_env,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {},
    }

    # Check Notion
    try:
        notion = get_notion_service()
        notion_ok = await notion.test_connection()
        health["checks"]["notion"] = {
            "status": "healthy" if notion_ok else "unhealthy",
            "latency_ms": None,  # TODO: medir latencia
        }
    except Exception as e:
        health["checks"]["notion"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health["status"] = "degraded"

    # Check Scheduler
    try:
        scheduler = get_scheduler()
        jobs = get_job_status()
        health["checks"]["scheduler"] = {
            "status": "healthy" if scheduler.running else "unhealthy",
            "running": scheduler.running,
            "jobs_count": len(jobs),
            "jobs": jobs[:5],  # Solo primeros 5
        }
    except Exception as e:
        health["checks"]["scheduler"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health["status"] = "degraded"

    # Check Cache
    try:
        cache = get_cache()
        cache_stats = cache.get_stats()
        health["checks"]["cache"] = {
            "status": "healthy",
            **cache_stats,
        }
    except Exception as e:
        health["checks"]["cache"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    return health
