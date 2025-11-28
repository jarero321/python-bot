"""Configuración de la base de datos SQLite."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class Base(DeclarativeBase):
    """Clase base para los modelos de SQLAlchemy."""

    pass


# Asegurar que el directorio de datos existe
db_path = Path(settings.database_url.replace("sqlite+aiosqlite:///", ""))
db_path.parent.mkdir(parents=True, exist_ok=True)

# Motor de base de datos async
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)

# Session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@asynccontextmanager
async def get_session():
    """Context manager para obtener una sesión de base de datos."""
    session = async_session_factory()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Error en sesión de DB: {e}")
        raise
    finally:
        await session.close()


async def init_db():
    """Inicializa la base de datos creando todas las tablas."""
    from app.db.models import Base  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Base de datos inicializada")


async def close_db():
    """Cierra las conexiones de la base de datos."""
    await engine.dispose()
    logger.info("Conexiones de base de datos cerradas")
