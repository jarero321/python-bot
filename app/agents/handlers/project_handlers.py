"""
Project Handlers - Proyectos y estudio.

Handlers para CRUD de proyectos y sesiones de estudio.
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
from app.services.notion import get_notion_service

logger = logging.getLogger(__name__)


def project_type_keyboard() -> InlineKeyboardMarkup:
    """Teclado para seleccionar tipo de proyecto."""
    keyboard = [
        [
            InlineKeyboardButton("💼 Trabajo", callback_data="project_type_trabajo"),
            InlineKeyboardButton("💰 Freelance", callback_data="project_type_freelance"),
        ],
        [
            InlineKeyboardButton("🏠 Personal", callback_data="project_type_personal"),
            InlineKeyboardButton("📚 Estudio", callback_data="project_type_estudio"),
        ],
        [
            InlineKeyboardButton("🚀 Side Project", callback_data="project_type_side_project"),
        ],
        [
            InlineKeyboardButton("❌ Cancelar", callback_data="project_cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


PROJECT_TYPE_LABELS = {
    "trabajo": "💼 Trabajo",
    "freelance": "💰 Freelance",
    "personal": "🏠 Personal",
    "estudio": "📚 Estudio/Aprendizaje",
    "side_project": "🚀 Side Project",
}


@intent_handler(UserIntent.PROJECT_CREATE)
class ProjectCreateHandler(BaseIntentHandler):
    """Handler para crear proyectos."""

    name = "ProjectCreateHandler"
    intents = [UserIntent.PROJECT_CREATE]

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
        project_type = entities.get("project_type", "")

        if not project_name:
            # Limpiar prefijos comunes
            cleaned = re.sub(
                r'^(crear|nuevo|iniciar)\s+(proyecto\s+)?',
                '',
                text,
                flags=re.IGNORECASE
            ).strip()
            project_name = cleaned[:50] if cleaned else text[:50]

        # Guardar en context
        context.user_data["pending_project_name"] = project_name
        context.user_data["pending_project_type"] = project_type

        if project_type:
            # Mostrar confirmación directa
            keyboard = confirm_keyboard(
                confirm_data="project_create",
                cancel_data="project_cancel",
                confirm_text="✅ Crear proyecto",
                cancel_text="❌ Cancelar",
            )

            message = (
                f"📁 <b>Nuevo Proyecto</b>\n\n"
                f"<b>Nombre:</b> {project_name}\n"
                f"<b>Tipo detectado:</b> {PROJECT_TYPE_LABELS.get(project_type, project_type)}\n"
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

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        notion = get_notion_service()
        projects = await notion.get_projects(active_only=True)

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
            props = project.get("properties", {})
            title_prop = props.get("Proyecto", {}).get("title", [])
            title = (
                title_prop[0].get("text", {}).get("content", "Sin nombre")
                if title_prop
                else "Sin nombre"
            )

            tipo = props.get("Tipo", {}).get("select", {}).get("name", "")
            progreso = props.get("Progreso", {}).get("number", 0) or 0

            tipo_emoji = {
                "Trabajo": "💼",
                "Freelance": "💰",
                "Personal": "🏠",
                "Estudio": "📚",
                "Side Project": "🚀",
            }.get(tipo, "📁")

            # Barra de progreso
            filled = int(progreso / 10)
            bar = "▓" * filled + "░" * (10 - filled)

            msg += f"{tipo_emoji} <b>{title}</b>\n"
            msg += f"   {bar} {progreso}%\n\n"

        return HandlerResponse(message=msg)


@intent_handler(UserIntent.PROJECT_UPDATE)
class ProjectUpdateHandler(BaseIntentHandler):
    """Handler para actualizar proyectos."""

    name = "ProjectUpdateHandler"
    intents = [UserIntent.PROJECT_UPDATE]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        entities = self.get_entities(intent_result)
        text = self.get_raw_message(intent_result)

        project_name = entities.get("project_name", text)
        notion = get_notion_service()

        projects = await notion.get_projects(active_only=True)
        matching_projects = []

        for project in projects:
            props = project.get("properties", {})
            title_prop = props.get("Proyecto", {}).get("title", [])
            title = (
                title_prop[0].get("text", {}).get("content", "")
                if title_prop
                else ""
            )

            if project_name.lower() in title.lower() or title.lower() in project_name.lower():
                matching_projects.append({
                    "id": project.get("id"),
                    "title": title,
                })

        if matching_projects:
            keyboard = []
            for proj in matching_projects[:5]:
                short_id = proj["id"][:8]
                keyboard.append([
                    InlineKeyboardButton(
                        f"✏️ {proj['title'][:30]}",
                        callback_data=f"project_edit:{short_id}",
                    ),
                ])
            keyboard.append([
                InlineKeyboardButton(
                    "❌ Cancelar",
                    callback_data="project_update_cancel",
                ),
            ])

            context.user_data["pending_edit_projects"] = matching_projects

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

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        entities = self.get_entities(intent_result)
        text = self.get_raw_message(intent_result)

        project_name = entities.get("project_name", text)
        notion = get_notion_service()

        projects = await notion.get_projects(active_only=True)
        matching_projects = []

        for project in projects:
            props = project.get("properties", {})
            title_prop = props.get("Proyecto", {}).get("title", [])
            title = (
                title_prop[0].get("text", {}).get("content", "")
                if title_prop
                else ""
            )

            if project_name.lower() in title.lower():
                matching_projects.append({
                    "id": project.get("id"),
                    "title": title,
                })

        if matching_projects:
            keyboard = []
            for proj in matching_projects[:5]:
                short_id = proj["id"][:8]
                keyboard.append([
                    InlineKeyboardButton(
                        f"🏁 Completar {proj['title'][:25]}",
                        callback_data=f"project_complete:{short_id}",
                    ),
                ])
                keyboard.append([
                    InlineKeyboardButton(
                        f"❌ Cancelar {proj['title'][:25]}",
                        callback_data=f"project_cancel_proj:{short_id}",
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
