"""Study Reminder Job - Recordatorio de hora de estudio."""

import logging
from datetime import datetime, timedelta

from app.config import get_settings
from app.services.telegram import get_telegram_service
from app.services.notion import get_notion_service
from app.bot.keyboards import study_options_keyboard

logger = logging.getLogger(__name__)
settings = get_settings()


async def study_reminder_job() -> None:
    """
    Envía recordatorio de hora de estudio con sugerencia de tema.

    Se ejecuta a las 5:30 PM todos los días.
    """
    logger.info("Ejecutando Study Reminder...")

    telegram = get_telegram_service()
    notion = get_notion_service()

    try:
        # Obtener proyectos de estudio en rotación
        study_projects = await notion.get_study_projects()

        # Obtener sugerencia
        suggestion = await _get_study_suggestion(study_projects)

        # Generar mensaje
        message = _format_study_message(suggestion)

        await telegram.send_message_with_keyboard(
            text=message,
            reply_markup=study_options_keyboard(suggestion),
        )

        logger.info("Study Reminder enviado")

    except Exception as e:
        logger.error(f"Error en Study Reminder: {e}")


async def _get_study_suggestion(study_projects: list) -> dict:
    """Obtiene sugerencia de tema a estudiar."""
    suggestion = {
        "topic": None,
        "project_id": None,
        "reason": "Balance de aprendizaje",
        "alternatives": [],
        "session_goal": "Estudiar 1 hora",
    }

    if not study_projects:
        suggestion["topic"] = "Sin proyectos de estudio definidos"
        suggestion["reason"] = "Agrega proyectos con 'En Rotación Estudio' en Notion"
        return suggestion

    # Analizar proyectos
    projects_data = []
    for project in study_projects:
        props = project.get("properties", {})

        # Nombre del proyecto
        title_prop = props.get("Proyecto", {}).get("title", [])
        name = (
            title_prop[0].get("text", {}).get("content", "Proyecto")
            if title_prop
            else "Proyecto"
        )

        # Última actividad
        last_activity = props.get("Última Actividad", {}).get("date", {})
        last_date = None
        if last_activity:
            date_str = last_activity.get("start", "")
            if date_str:
                try:
                    last_date = datetime.fromisoformat(date_str.split("T")[0])
                except ValueError:
                    pass

        # Días sin actividad
        days_inactive = 999
        if last_date:
            days_inactive = (datetime.now() - last_date).days

        # Progreso del hito
        progreso = props.get("Progreso Hito", {}).get("number", 0) or 0

        # Hito actual
        hito_prop = props.get("Hito Actual", {}).get("rich_text", [])
        hito = (
            hito_prop[0].get("text", {}).get("content", "")
            if hito_prop
            else ""
        )

        projects_data.append({
            "id": project.get("id"),
            "name": name,
            "days_inactive": days_inactive,
            "progreso": progreso,
            "hito": hito,
        })

    # Ordenar por días de inactividad (más descuidados primero)
    projects_data.sort(key=lambda x: x["days_inactive"], reverse=True)

    # Seleccionar sugerencia principal
    if projects_data:
        main = projects_data[0]
        suggestion["topic"] = main["name"]
        suggestion["project_id"] = main["id"]

        if main["days_inactive"] > 3:
            suggestion["reason"] = f"Sin actividad hace {main['days_inactive']} días"
        elif main["progreso"] < 50:
            suggestion["reason"] = f"Progreso: {main['progreso']}%"
        else:
            suggestion["reason"] = "Continuar donde lo dejaste"

        if main["hito"]:
            suggestion["session_goal"] = f"Avanzar en: {main['hito']}"

        # Agregar alternativas
        for alt in projects_data[1:3]:
            suggestion["alternatives"].append(alt["name"])

    return suggestion


def _format_study_message(suggestion: dict) -> str:
    """Formatea el mensaje de estudio."""
    now = datetime.now()
    weekday = now.weekday()

    # Mensaje base
    message = "📚 <b>Hora de Estudio</b>\n\n"

    # Día de la semana
    if weekday == 4:  # Viernes
        message += "🎉 ¡Último día laboral! Una hora de estudio y listo.\n\n"
    elif weekday >= 5:  # Fin de semana
        message += "🏖️ Fin de semana - estudio opcional pero recomendado.\n\n"

    # Sugerencia
    if suggestion["topic"]:
        message += f"📖 <b>Sugerencia:</b> {suggestion['topic']}\n"
        message += f"💡 <i>{suggestion['reason']}</i>\n\n"

        if suggestion["session_goal"]:
            message += f"🎯 <b>Meta de sesión:</b>\n{suggestion['session_goal']}\n\n"
    else:
        message += "No hay proyectos de estudio configurados.\n"
        message += "Agrega proyectos con 'En Rotación Estudio' = true en Notion.\n\n"

    # Alternativas
    if suggestion["alternatives"]:
        message += "<b>📋 Alternativas:</b>\n"
        for alt in suggestion["alternatives"]:
            message += f"• {alt}\n"
        message += "\n"

    # Tips según el día
    tips = {
        0: "💡 Lunes es buen día para empezar algo nuevo.",
        1: "💡 Martes: continúa lo que empezaste ayer.",
        2: "💡 Miércoles: mitad de semana, mantén el ritmo.",
        3: "💡 Jueves: casi viernes, un esfuerzo más.",
        4: "💡 Viernes: sesión ligera está bien.",
        5: "💡 Sábado: explora algo que te interese.",
        6: "💡 Domingo: prepara la semana estudiando algo útil.",
    }

    message += tips.get(weekday, "")
    message += "\n\n¿Qué vas a estudiar hoy?"

    return message


def study_options_keyboard(suggestion: dict):
    """Teclado de opciones de estudio."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    buttons = []

    # Botón principal si hay sugerencia
    if suggestion["topic"] and suggestion["topic"] != "Sin proyectos de estudio definidos":
        buttons.append([
            InlineKeyboardButton(
                f"✅ Estudiar {suggestion['topic'][:20]}",
                callback_data=f"study_start_{suggestion['project_id'][:8] if suggestion['project_id'] else 'none'}",
            ),
        ])

    # Alternativas
    for i, alt in enumerate(suggestion["alternatives"][:2]):
        buttons.append([
            InlineKeyboardButton(
                f"📖 {alt[:25]}",
                callback_data=f"study_alt_{i}",
            ),
        ])

    # Opciones adicionales
    buttons.append([
        InlineKeyboardButton("⏰ En 30 min", callback_data="study_later_30"),
        InlineKeyboardButton("❌ Hoy no", callback_data="study_skip"),
    ])

    return InlineKeyboardMarkup(buttons)
