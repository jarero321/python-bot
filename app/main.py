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
from app.api.admin import router as admin_router
from app.config import get_settings
from app.utils.errors import CarlosCommandError, ErrorCategory, log_error
from app.utils.alerts import (
    send_startup_alert,
    send_shutdown_alert,
    alert_critical_error,
    send_health_alert,
)
from app.utils.metrics import metrics_middleware

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

    # Inicializar Core (LLM + Handlers + RAG)
    from app.core import initialize_core

    # RAG habilitado para búsqueda semántica y detección de duplicados
    await initialize_core(include_rag=True)
    logger.info("Core inicializado (LLM + Handlers + RAG)")

    # Inicializar Domain Services (TaskService, ProjectService)
    from app.domain.services import get_task_service, get_project_service

    task_service = get_task_service()
    await task_service.initialize()
    logger.info("TaskService inicializado con RAG")

    project_service = get_project_service()
    await project_service.initialize()
    logger.info("ProjectService inicializado")

    # Indexación automática de tareas y proyectos existentes
    try:
        from app.core.rag import get_vector_store, get_retriever

        vector_store = get_vector_store()
        retriever = get_retriever()

        # Solo reindexar si el índice está vacío
        if vector_store.count == 0:
            logger.info("Índice RAG vacío, iniciando indexación automática...")

            # Indexar tareas pendientes
            tasks_count = await task_service.reindex_all()
            logger.info(f"Indexadas {tasks_count} tareas")

            # Indexar proyectos activos
            projects = await project_service.get_active()
            for project in projects:
                try:
                    await retriever.index_project(project)
                except Exception as e:
                    logger.warning(f"Error indexando proyecto {project.name}: {e}")
            logger.info(f"Indexados {len(projects)} proyectos")

            logger.info(f"Indexación automática completada: {vector_store.count} documentos")
        else:
            logger.info(f"Índice RAG existente: {vector_store.count} documentos")

    except Exception as e:
        logger.warning(f"Error en indexación automática (no crítico): {e}")

    # Inicializar base de datos
    from app.db.database import init_db, close_db

    await init_db()
    logger.info("Base de datos inicializada")

    # Inicializar scheduler
    from app.scheduler.setup import setup_scheduler, shutdown_scheduler

    await setup_scheduler()
    logger.info("Scheduler inicializado")

    # Inicializar Telegram Bot Application
    from telegram.ext import Application
    from app.bot.handlers import setup_handlers

    telegram_app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .build()
    )
    setup_handlers(telegram_app)
    await telegram_app.initialize()
    logger.info("Telegram Bot inicializado")

    # Enviar alerta de inicio
    try:
        await send_startup_alert()
        logger.info("Alerta de inicio enviada")
    except Exception as e:
        logger.warning(f"No se pudo enviar alerta de inicio: {e}")

    yield

    # Enviar alerta de apagado
    try:
        await send_shutdown_alert("normal")
        logger.info("Alerta de apagado enviada")
    except Exception as e:
        logger.warning(f"No se pudo enviar alerta de apagado: {e}")

    # Shutdown Telegram
    await telegram_app.shutdown()

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


# Metrics middleware
app.middleware("http")(metrics_middleware)

# Routers
app.include_router(telegram_router)
app.include_router(admin_router)


# Middleware de manejo global de errores
@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    """Middleware para capturar errores no manejados."""
    try:
        response = await call_next(request)
        return response
    except CarlosCommandError as e:
        # Alertar errores críticos
        await alert_critical_error(
            e,
            f"request:{request.url.path}",
            e.category,
            {"path": request.url.path, "method": request.method},
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": e.category.value,
                "message": str(e),
                "path": request.url.path,
            },
        )
    except Exception as e:
        # Alertar errores no manejados
        await alert_critical_error(
            e,
            f"request:{request.url.path}",
            ErrorCategory.UNKNOWN,
            {"path": request.url.path, "method": request.method},
        )
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

    # Check RAG / Vector Store
    try:
        from app.core.rag import get_vector_store
        vector_store = get_vector_store()
        health["checks"]["rag"] = {
            "status": "healthy",
            "documents_indexed": vector_store.count,
        }
    except Exception as e:
        health["checks"]["rag"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    return health
