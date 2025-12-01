"""
Planning Handlers - Planificación y recordatorios.

Handlers para planificar el día/semana, priorizar tareas, y recordatorios.
Usan repositorios del dominio en lugar de NotionService directamente.
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
from app.core.llm import get_llm_provider
from app.domain.repositories import get_task_repository, ITaskRepository
from app.domain.entities.task import Task, TaskStatus, TaskPriority

logger = logging.getLogger(__name__)


# ==================== Helpers ====================

def format_task_for_plan(task: Task) -> str:
    """Formatea una tarea para planes."""
    priority_icon = {
        TaskPriority.URGENT: "🔥",
        TaskPriority.HIGH: "⚡",
        TaskPriority.NORMAL: "📌",
        TaskPriority.LOW: "🧊",
    }.get(task.priority, "📌")

    return f"{priority_icon} {task.title}"


# ==================== Helpers ====================

def is_working_hours() -> tuple[bool, str]:
    """
    Verifica si estamos en horario laboral.
    Retorna (is_working, message).
    """
    from datetime import datetime

    now = datetime.now()

    # Fin de semana
    if now.weekday() > 4:
        return False, "Es fin de semana. El horario laboral es de lunes a viernes."

    # Fuera de horario (9:00 - 18:00)
    if now.hour < 9:
        return False, f"Aún no es horario laboral (son las {now.hour}:{now.minute:02d}). El horario comienza a las 9:00."

    if now.hour >= 18:
        return False, f"Ya terminó el horario laboral (son las {now.hour}:{now.minute:02d}). El horario es hasta las 18:00."

    return True, ""


# ==================== Handlers ====================

@intent_handler(UserIntent.PLAN_TODAY)
class PlanTodayHandler(BaseIntentHandler):
    """Handler para planificar el día de hoy."""

    name = "PlanTodayHandler"
    intents = [UserIntent.PLAN_TODAY]

    def __init__(self, task_repo: ITaskRepository | None = None):
        super().__init__()
        self._task_repo = task_repo or get_task_repository()

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        from datetime import datetime
        from app.agents.orchestrator import get_orchestrator

        # Validar horario laboral
        is_working, reason = is_working_hours()
        if not is_working:
            return HandlerResponse(
                message=f"⏰ <b>Fuera de horario laboral</b>\n\n{reason}\n\n💡 Puedes usar <i>\"planifica mañana\"</i> para preparar el día siguiente.",
            )

        text = self.get_raw_message(intent_result)

        # Mostrar procesamiento
        processing_msg = await update.message.reply_html(
            "📅 <b>Planificando tu día...</b>\n\n"
            "⏳ Analizando tareas pendientes y prioridades..."
        )

        try:
            orchestrator = get_orchestrator()

            # Obtener tareas de hoy
            today_tasks = await self._task_repo.get_for_today()

            if not today_tasks:
                # No hay tareas, ofrecer generar plan
                pending_tasks = await self._task_repo.get_pending(limit=10)

                if not pending_tasks:
                    await processing_msg.edit_text(
                        "📭 <b>Sin tareas pendientes</b>\n\n"
                        "No tienes tareas para hoy ni pendientes.\n\n"
                        "💡 Puedes crear una tarea con:\n"
                        "<i>\"Tengo que hacer X\"</i>",
                        parse_mode="HTML",
                    )
                    return HandlerResponse(
                        message="Sin tareas pendientes",
                        already_sent=True,
                    )

                # Hay tareas pendientes pero ninguna para hoy
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "📋 Asignar tareas a hoy",
                            callback_data="assign_tasks_today",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "🌅 Generar plan automático",
                            callback_data="generate_today_plan",
                        ),
                    ],
                ])

                pending_list = "\n".join([f"  • {format_task_for_plan(t)}" for t in pending_tasks[:5]])

                await processing_msg.edit_text(
                    f"📅 <b>Planificar Hoy</b>\n\n"
                    f"No tienes tareas asignadas para hoy.\n\n"
                    f"<b>Tareas pendientes disponibles:</b>\n{pending_list}\n\n"
                    f"¿Qué quieres hacer?",
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )

                return HandlerResponse(
                    message="Ofrecer asignar tareas",
                    already_sent=True,
                )

            # Hay tareas para hoy, generar plan con AI
            provider = get_llm_provider()
            provider.ensure_configured()

            with provider.for_task("morning_planning"):
                plan = await orchestrator.generate_morning_plan()

            # Formatear respuesta
            now = datetime.now()
            response = f"📅 <b>Tu plan para hoy</b>\n"
            response += f"<i>{now.strftime('%A %d de %B')}</i>\n\n"

            message = orchestrator.morning_planner.format_telegram_message(plan)

            # Agregar resumen de carga
            workload = await orchestrator.get_workload_summary()
            if workload.get("overdue", 0) > 0:
                message += f"\n\n⚠️ <b>Atrasadas:</b> {workload['overdue']} tareas"

            await processing_msg.edit_text(
                message,
                parse_mode="HTML",
            )

            return HandlerResponse(
                message=message,
                already_sent=True,
            )

        except Exception as e:
            logger.error(f"Error en planificación de hoy: {e}")
            try:
                await processing_msg.edit_text(
                    "❌ Error al planificar. Intenta de nuevo.",
                    parse_mode="HTML",
                )
            except Exception:
                pass
            return HandlerResponse(
                message="❌ Error al planificar.",
                success=False,
                already_sent=True,
            )


@intent_handler(UserIntent.PLAN_TOMORROW)
class PlanTomorrowHandler(BaseIntentHandler):
    """Handler para planificar el día siguiente."""

    name = "PlanTomorrowHandler"
    intents = [UserIntent.PLAN_TOMORROW]

    def __init__(self, task_repo: ITaskRepository | None = None):
        super().__init__()
        self._task_repo = task_repo or get_task_repository()

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        from app.agents.planning_assistant import get_planning_assistant

        text = self.get_raw_message(intent_result)

        # Mostrar procesamiento (mensaje que se editará después)
        processing_msg = await update.message.reply_html(
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

            # Verificar si hay error (plan vacío)
            if not plan.selected_tasks:
                if plan.warnings and "Error" in plan.warnings[0]:
                    return HandlerResponse(
                        message=f"❌ Error: {plan.warnings[0]}",
                        success=False,
                        already_sent=True,
                    )

            # Construir respuesta usando atributos del dataclass TomorrowPlan
            response = f"🌅 <b>Plan para {plan.day_of_week}</b>\n"
            response += f"<i>{plan.date}</i>\n\n"

            if plan.selected_tasks:
                response += "<b>🎯 Tareas seleccionadas:</b>\n"
                for task in plan.selected_tasks[:5]:
                    task_name = task.get("name", "Sin nombre") if isinstance(task, dict) else str(task)
                    prioridad = task.get("prioridad", "") if isinstance(task, dict) else ""
                    response += f"  • {task_name}"
                    if prioridad:
                        response += f" [{prioridad}]"
                    response += "\n"
                response += "\n"

            if plan.task_order:
                response += "<b>📋 Orden sugerido:</b>\n"
                for i, order_item in enumerate(plan.task_order[:5], 1):
                    response += f"  {i}. {order_item}\n"
                response += "\n"

            if plan.reasoning:
                response += f"<b>💡 Razonamiento:</b>\n{plan.reasoning}\n\n"

            if plan.warnings:
                response += "<b>⚠️ Alertas:</b>\n"
                for warning in plan.warnings[:3]:
                    response += f"  • {warning}\n"
                response += "\n"

            if plan.suggestions:
                response += "<b>💭 Sugerencias:</b>\n"
                for suggestion in plan.suggestions[:2]:
                    response += f"  • {suggestion}\n"
                response += "\n"

            response += f"<i>⏱️ Carga estimada: {plan.estimated_workload_hours:.1f} horas</i>"

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

            # Editar el mensaje de procesamiento con la respuesta final
            await processing_msg.edit_text(
                response,
                parse_mode="HTML",
                reply_markup=keyboard,
            )

            return HandlerResponse(
                message=response,
                keyboard=keyboard,
                already_sent=True,
            )

        except Exception as e:
            logger.error(f"Error en planificación: {e}")
            # Editar mensaje con error
            try:
                await processing_msg.edit_text(
                    "❌ Error al planificar. Intenta de nuevo.",
                    parse_mode="HTML",
                )
            except Exception:
                pass
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

    def __init__(self, task_repo: ITaskRepository | None = None):
        super().__init__()
        self._task_repo = task_repo or get_task_repository()

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        from app.agents.planning_assistant import get_planning_assistant

        processing_msg = await update.message.reply_html(
            "📊 <b>Cargando resumen semanal...</b>"
        )

        try:
            planning = get_planning_assistant()
            overview = await planning.get_week_overview()

            if "error" in overview:
                await processing_msg.edit_text(
                    f"❌ Error: {overview['error']}",
                    parse_mode="HTML",
                )
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

            # Editar mensaje con respuesta
            await processing_msg.edit_text(response, parse_mode="HTML")

            return HandlerResponse(
                message=response,
                already_sent=True,
            )

        except Exception as e:
            logger.error(f"Error obteniendo semana: {e}")
            try:
                await processing_msg.edit_text(
                    "❌ Error al cargar la semana.",
                    parse_mode="HTML",
                )
            except Exception:
                pass
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

    def __init__(self, task_repo: ITaskRepository | None = None):
        super().__init__()
        self._task_repo = task_repo or get_task_repository()

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        try:
            # Usar repositorio directamente
            summary = await self._task_repo.get_workload_summary()

            total = summary.get("total_pending", 0)
            overdue = summary.get("overdue", 0)
            prio = summary.get("by_priority", {})

            response = "📊 <b>Tu carga de trabajo</b>\n\n"
            response += f"📋 <b>Total pendiente:</b> {total} tareas\n"

            if overdue > 0:
                response += f"⚠️ <b>Vencidas:</b> {overdue}\n"

            response += f"\n<b>Por prioridad:</b>\n"
            response += f"🔥 Urgente: {prio.get('urgent', 0)}\n"
            response += f"⚡ Alta: {prio.get('high', 0)}\n"
            response += f"📌 Normal: {prio.get('normal', 0)}\n"
            response += f"🧊 Baja: {prio.get('low', 0)}\n"

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

    def __init__(self, task_repo: ITaskRepository | None = None):
        super().__init__()
        self._task_repo = task_repo or get_task_repository()

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        # Obtener tareas urgentes para mostrar
        urgent_tasks = await self._task_repo.get_by_priority(TaskPriority.URGENT)

        keyboard_rows = []

        if urgent_tasks:
            keyboard_rows.append([
                InlineKeyboardButton(
                    f"🔥 Ver {len(urgent_tasks)} urgentes",
                    callback_data="show_urgent_tasks",
                ),
            ])

        keyboard_rows.append([
            InlineKeyboardButton(
                "📊 Ver mi carga",
                callback_data="workload_check",
            ),
        ])

        keyboard = InlineKeyboardMarkup(keyboard_rows)

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

    def __init__(self, task_repo: ITaskRepository | None = None):
        super().__init__()
        self._task_repo = task_repo or get_task_repository()

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

        # Buscar la tarea usando repositorio
        tasks = await self._task_repo.get_pending(limit=15)

        matching = []
        for task in tasks:
            if task_name.lower() in task.title.lower():
                matching.append(task)

        if matching:
            keyboard = []
            for task in matching[:5]:
                keyboard.append([
                    InlineKeyboardButton(
                        f"📅 {task.title[:30]}",
                        callback_data=f"reschedule_task:{task.id}",
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

        # El IntentRouter usa "task" o "reminder" para el texto del recordatorio
        reminder_text = entities.get("task") or entities.get("reminder") or text
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
        import re
        from datetime import datetime, timedelta
        from app.services.reminder_service import get_reminder_service

        now = datetime.now()
        scheduled_at = None
        time_str = (reminder_time or reminder_date or "").lower()

        # Parsear tiempo relativo
        match = re.search(r"(\d+)\s*(minuto|min|m|hora|h)", time_str)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            if unit.startswith("h"):
                scheduled_at = now + timedelta(hours=amount)
            else:
                scheduled_at = now + timedelta(minutes=amount)

        # Parsear "mañana"
        if not scheduled_at and "mañana" in time_str:
            hour_match = re.search(r"(\d{1,2})(?::(\d{2}))?", time_str)
            if hour_match:
                hour = int(hour_match.group(1))
                minute = int(hour_match.group(2) or 0)
                scheduled_at = (now + timedelta(days=1)).replace(
                    hour=hour, minute=minute, second=0
                )
            else:
                scheduled_at = (now + timedelta(days=1)).replace(
                    hour=9, minute=0, second=0
                )

        # Parsear hora específica "a las X"
        if not scheduled_at:
            hour_match = re.search(r"(?:a\s+las?\s+)?(\d{1,2})(?::(\d{2}))?(?:\s*(am|pm))?", time_str)
            if hour_match:
                hour = int(hour_match.group(1))
                minute = int(hour_match.group(2) or 0)
                ampm = hour_match.group(3)
                if ampm == "pm" and hour < 12:
                    hour += 12
                scheduled_at = now.replace(hour=hour, minute=minute, second=0)
                if scheduled_at <= now:
                    scheduled_at += timedelta(days=1)

        if not scheduled_at:
            # Fallback: 1 hora
            scheduled_at = now + timedelta(hours=1)

        # Crear recordatorio
        try:
            chat_id = str(update.effective_chat.id)
            user_id = str(update.effective_user.id)
            service = get_reminder_service()

            await service.create_reminder(
                chat_id=chat_id,
                user_id=user_id,
                title=reminder_text,
                scheduled_at=scheduled_at,
            )

            time_display = scheduled_at.strftime("%H:%M del %d/%m")
            return HandlerResponse(
                message=(
                    f"✅ <b>Recordatorio creado</b>\n\n"
                    f"<i>{reminder_text[:100]}</i>\n\n"
                    f"⏰ Te recordaré: {time_display}"
                )
            )
        except Exception as e:
            self.logger.error(f"Error creando recordatorio: {e}")
            return HandlerResponse(
                message=f"❌ Error creando recordatorio: {str(e)[:50]}"
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
        from app.services.reminder_service import get_reminder_service
        from datetime import datetime

        chat_id = str(update.effective_chat.id)
        service = get_reminder_service()

        # Obtener recordatorios próximos (24 horas)
        upcoming = await service.get_upcoming_reminders(chat_id, hours=24)

        # Obtener todos los pendientes
        all_pending = await service.get_pending_reminders(chat_id=chat_id)

        if not upcoming and not all_pending:
            return HandlerResponse(
                message=(
                    "⏰ <b>Tus Recordatorios</b>\n\n"
                    "No tienes recordatorios pendientes.\n\n"
                    "💡 Crea uno con:\n"
                    "<i>\"Recuérdame llamar al doctor mañana a las 10\"</i>"
                )
            )

        message = "⏰ <b>Tus Recordatorios</b>\n\n"

        if upcoming:
            message += "<b>📍 Próximas 24 horas:</b>\n"
            for reminder in upcoming[:5]:
                time_str = reminder.scheduled_at.strftime("%H:%M")
                date_str = reminder.scheduled_at.strftime("%d/%m")
                priority_emoji = {
                    "urgent": "🔥",
                    "high": "⚡",
                    "normal": "📌",
                    "low": "📎",
                }.get(reminder.priority.value, "📌")

                status_emoji = ""
                if reminder.status.value == "snoozed":
                    status_emoji = " (⏸️ pospuesto)"

                message += f"{priority_emoji} {time_str} - {reminder.title}{status_emoji}\n"
            message += "\n"

        # Mostrar otros pendientes (no en las próximas 24h)
        other_pending = [r for r in all_pending if r not in upcoming]
        if other_pending:
            message += f"<b>📅 Más adelante:</b> {len(other_pending)} recordatorio(s)\n"

        message += f"\n📊 Total pendientes: {len(all_pending)}"

        return HandlerResponse(message=message)
