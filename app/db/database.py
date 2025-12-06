"""
Database V2 - PostgreSQL con psycopg3.

Fuente de verdad única, sin dependencia de Notion.
psycopg3 tiene mejor soporte nativo para pgvector.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class Base(DeclarativeBase):
    """Base class para modelos SQLAlchemy."""
    pass


# Engine y session factory
_engine = None
_async_session_factory = None
_pgvector_registered = False


def get_engine():
    """Obtiene el engine de PostgreSQL con psycopg3."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory():
    """Obtiene la factory de sesiones."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


async def _register_pgvector_types():
    """Registra los tipos de pgvector globalmente para psycopg3."""
    global _pgvector_registered
    if _pgvector_registered:
        return

    try:
        import psycopg
        from pgvector.psycopg import register_vector_async

        # Obtener una conexión para registrar los tipos
        engine = get_engine()
        async with engine.connect() as conn:
            raw_conn = await conn.get_raw_connection()
            await register_vector_async(raw_conn.dbapi_connection)

        _pgvector_registered = True
        logger.info("pgvector registrado correctamente con psycopg3")
    except Exception as e:
        logger.warning(f"No se pudo registrar pgvector: {e}")


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager para obtener una sesión."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Inicializa la base de datos."""
    logger.info(f"Conectando a PostgreSQL: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")

    # Importar modelos para que se registren
    from app.db.models import (
        UserProfileModel,
        ProjectModel,
        TaskModel,
        ReminderModel,
        TransactionModel,
        DebtModel,
        WorkoutModel,
        NutritionLogModel,
        ConversationHistoryModel,
        WorkingMemoryModel,
        LearnedPatternModel,
        BrainMetricModel,
        TriggerLogModel,
    )

    engine = get_engine()

    # En desarrollo, crear tablas automáticamente
    # En producción, usar migraciones
    if settings.is_development:
        async with engine.begin() as conn:
            # await conn.run_sync(Base.metadata.drop_all)  # Descomentar para reset
            await conn.run_sync(Base.metadata.create_all)

    # Registrar tipos pgvector para psycopg3
    await _register_pgvector_types()

    logger.info("Base de datos PostgreSQL inicializada con pgvector")


async def close_db() -> None:
    """Cierra las conexiones de la base de datos."""
    global _engine, _async_session_factory

    if _engine:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None

    logger.info("Conexiones de base de datos cerradas")


async def check_db_connection() -> bool:
    """Verifica la conexión a la base de datos."""
    try:
        async with get_session() as session:
            await session.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Error conectando a la base de datos: {e}")
        return False
