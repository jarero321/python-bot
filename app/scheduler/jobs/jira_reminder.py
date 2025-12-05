"""
Jira Reminder Job - Recordatorio para registrar tareas PayCash en Jira.

Al final del día, pregunta si registraste las tareas completadas de PayCash en Jira.
Si no, te ayuda a crear el contexto de la HU.
"""

import logging
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import get_settings
from app.services.notion import get_notion_service, TaskEstado, TaskContexto
from app.services.telegram import get_telegram_service
from app.utils.schedule_helpers import is_weekend

logger = logging.getLogger(__name__)
settings = get_settings()


async def jira_reminder_job() -> None:
    """
    Recordatorio diario de Jira para tareas PayCash.

    Se ejecuta a las 6:30 PM en días laborales.
    Pregunta si registraste las tareas completadas hoy en Jira.
    """
    now = datetime.now()

    # No ejecutar en fines de semana
    if is_weekend(now):
        logger.info("Jira reminder omitido - es fin de semana")
        return

    logger.info("Ejecutando Jira Reminder...")

    notion = get_notion_service()
    telegram = get_telegram_service()

    try:
        # Obtener tareas PayCash completadas hoy
        completed_tasks = await get_paycash_tasks_completed_today()

        if not completed_tasks:
            logger.info("No hay tareas PayCash completadas hoy")
            return

        # Construir mensaje
        message = (
            "<b>Recordatorio Jira</b>\n\n"
            f"Completaste {len(completed_tasks)} tarea(s) de PayCash hoy:\n\n"
        )

        for i, task in enumerate(completed_tasks, 1):
            message += f"{i}. {task['title']}\n"

        message += "\n¿Ya las registraste en Jira?"

        # Botones
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Sí, todas",
                    callback_data="jira_done_all",
                ),
                InlineKeyboardButton(
                    "❌ No, ayúdame",
                    callback_data="jira_need_help",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔄 Algunas sí, otras no",
                    callback_data="jira_partial",
                ),
            ],
        ]

        await telegram.send_message(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        # Guardar tareas en contexto para el callback
        from app.db.database import async_session_factory
        from app.db.models import ConversationState
        from sqlalchemy import select
        import json

        async with async_session_factory() as session:
            stmt = select(ConversationState).where(
                ConversationState.chat_id == str(settings.telegram_chat_id)
            )
            result = await session.execute(stmt)
            state = result.scalar_one_or_none()

            if state:
                state.flow_data = json.dumps({
                    "pending_jira_tasks": [
                        {"id": t["id"], "title": t["title"]}
                        for t in completed_tasks
                    ]
                })
                await session.commit()

        logger.info(f"Jira reminder enviado para {len(completed_tasks)} tareas")

    except Exception as e:
        logger.error(f"Error en Jira Reminder: {e}")


async def get_paycash_tasks_completed_today() -> list[dict]:
    """
    Obtiene tareas de PayCash completadas hoy.
    """
    notion = get_notion_service()

    try:
        # Obtener todas las tareas completadas
        tasks = await notion.get_tasks_by_status(TaskEstado.DONE)

        # Filtrar por contexto PayCash y fecha de hoy
        today = datetime.now().strftime("%Y-%m-%d")
        paycash_tasks = []

        for task in tasks:
            properties = task.get("properties", {})

            # Verificar contexto PayCash
            contexto = properties.get("Contexto", {}).get("select", {})
            if not contexto or contexto.get("name") != TaskContexto.PAYCASH.value:
                continue

            # Verificar fecha de completado (Fecha Done)
            fecha_done = properties.get("Fecha Done", {}).get("date")
            if not fecha_done:
                continue

            done_date = fecha_done.get("start", "")[:10]
            if done_date != today:
                continue

            # Extraer título
            title_prop = properties.get("Tarea", {}).get("title", [])
            title = title_prop[0].get("plain_text", "") if title_prop else "Sin título"

            paycash_tasks.append({
                "id": task.get("id", ""),
                "title": title,
                "properties": properties,
            })

        return paycash_tasks

    except Exception as e:
        logger.error(f"Error obteniendo tareas PayCash: {e}")
        return []


async def send_jira_task_builder(task_id: str, task_title: str) -> None:
    """
    Envía el builder de contexto para crear HU en Jira.
    """
    telegram = get_telegram_service()

    message = (
        f"<b>Crear HU para Jira</b>\n\n"
        f"<b>Tarea:</b> {task_title}\n\n"
        "Dame el contexto de la tarea para ayudarte a crear la HU:\n\n"
        "1. ¿Qué problema resuelve?\n"
        "2. ¿Qué cambios hiciste?\n"
        "3. ¿Hay criterios de aceptación?\n\n"
        "<i>Escribe libremente y te ayudo a estructurarlo.</i>"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "📋 Usar plantilla",
                callback_data=f"jira_template:{task_id[:20]}",
            ),
        ],
        [
            InlineKeyboardButton(
                "⏭️ Saltar esta",
                callback_data=f"jira_skip:{task_id[:20]}",
            ),
        ],
    ]

    await telegram.send_message(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
