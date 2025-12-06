"""
Database V2 - PostgreSQL con asyncpg.

Fuente de verdad única, sin dependencia de Notion.
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
from sqlalchemy.pool import AsyncAdaptedQueuePool

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class Base(DeclarativeBase):
    """Base class para modelos SQLAlchemy."""
    pass


# Engine y session factory
_engine = None
_async_session_factory = None


async def _init_connection(connection):
    """Inicializa una conexión asyncpg con pgvector."""
    from pgvector.asyncpg import register_vector
    await register_vector(connection)


def get_engine():
    """Obtiene el engine de PostgreSQL."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            # Usar connect_args para configurar la inicialización de conexión
            connect_args={
                "server_settings": {"jit": "off"}  # Desactivar JIT para mejor compatibilidad
            }
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


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager para obtener una sesión con pgvector registrado."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            # Registrar pgvector en la conexión subyacente
            conn = await session.connection()
            raw_conn = await conn.get_raw_connection()
            await _init_connection(raw_conn.driver_connection)
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

    logger.info("Base de datos PostgreSQL inicializada")


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
