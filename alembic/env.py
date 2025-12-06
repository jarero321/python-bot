"""
Alembic Environment Configuration.

Lee la URL de la base de datos desde las variables de entorno
y configura las migraciones para trabajar con SQLAlchemy.
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Agregar el directorio raiz al path para importar app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings
from app.db.database import Base
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

# Alembic Config object
config = context.config

# Logging configuration
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata de los modelos para autogenerate
target_metadata = Base.metadata

# Obtener URL de la base de datos
settings = get_settings()

def get_url():
    """Obtiene la URL de conexion sincrona para Alembic."""
    return (
        f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Genera SQL sin conectar a la base de datos.
    Util para revisar que hara una migracion.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    Conecta a la base de datos y aplica las migraciones.
    """
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
