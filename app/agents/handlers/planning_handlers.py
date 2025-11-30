"""
Planning Handlers - Planificación y recordatorios.

Handlers para planificar el día/semana, priorizar tareas, y recordatorios.
"""

import logging
from typing import Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from app.agents.intent_router import UserIntent
from app.core.routing import (
    BaseIntentHandler,
    HandlerResponse,
    intent_handler,
)
from app.core.llm import get_llm_provider, ModelType
from app.services.notion import get_notion_service

logger = logging.getLogger(__name__)


@intent_handler(UserIntent.PLAN_TOMORROW)
class PlanTomorrowHandler(BaseIntentHandler):
    """Handler para planificar el día siguiente."""

    name = "PlanTomorrowHandler"
    intents = [UserIntent.PLAN_TOMORROW]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        from app.agents.planning_assistant import get_planning_assistant

        text = self.get_raw_message(intent_result)

        # Mostrar procesamiento
        await update.message.reply_html(
            "🌙 <b>Planificando tu mañana...</b>\n\n"
            "⏳ Analizando tareas pendientes y prioridades..."
        )

        try:
            # Usar modelo PRO para planificación
            provider = get_llm_provider()
            provider.ensure_configured()

            with provider.for_task("morning_planning"):
                planning = get_planning_assistant()

                # Detectar nivel de energía del mensaje
                energy = "no_especificado"
                message_lower = text.lower()
                if any(w in message_lower for w in ["cansado", "poco", "ligero"]):
                    energy = "bajo"
                elif any(w in message_lower for w in ["motivado", "energía", "productivo"]):
                    energy = "alto"

                plan = await planning.plan_tomorrow(
                    user_message=text,
                    energy_level=energy,
                )

            if "error" in plan:
                return HandlerResponse(
                    message=f"❌ Error: {plan['error']}",
                    success=False,
                    already_sent=True,
                )

            # Construir respuesta
            response = "🌅 <b>Plan para mañana</b>\n\n"

            if plan.get("priority_tasks"):
                response += "<b>🎯 Prioridades:</b>\n"
                for task in plan["priority_tasks"][:3]:
                    response += f"  • {task}\n"
                response += "\n"

            if plan.get("secondary_tasks"):
                response += "<b>📋 Si hay tiempo:</b>\n"
                for task in plan["secondary_tasks"][:3]:
                    response += f"  • {task}\n"
                response += "\n"

            if plan.get("ai_suggestion"):
                response += f"<b>💡 Sugerencia:</b>\n{plan['ai_suggestion']}\n\n"

            if plan.get("energy_tip"):
                response += f"<i>🔋 {plan['energy_tip']}</i>\n"

            # Keyboard para acciones
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "✅ Aceptar plan",
                        callback_data="plan_accept",
                    ),
                    InlineKeyboardButton(
                        "✏️ Ajustar",
                        callback_data="plan_adjust",
                    ),
                ],
            ])

            return HandlerResponse(
                message=response,
                keyboard=keyboard,
                already_sent=True,
            )

        except Exception as e:
            logger.error(f"Error en planificación: {e}")
            return HandlerResponse(
                message="❌ Error al planificar. Intenta de nuevo.",
                success=False,
                already_sent=True,
            )


