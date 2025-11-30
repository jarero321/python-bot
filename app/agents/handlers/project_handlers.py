"""
Project Handlers - Proyectos y estudio.

Handlers para CRUD de proyectos y sesiones de estudio.
Usan repositorios del dominio en lugar de NotionService directamente.
"""

import re
import logging
from typing import Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.agents.intent_router import UserIntent
from app.bot.keyboards import confirm_keyboard
from app.core.routing import (
    BaseIntentHandler,
    HandlerResponse,
    intent_handler,
)
from app.domain.repositories import get_project_repository, IProjectRepository
from app.domain.entities.project import Project, ProjectType, ProjectStatus

logger = logging.getLogger(__name__)


# ==================== Helpers ====================

def project_type_keyboard() -> InlineKeyboardMarkup:
    """Teclado para seleccionar tipo de proyecto."""
    keyboard = [
        [
            InlineKeyboardButton("💼 Trabajo", callback_data="project_type:work"),
            InlineKeyboardButton("💰 Freelance", callback_data="project_type:freelance"),
        ],
        [
            InlineKeyboardButton("🏠 Personal", callback_data="project_type:personal"),
            InlineKeyboardButton("📚 Estudio", callback_data="project_type:learning"),
        ],
        [
            InlineKeyboardButton("🚀 Side Project", callback_data="project_type:side_project"),
        ],
        [
            InlineKeyboardButton("❌ Cancelar", callback_data="project_cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


PROJECT_TYPE_LABELS = {
    ProjectType.WORK: "💼 Trabajo",
    ProjectType.FREELANCE: "💰 Freelance",
    ProjectType.PERSONAL: "🏠 Personal",
    ProjectType.LEARNING: "📚 Estudio/Aprendizaje",
    ProjectType.SIDE_PROJECT: "🚀 Side Project",
    ProjectType.HOBBY: "🎯 Hobby",
    ProjectType.FINANCIAL: "💳 Financiero",
    ProjectType.SEARCH: "🔍 Búsqueda",
}

PROJECT_STATUS_LABELS = {
    ProjectStatus.IDEA: "💡 Idea",
    ProjectStatus.PLANNING: "📝 Planificando",
    ProjectStatus.ACTIVE: "🟢 Activo",
    ProjectStatus.WAITING: "🟡 Esperando",
    ProjectStatus.PAUSED: "⏸️ Pausado",
    ProjectStatus.COMPLETED: "✅ Completado",
    ProjectStatus.CANCELLED: "❌ Cancelado",
}


def format_project_line(project: Project) -> str:
    """Formatea un proyecto para mostrar en lista."""
    type_emoji = PROJECT_TYPE_LABELS.get(project.type, "📁").split()[0]

    # Barra de progreso
    filled = int(project.progress / 10)
    bar = "▓" * filled + "░" * (10 - filled)

    overdue = " ⚠️" if project.is_overdue else ""

    return f"{type_emoji} <b>{project.name}</b>{overdue}\n   {bar} {project.progress}%"


def format_project_detail(project: Project) -> str:
    """Formatea detalles completos de un proyecto."""
    lines = [f"<b>{project.name}</b>"]

    lines.append(f"Tipo: {PROJECT_TYPE_LABELS.get(project.type, project.type.value)}")
    lines.append(f"Estado: {PROJECT_STATUS_LABELS.get(project.status, project.status.value)}")

    # Barra de progreso
    filled = int(project.progress / 10)
    bar = "▓" * filled + "░" * (10 - filled)
    lines.append(f"Progreso: {bar} {project.progress}%")

    if project.description:
        lines.append(f"\n📝 {project.description[:100]}")

    if project.target_date:
        days = project.days_until_target
        if days is not None:
            if days < 0:
                lines.append(f"\n⚠️ Vencido hace {abs(days)} días")
            elif days == 0:
                lines.append("\n📅 Target: Hoy")
            else:
                lines.append(f"\n📅 Target en {days} días")

    if project.total_tasks > 0:
        lines.append(f"📋 {project.completed_tasks}/{project.total_tasks} tareas")

    return "\n".join(lines)


# ==================== Handlers ====================

@intent_handler(UserIntent.PROJECT_CREATE)
class ProjectCreateHandler(BaseIntentHandler):
    """Handler para crear proyectos."""

    name = "ProjectCreateHandler"
    intents = [UserIntent.PROJECT_CREATE]

    def __init__(self, project_repo: IProjectRepository | None = None):
        super().__init__()
        self._project_repo = project_repo or get_project_repository()

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        entities = self.get_entities(intent_result)
        text = self.get_raw_message(intent_result)
        confidence = getattr(intent_result, "confidence", 0.5)

        project_name = entities.get("project_name", "")
        project_type_str = entities.get("project_type", "")

        if not project_name:
            # Limpiar prefijos comunes
            cleaned = re.sub(
                r'^(crear|nuevo|iniciar)\s+(proyecto\s+)?',
                '',
                text,
                flags=re.IGNORECASE
            ).strip()
            project_name = cleaned[:50] if cleaned else text[:50]

        # Mapear tipo de string a enum
        type_mapping = {
            "trabajo": ProjectType.WORK,
            "work": ProjectType.WORK,
            "freelance": ProjectType.FREELANCE,
            "personal": ProjectType.PERSONAL,
            "estudio": ProjectType.LEARNING,
            "learning": ProjectType.LEARNING,
            "side_project": ProjectType.SIDE_PROJECT,
            "hobby": ProjectType.HOBBY,
        }
        project_type = type_mapping.get(project_type_str.lower()) if project_type_str else None

        # Guardar en context
        context.user_data["pending_project"] = {
            "name": project_name,
            "type": project_type.value if project_type else None,
        }

        if project_type:
            # Mostrar confirmación directa
            keyboard = confirm_keyboard(
                confirm_data="project_create_confirm",
                cancel_data="project_cancel",
                confirm_text="✅ Crear proyecto",
                cancel_text="❌ Cancelar",
            )

            message = (
                f"📁 <b>Nuevo Proyecto</b>\n\n"
                f"<b>Nombre:</b> {project_name}\n"
                f"<b>Tipo:</b> {PROJECT_TYPE_LABELS.get(project_type, project_type.value)}\n"
                f"<b>Confianza:</b> {confidence:.0%}\n\n"
                f"¿Confirmar creación?"
            )

            return HandlerResponse(
                message=message,
                keyboard=keyboard,
            )

        # Preguntar tipo de proyecto
        return HandlerResponse(
            message=(
                f"📁 <b>Nuevo Proyecto</b>\n\n"
                f"<b>Nombre:</b> {project_name}\n\n"
                f"¿Qué tipo de proyecto es?"
            ),
            keyboard=project_type_keyboard(),
        )


@intent_handler(UserIntent.PROJECT_QUERY)
class ProjectQueryHandler(BaseIntentHandler):
    """Handler para consultar proyectos."""

    name = "ProjectQueryHandler"
    intents = [UserIntent.PROJECT_QUERY]

    def __init__(self, project_repo: IProjectRepository | None = None):
        super().__init__()
        self._project_repo = project_repo or get_project_repository()

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        # Obtener proyectos activos usando el repositorio
        projects = await self._project_repo.get_active()

        if not projects:
            return HandlerResponse(
                message=(
                    "📁 <b>Proyectos Activos</b>\n\n"
                    "No tienes proyectos activos.\n\n"
                    "Crea uno con: 'Nuevo proyecto [nombre]'"
                )
            )

        msg = "📁 <b>Proyectos Activos</b>\n\n"

        for project in projects[:10]:
            msg += format_project_line(project) + "\n\n"

        # Resumen
        total = len(projects)
        avg_progress = sum(p.progress for p in projects) / total if total > 0 else 0
        msg += f"📊 {total} proyectos | Progreso promedio: {avg_progress:.0f}%"

        return HandlerResponse(message=msg)


@intent_handler(UserIntent.PROJECT_UPDATE)
class ProjectUpdateHandler(BaseIntentHandler):
    """Handler para actualizar proyectos."""

    name = "ProjectUpdateHandler"
    intents = [UserIntent.PROJECT_UPDATE]

    def __init__(self, project_repo: IProjectRepository | None = None):
        super().__init__()
        self._project_repo = project_repo or get_project_repository()

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        entities = self.get_entities(intent_result)
        text = self.get_raw_message(intent_result)

        project_name = entities.get("project_name", text)

        # Buscar proyectos usando el repositorio
        projects = await self._project_repo.search_by_name(project_name)

        if projects:
            keyboard = []
            for proj in projects[:5]:
                keyboard.append([
                    InlineKeyboardButton(
                        f"✏️ {proj.name[:30]}",
                        callback_data=f"project_edit:{proj.id}",
                    ),
                ])
            keyboard.append([
                InlineKeyboardButton(
                    "❌ Cancelar",
                    callback_data="project_update_cancel",
                ),
            ])

            context.user_data["pending_edit_projects"] = [
                {"id": p.id, "name": p.name} for p in projects
            ]

            return HandlerResponse(
                message=(
                    f"📁 <b>Editar Proyecto</b>\n\n"
                    f"Selecciona el proyecto que quieres editar:"
                ),
                keyboard=InlineKeyboardMarkup(keyboard),
            )

        return HandlerResponse(
            message=(
                f"🔍 No encontré proyectos que coincidan con:\n"
                f"<i>{project_name[:50]}</i>\n\n"
                f"Usa /projects para ver tus proyectos."
            )
        )


@intent_handler(UserIntent.PROJECT_DELETE)
class ProjectDeleteHandler(BaseIntentHandler):
    """Handler para eliminar/cerrar proyectos."""

    name = "ProjectDeleteHandler"
    intents = [UserIntent.PROJECT_DELETE]

    def __init__(self, project_repo: IProjectRepository | None = None):
        super().__init__()
        self._project_repo = project_repo or get_project_repository()

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        entities = self.get_entities(intent_result)
        text = self.get_raw_message(intent_result)

        project_name = entities.get("project_name", text)

        # Buscar proyectos usando el repositorio
        projects = await self._project_repo.search_by_name(project_name)

        if projects:
            keyboard = []
            for proj in projects[:5]:
                keyboard.append([
                    InlineKeyboardButton(
                        f"🏁 Completar {proj.name[:25]}",
                        callback_data=f"project_complete:{proj.id}",
                    ),
                ])
                keyboard.append([
                    InlineKeyboardButton(
                        f"❌ Cancelar {proj.name[:25]}",
                        callback_data=f"project_cancel_proj:{proj.id}",
                    ),
                ])
            keyboard.append([
                InlineKeyboardButton(
                    "⬅️ Volver",
                    callback_data="project_delete_cancel",
                ),
            ])

            return HandlerResponse(
                message=(
                    f"📁 <b>Cerrar Proyecto</b>\n\n"
                    f"¿Qué quieres hacer con el proyecto?"
                ),
                keyboard=InlineKeyboardMarkup(keyboard),
            )

        return HandlerResponse(
            message=(
                f"🔍 No encontré proyectos que coincidan con:\n"
                f"<i>{project_name[:50]}</i>"
            )
        )


@intent_handler(UserIntent.STUDY_SESSION)
class StudySessionHandler(BaseIntentHandler):
    """Handler para iniciar sesiones de estudio."""

    name = "StudySessionHandler"
    intents = [UserIntent.STUDY_SESSION]

    def __init__(self, project_repo: IProjectRepository | None = None):
        super().__init__()
        self._project_repo = project_repo or get_project_repository()

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        entities = self.get_entities(intent_result)
        text = self.get_raw_message(intent_result)

        topic = entities.get("topic", text[:50])

        # Guardar en context
        context.user_data["study_topic"] = topic

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "⏱️ 25 min (Pomodoro)",
                    callback_data="study_time:25",
                ),
                InlineKeyboardButton(
                    "⏱️ 50 min",
                    callback_data="study_time:50",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⏱️ 90 min (Deep Work)",
                    callback_data="study_time:90",
                ),
            ],
            [
                InlineKeyboardButton(
                    "❌ Cancelar",
                    callback_data="study_cancel",
                ),
            ],
        ])

        message = (
            f"📚 <b>Sesión de Estudio</b>\n\n"
            f"<b>Tema:</b> {topic}\n\n"
            f"¿Cuánto tiempo quieres dedicarle?"
        )

        return HandlerResponse(
            message=message,
            keyboard=keyboard,
        )
