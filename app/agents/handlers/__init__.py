"""
Intent Handlers - Handlers modulares para cada tipo de intent.

Este módulo contiene handlers separados por dominio que reemplazan
los 30+ if/elif en handlers.py.

Estructura:
    - general_handlers: Greeting, Help, Status
    - task_handlers: Task CRUD
    - planning_handlers: Planificación y priorización
    - finance_handlers: Gastos y deudas
    - fitness_handlers: Gym y nutrición
    - project_handlers: Proyectos y estudio
    - capture_handlers: Ideas y notas
"""

from app.agents.handlers.general_handlers import (
    GreetingHandler,
    HelpHandler,
    StatusHandler,
)
from app.agents.handlers.task_handlers import (
    TaskCreateHandler,
    TaskQueryHandler,
    TaskUpdateHandler,
    TaskDeleteHandler,
)
from app.agents.handlers.planning_handlers import (
    PlanTomorrowHandler,
    PlanWeekHandler,
    WorkloadCheckHandler,
    PrioritizeHandler,
    RescheduleHandler,
    ReminderCreateHandler,
    ReminderQueryHandler,
)
from app.agents.handlers.finance_handlers import (
    ExpenseAnalyzeHandler,
    ExpenseLogHandler,
    DebtQueryHandler,
)
from app.agents.handlers.fitness_handlers import (
    GymLogHandler,
    GymQueryHandler,
    NutritionLogHandler,
    NutritionQueryHandler,
)
from app.agents.handlers.project_handlers import (
    ProjectCreateHandler,
    ProjectQueryHandler,
    ProjectUpdateHandler,
    ProjectDeleteHandler,
    StudySessionHandler,
)
from app.agents.handlers.capture_handlers import (
    IdeaHandler,
    NoteHandler,
    UnknownHandler,
    FallbackHandler,
    setup_fallback_handler,
)

__all__ = [
    # General
    "GreetingHandler",
    "HelpHandler",
    "StatusHandler",
    # Tasks
    "TaskCreateHandler",
    "TaskQueryHandler",
    "TaskUpdateHandler",
    "TaskDeleteHandler",
    # Planning
    "PlanTomorrowHandler",
    "PlanWeekHandler",
    "WorkloadCheckHandler",
    "PrioritizeHandler",
    "RescheduleHandler",
    "ReminderCreateHandler",
    "ReminderQueryHandler",
    # Finance
    "ExpenseAnalyzeHandler",
    "ExpenseLogHandler",
    "DebtQueryHandler",
    # Fitness
    "GymLogHandler",
    "GymQueryHandler",
    "NutritionLogHandler",
    "NutritionQueryHandler",
    # Projects
    "ProjectCreateHandler",
    "ProjectQueryHandler",
    "ProjectUpdateHandler",
    "ProjectDeleteHandler",
    "StudySessionHandler",
    # Capture
    "IdeaHandler",
    "NoteHandler",
    "UnknownHandler",
    "FallbackHandler",
    "setup_fallback_handler",
]


def register_all_handlers() -> None:
    """
    Registra todos los handlers en el registry.

    Llamar esta función al inicio de la aplicación para
    que todos los handlers estén disponibles.
    """
    import logging
    logger = logging.getLogger(__name__)

    # Los handlers se auto-registran via decoradores al importarse
    # Importar cada módulo para trigger el registro
    from app.agents.handlers import general_handlers  # noqa: F401
    from app.agents.handlers import task_handlers  # noqa: F401
    from app.agents.handlers import planning_handlers  # noqa: F401
    from app.agents.handlers import finance_handlers  # noqa: F401
    from app.agents.handlers import fitness_handlers  # noqa: F401
    from app.agents.handlers import project_handlers  # noqa: F401
    from app.agents.handlers import capture_handlers  # noqa: F401

    # Configurar fallback handler
    setup_fallback_handler()

    from app.core.routing import get_handler_registry
    registry = get_handler_registry()

    # Log handlers registrados
    logger.info(f"Handlers registrados: {registry.handler_count}")
    logger.debug(f"Handlers: {registry.list_handlers()}")