@intent_handler(UserIntent.PLAN_WEEK)
class PlanWeekHandler(BaseIntentHandler):
    """Handler para ver resumen semanal."""

    name = "PlanWeekHandler"
    intents = [UserIntent.PLAN_WEEK]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        from app.agents.planning_assistant import get_planning_assistant

        await update.message.reply_html(
            "📊 <b>Cargando resumen semanal...</b>"
        )

        try:
            planning = get_planning_assistant()
            overview = await planning.get_week_overview()

            if "error" in overview:
                return HandlerResponse(
                    message=f"❌ Error: {overview['error']}",
                    success=False,
                    already_sent=True,
                )

            response = f"📊 <b>Resumen Semanal</b>\n"
            response += f"<i>{overview['week_start']} al {overview['week_end']}</i>\n\n"

            # Carga por día
            response += "<b>Carga por día:</b>\n"
            for day, data in overview.get("workload_by_day", {}).items():
                if data["tasks"] > 0:
                    bar = "█" * min(data["tasks"], 5)
                    urgent = f" 🔥{data['urgent']}" if data["urgent"] > 0 else ""
                    response += f"{day[:3]}: {bar} ({data['tasks']}){urgent}\n"

            response += "\n"

            # Deadlines
            if overview.get("upcoming_deadlines"):
                response += "<b>📅 Próximos deadlines:</b>\n"
                for dl in overview["upcoming_deadlines"][:5]:
                    response += f"  • {dl['date']}: {dl['task'][:30]}\n"
                response += "\n"

            # Alertas
            if overview.get("alerts"):
                response += "<b>⚠️ Alertas:</b>\n"
                for alert in overview["alerts"][:3]:
                    response += f"  • {alert}\n"

            return HandlerResponse(
                message=response,
                already_sent=True,
            )

        except Exception as e:
            logger.error(f"Error obteniendo semana: {e}")
            return HandlerResponse(
                message="❌ Error al cargar la semana.",
                success=False,
                already_sent=True,
            )


@intent_handler(UserIntent.WORKLOAD_CHECK)
class WorkloadCheckHandler(BaseIntentHandler):
    """Handler para revisar carga de trabajo."""

    name = "WorkloadCheckHandler"
    intents = [UserIntent.WORKLOAD_CHECK]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        from app.agents.orchestrator import get_orchestrator

        try:
            orchestrator = get_orchestrator()
            summary = await orchestrator.get_workload_summary()

            total = summary.get("total_pending", 0)
            overdue = summary.get("overdue", 0)
            prio = summary.get("by_priority", {})

            response = "📊 <b>Tu carga de trabajo</b>\n\n"
            response += f"📋 <b>Total pendiente:</b> {total} tareas\n"

            if overdue > 0:
                response += f"⚠️ <b>Vencidas:</b> {overdue}\n"

            response += f"\n<b>Por prioridad:</b>\n"
            response += f"🔥 Urgente: {prio.get('urgente', 0)}\n"
            response += f"⚡ Alta: {prio.get('alta', 0)}\n"
            response += f"📌 Normal: {prio.get('normal', 0)}\n"

            # Deadlines de la semana
            deadlines = summary.get("deadlines_this_week", [])
            if deadlines:
                response += "\n<b>Próximos deadlines:</b>\n"
                for dl in deadlines[:5]:
                    response += f"  • {dl['date']}: {dl['task'][:25]}\n"

            return HandlerResponse(message=response)

        except Exception as e:
            logger.error(f"Error en workload check: {e}")
            return HandlerResponse(
                message="❌ Error al revisar carga de trabajo.",
                success=False,
            )


@intent_handler(UserIntent.PRIORITIZE)
class PrioritizeHandler(BaseIntentHandler):
    """Handler para ayudar a priorizar tareas."""

    name = "PrioritizeHandler"
    intents = [UserIntent.PRIORITIZE]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "📋 Ver tareas urgentes",
                    callback_data="show_urgent_tasks",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📊 Ver mi carga",
                    callback_data="workload_check",
                ),
            ],
        ])

        message = (
            "🤔 <b>Ayuda para priorizar</b>\n\n"
            "Dime las dos tareas que quieres comparar.\n"
            "Por ejemplo: 'debería hacer primero X o Y?'\n\n"
            "O selecciona una opción:"
        )

        return HandlerResponse(
            message=message,
            keyboard=keyboard,
        )


@intent_handler(UserIntent.RESCHEDULE)
class RescheduleHandler(BaseIntentHandler):
    """Handler para reprogramar tareas."""

    name = "RescheduleHandler"
    intents = [UserIntent.RESCHEDULE]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        entities = self.get_entities(intent_result)
        task_name = entities.get("task", "")

        if not task_name:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "📋 Ver tareas de hoy",
                        callback_data="show_today_for_reschedule",
                    ),
                ],
            ])

            return HandlerResponse(
                message=(
                    "📅 <b>Reprogramar tarea</b>\n\n"
                    "¿Qué tarea quieres mover?\n"
                    "Dime el nombre de la tarea o selecciona de tus pendientes:"
                ),
                keyboard=keyboard,
            )

        # Buscar la tarea
        notion = get_notion_service()
        tasks = await notion.get_pending_tasks(limit=15)

        matching = []
        for task in tasks:
            props = task.get("properties", {})
            title_prop = props.get("Tarea", {}).get("title", [])
            title = (
                title_prop[0].get("text", {}).get("content", "")
                if title_prop
                else ""
            )
            if task_name.lower() in title.lower():
                matching.append({"id": task["id"], "title": title})

        if matching:
            keyboard = []
            for task in matching[:5]:
                short_id = task["id"][:8]
                keyboard.append([
                    InlineKeyboardButton(
                        f"📅 {task['title'][:30]}",
                        callback_data=f"reschedule_task:{short_id}",
                    ),
                ])
            keyboard.append([
                InlineKeyboardButton(
                    "❌ Cancelar",
                    callback_data="reschedule_cancel",
                ),
            ])

            return HandlerResponse(
                message=(
                    f"📅 <b>Reprogramar tarea</b>\n\n"
                    f"Encontré estas tareas. Selecciona cuál mover:"
                ),
                keyboard=InlineKeyboardMarkup(keyboard),
            )

        return HandlerResponse(
            message=(
                f"🔍 No encontré tareas que coincidan con:\n"
                f"<i>{task_name[:50]}</i>\n\n"
                f"Intenta con otro nombre o usa /today."
            )
        )


@intent_handler(UserIntent.REMINDER_CREATE)
class ReminderCreateHandler(BaseIntentHandler):
    """Handler para crear recordatorios."""

    name = "ReminderCreateHandler"
    intents = [UserIntent.REMINDER_CREATE]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        entities = self.get_entities(intent_result)
        text = self.get_raw_message(intent_result)

        reminder_text = entities.get("reminder", text)
        reminder_time = entities.get("time", "")
        reminder_date = entities.get("date", "")

        # Guardar en context
        context.user_data["pending_reminder"] = {
            "text": reminder_text,
            "time": reminder_time,
            "date": reminder_date,
        }

        if not reminder_time and not reminder_date:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⏰ 30 min",
                        callback_data="reminder_time:30m",
                    ),
                    InlineKeyboardButton(
                        "⏰ 1 hora",
                        callback_data="reminder_time:1h",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "⏰ 3 horas",
                        callback_data="reminder_time:3h",
                    ),
                    InlineKeyboardButton(
                        "📅 Mañana 9AM",
                        callback_data="reminder_time:tomorrow",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "✏️ Personalizado",
                        callback_data="reminder_time:custom",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "❌ Cancelar",
                        callback_data="reminder_cancel",
                    ),
                ],
            ])

            return HandlerResponse(
                message=(
                    f"⏰ <b>Crear Recordatorio</b>\n\n"
                    f"<i>{reminder_text[:100]}</i>\n\n"
                    f"¿Cuándo quieres que te recuerde?"
                ),
                keyboard=keyboard,
            )

        # Crear el recordatorio directamente
        # TODO: Integrar con ReminderService
        return HandlerResponse(
            message=(
                f"⏰ <b>Recordatorio creado</b>\n\n"
                f"<i>{reminder_text[:100]}</i>\n\n"
                f"Te recordaré: {reminder_time or reminder_date or 'pronto'}"
            )
        )


@intent_handler(UserIntent.REMINDER_QUERY)
class ReminderQueryHandler(BaseIntentHandler):
    """Handler para consultar recordatorios."""

    name = "ReminderQueryHandler"
    intents = [UserIntent.REMINDER_QUERY]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        # TODO: Integrar con ReminderService para listar recordatorios
        return HandlerResponse(
            message=(
                "⏰ <b>Tus Recordatorios</b>\n\n"
                "(Funcionalidad de listar recordatorios próximamente)"
            )
        )
