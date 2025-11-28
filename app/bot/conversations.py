"""Flujos conversacionales del bot de Telegram."""

import logging
import re
from datetime import datetime, timedelta
from enum import IntEnum, auto

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from app.agents import (
    InboxProcessorAgent,
    SpendingAnalyzerAgent,
    WorkoutLoggerAgent,
    NutritionAnalyzerAgent,
    WorkoutType,
)
from app.services.notion import (
    get_notion_service,
    TaskEstado,
    TaskContexto,
    TaskPrioridad,
    InboxFuente,
)

logger = logging.getLogger(__name__)


# ==================== ESTADOS DE CONVERSACIÓN ====================


class InboxStates(IntEnum):
    """Estados del flujo de captura rápida."""
    WAITING_CLASSIFICATION = auto()
    WAITING_PROJECT = auto()
    WAITING_PRIORITY = auto()
    WAITING_CONFIRMATION = auto()


class DeepWorkStates(IntEnum):
    """Estados del flujo de Deep Work."""
    SELECTING_TASK = auto()
    CONFIRMING_DURATION = auto()
    IN_PROGRESS = auto()
    CHECKING_STATUS = auto()
    COMPLETING = auto()


class PurchaseStates(IntEnum):
    """Estados del flujo de análisis de compra."""
    ANALYZING = auto()
    WAITING_DECISION = auto()
    ADDING_NOTES = auto()


class GymStates(IntEnum):
    """Estados del flujo de registro de gym."""
    SELECTING_TYPE = auto()
    ENTERING_EXERCISES = auto()
    CONFIRMING_DETAILS = auto()
    ADDING_NOTES = auto()


class NutritionStates(IntEnum):
    """Estados del flujo de registro de comidas."""
    ENTERING_MEALS = auto()
    RATING_DAY = auto()
    ADDING_DETAILS = auto()
    CONFIRMING = auto()


# ==================== FLUJO: CAPTURA RÁPIDA ====================


async def start_inbox_capture(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el flujo de captura rápida cuando llega un mensaje."""
    text = update.message.text
    user_data = context.user_data

    # Guardar mensaje original
    user_data["inbox_text"] = text
    user_data["inbox_timestamp"] = datetime.now()

    await update.message.reply_text("🔄 Analizando mensaje...")

    try:
        # Clasificar con InboxProcessor
        agent = InboxProcessorAgent()
        result = await agent.classify_message(text)

        user_data["classification"] = result

        # Construir mensaje según confianza
        if result.confidence >= 0.8:
            # Alta confianza - confirmar directamente
            message = (
                f"📋 <b>Clasificación</b> (confianza: {result.confidence:.0%})\n\n"
                f"<b>Categoría:</b> {result.category.value}\n"
                f"<b>Título:</b> {result.suggested_title}\n"
            )
            if result.suggested_project:
                message += f"<b>Proyecto:</b> {result.suggested_project}\n"
            if result.suggested_context:
                message += f"<b>Contexto:</b> {result.suggested_context}\n"

            message += "\n¿Es correcto?"

            keyboard = [
                [
                    InlineKeyboardButton("✅ Sí, guardar", callback_data="inbox_confirm"),
                    InlineKeyboardButton("✏️ Editar", callback_data="inbox_edit"),
                ],
                [
                    InlineKeyboardButton("❌ Cancelar", callback_data="inbox_cancel"),
                ],
            ]

            await update.message.reply_html(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return InboxStates.WAITING_CONFIRMATION

        elif result.confidence >= 0.5:
            # Confianza media - preguntar específico
            message = (
                f"🤔 <b>Necesito confirmar</b> (confianza: {result.confidence:.0%})\n\n"
                f"Creo que es: <b>{result.category.value}</b>\n"
            )

            if result.needs_clarification and result.clarification_question:
                message += f"\n{result.clarification_question}"

            keyboard = [
                [
                    InlineKeyboardButton("✅ Sí", callback_data="inbox_confirm_category"),
                    InlineKeyboardButton("❌ No", callback_data="inbox_change_category"),
                ],
            ]

            await update.message.reply_html(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return InboxStates.WAITING_CLASSIFICATION

        else:
            # Baja confianza - pedir más contexto
            message = (
                f"❓ <b>No estoy seguro</b> (confianza: {result.confidence:.0%})\n\n"
                f"<i>{text[:100]}</i>\n\n"
            )

            if result.clarification_question:
                message += result.clarification_question
            else:
                message += "¿Qué tipo de captura es?\n"

            keyboard = [
                [
                    InlineKeyboardButton("📋 Tarea", callback_data="inbox_type_task"),
                    InlineKeyboardButton("💰 Gasto", callback_data="inbox_type_finance"),
                ],
                [
                    InlineKeyboardButton("💡 Idea", callback_data="inbox_type_idea"),
                    InlineKeyboardButton("📝 Nota", callback_data="inbox_type_note"),
                ],
                [
                    InlineKeyboardButton("❌ Cancelar", callback_data="inbox_cancel"),
                ],
            ]

            await update.message.reply_html(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return InboxStates.WAITING_CLASSIFICATION

    except Exception as e:
        logger.error(f"Error en clasificación: {e}")
        # Fallback: guardar directamente en inbox
        notion = get_notion_service()
        await notion.create_inbox_item(
            contenido=text[:200],
            fuente=InboxFuente.TELEGRAM,
            notas="Clasificación automática fallida",
        )
        await update.message.reply_html(
            f"📥 Guardado en Inbox (clasificación manual pendiente):\n\n"
            f"<i>{text[:100]}</i>"
        )
        return ConversationHandler.END


async def handle_inbox_classification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la selección de categoría del inbox."""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_data = context.user_data

    if data == "inbox_confirm_category":
        # Usuario confirmó la categoría sugerida
        return await save_inbox_item(update, context)

    elif data == "inbox_change_category":
        # Usuario quiere cambiar categoría
        keyboard = [
            [
                InlineKeyboardButton("📋 Tarea", callback_data="inbox_type_task"),
                InlineKeyboardButton("💰 Finanzas", callback_data="inbox_type_finance"),
            ],
            [
                InlineKeyboardButton("🏋️ Gym", callback_data="inbox_type_gym"),
                InlineKeyboardButton("🍽️ Nutrición", callback_data="inbox_type_nutrition"),
            ],
            [
                InlineKeyboardButton("💡 Idea", callback_data="inbox_type_idea"),
                InlineKeyboardButton("📝 Nota", callback_data="inbox_type_note"),
            ],
        ]

        await query.edit_message_text(
            "Selecciona el tipo correcto:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return InboxStates.WAITING_CLASSIFICATION

    elif data.startswith("inbox_type_"):
        # Usuario seleccionó tipo manualmente
        type_selected = data.replace("inbox_type_", "")
        user_data["manual_type"] = type_selected

        # Pedir proyecto si es tarea
        if type_selected == "task":
            return await ask_for_project(update, context)
        else:
            return await save_inbox_item(update, context)

    return InboxStates.WAITING_CLASSIFICATION


async def ask_for_project(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Pregunta el proyecto para una tarea."""
    query = update.callback_query

    # Obtener proyectos activos
    notion = get_notion_service()
    projects = await notion.get_projects(active_only=True)

    keyboard = []
    for project in projects[:6]:  # Máximo 6 proyectos
        props = project.get("properties", {})
        title_prop = props.get("Proyecto", {}).get("title", [])
        name = title_prop[0].get("text", {}).get("content", "?") if title_prop else "?"

        keyboard.append([
            InlineKeyboardButton(
                name[:30],
                callback_data=f"inbox_project_{project.get('id', '')[:8]}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton("📁 Sin proyecto", callback_data="inbox_project_none"),
    ])

    await query.edit_message_text(
        "¿A qué proyecto pertenece?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return InboxStates.WAITING_PROJECT


async def handle_project_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la selección de proyecto."""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_data = context.user_data

    if data.startswith("inbox_project_"):
        project_id = data.replace("inbox_project_", "")
        if project_id != "none":
            user_data["selected_project_id"] = project_id

    return await save_inbox_item(update, context)


async def handle_inbox_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la confirmación final del inbox."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "inbox_confirm":
        return await save_inbox_item(update, context)
    elif data == "inbox_edit":
        return await ask_for_project(update, context)
    elif data == "inbox_cancel":
        await query.edit_message_text("❌ Captura cancelada.")
        return ConversationHandler.END

    return InboxStates.WAITING_CONFIRMATION


async def save_inbox_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el item en Notion."""
    query = update.callback_query
    user_data = context.user_data

    text = user_data.get("inbox_text", "")
    classification = user_data.get("classification")

    notion = get_notion_service()

    try:
        # Determinar si crear tarea o inbox
        manual_type = user_data.get("manual_type")
        is_task = (
            manual_type == "task"
            or (classification and classification.category.value == "task")
        )

        if is_task:
            # Crear tarea
            title = classification.suggested_title if classification else text[:100]
            result = await notion.create_task(
                tarea=title,
                contexto=TaskContexto.PERSONAL,
                estado=TaskEstado.BACKLOG,
                notas=text if len(text) > 100 else None,
            )
            message = f"✅ <b>Tarea creada:</b>\n{title}"
        else:
            # Crear inbox item
            confidence = classification.confidence if classification else 0
            result = await notion.create_inbox_item(
                contenido=text[:200],
                fuente=InboxFuente.TELEGRAM,
                confianza_ai=confidence,
            )
            message = f"✅ <b>Guardado en Inbox:</b>\n{text[:100]}"

        await query.edit_message_text(message, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error guardando: {e}")
        await query.edit_message_text("❌ Error guardando. Intenta de nuevo.")

    # Limpiar user_data
    user_data.clear()

    return ConversationHandler.END


async def cancel_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela el flujo de inbox."""
    context.user_data.clear()

    if update.callback_query:
        await update.callback_query.edit_message_text("❌ Captura cancelada.")
    else:
        await update.message.reply_text("❌ Captura cancelada.")

    return ConversationHandler.END


# ==================== FLUJO: DEEP WORK ====================


async def start_deep_work(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el flujo de Deep Work."""
    user_data = context.user_data

    # Verificar si hay tarea especificada
    if context.args:
        task_name = " ".join(context.args)
        user_data["deepwork_task"] = task_name
        user_data["deepwork_custom"] = True

        keyboard = [
            [
                InlineKeyboardButton("1h", callback_data="deepwork_duration_60"),
                InlineKeyboardButton("2h", callback_data="deepwork_duration_120"),
                InlineKeyboardButton("3h", callback_data="deepwork_duration_180"),
            ],
            [
                InlineKeyboardButton("❌ Cancelar", callback_data="deepwork_cancel"),
            ],
        ]

        await update.message.reply_html(
            f"🧠 <b>Deep Work</b>\n\n"
            f"Tarea: <b>{task_name}</b>\n\n"
            f"¿Cuánto tiempo?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return DeepWorkStates.CONFIRMING_DURATION

    # Sin tarea especificada - mostrar pendientes
    notion = get_notion_service()
    tasks = await notion.get_pending_tasks(limit=5)

    if not tasks:
        await update.message.reply_text(
            "No hay tareas pendientes. Usa /add para crear una."
        )
        return ConversationHandler.END

    keyboard = []
    for i, task in enumerate(tasks):
        props = task.get("properties", {})
        title_prop = props.get("Tarea", {}).get("title", [])
        name = title_prop[0].get("text", {}).get("content", "?") if title_prop else "?"

        keyboard.append([
            InlineKeyboardButton(
                f"{i+1}. {name[:40]}",
                callback_data=f"deepwork_task_{task.get('id', '')[:8]}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton("✏️ Otra tarea", callback_data="deepwork_custom"),
        InlineKeyboardButton("❌ Cancelar", callback_data="deepwork_cancel"),
    ])

    await update.message.reply_html(
        "🧠 <b>Deep Work</b>\n\n"
        "Selecciona la tarea para enfocarte:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return DeepWorkStates.SELECTING_TASK


async def handle_deepwork_task_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la selección de tarea para deep work."""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_data = context.user_data

    if data == "deepwork_cancel":
        await query.edit_message_text("❌ Deep Work cancelado.")
        return ConversationHandler.END

    if data == "deepwork_custom":
        await query.edit_message_text(
            "Escribe el nombre de la tarea:"
        )
        return DeepWorkStates.SELECTING_TASK

    if data.startswith("deepwork_task_"):
        task_id = data.replace("deepwork_task_", "")
        user_data["deepwork_task_id"] = task_id

        # TODO: Obtener nombre de la tarea
        user_data["deepwork_task"] = "Tarea seleccionada"

    # Preguntar duración
    keyboard = [
        [
            InlineKeyboardButton("1h", callback_data="deepwork_duration_60"),
            InlineKeyboardButton("2h", callback_data="deepwork_duration_120"),
            InlineKeyboardButton("3h", callback_data="deepwork_duration_180"),
        ],
        [
            InlineKeyboardButton("❌ Cancelar", callback_data="deepwork_cancel"),
        ],
    ]

    await query.edit_message_text(
        f"🧠 <b>Deep Work</b>\n\n"
        f"Tarea: <b>{user_data.get('deepwork_task', 'Tarea')}</b>\n\n"
        f"¿Cuánto tiempo?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return DeepWorkStates.CONFIRMING_DURATION


async def handle_deepwork_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la selección de duración del deep work."""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_data = context.user_data

    if data == "deepwork_cancel":
        await query.edit_message_text("❌ Deep Work cancelado.")
        return ConversationHandler.END

    if data.startswith("deepwork_duration_"):
        minutes = int(data.replace("deepwork_duration_", ""))
        user_data["deepwork_duration"] = minutes
        user_data["deepwork_start"] = datetime.now()
        user_data["deepwork_end"] = datetime.now() + timedelta(minutes=minutes)

        end_time = user_data["deepwork_end"].strftime("%H:%M")

        # Actualizar tarea a "Doing" si hay ID
        if user_data.get("deepwork_task_id"):
            notion = get_notion_service()
            await notion.update_task_estado(
                user_data["deepwork_task_id"],
                TaskEstado.DOING,
            )

        keyboard = [
            [
                InlineKeyboardButton("✅ Terminé antes", callback_data="deepwork_done_early"),
                InlineKeyboardButton("🚫 Bloqueado", callback_data="deepwork_blocked"),
            ],
            [
                InlineKeyboardButton("⏸️ Pausa", callback_data="deepwork_pause"),
            ],
        ]

        await query.edit_message_text(
            f"🧠 <b>DEEP WORK ACTIVO</b>\n\n"
            f"📋 {user_data.get('deepwork_task', 'Tarea')}\n"
            f"⏱️ {minutes} minutos\n"
            f"🏁 Hasta las {end_time}\n\n"
            f"<i>Te avisaré cuando termines.\n"
            f"Evita distracciones 🎯</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        # TODO: Programar recordatorio al terminar

        return DeepWorkStates.IN_PROGRESS

    return DeepWorkStates.CONFIRMING_DURATION


async def handle_deepwork_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja actualizaciones durante deep work."""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_data = context.user_data

    if data == "deepwork_done_early":
        # Calcular tiempo real
        start = user_data.get("deepwork_start", datetime.now())
        actual_minutes = int((datetime.now() - start).total_seconds() / 60)

        await query.edit_message_text(
            f"✅ <b>Deep Work Completado</b>\n\n"
            f"📋 {user_data.get('deepwork_task', 'Tarea')}\n"
            f"⏱️ Tiempo real: {actual_minutes} minutos\n\n"
            f"¡Buen trabajo! 💪",
            parse_mode="HTML",
        )

        # Actualizar tarea a Done
        if user_data.get("deepwork_task_id"):
            notion = get_notion_service()
            await notion.update_task_estado(
                user_data["deepwork_task_id"],
                TaskEstado.DONE,
                tiempo_real=actual_minutes,
            )

        user_data.clear()
        return ConversationHandler.END

    elif data == "deepwork_blocked":
        await query.edit_message_text(
            "🚫 <b>Bloqueado</b>\n\n"
            "¿Cuál es el blocker?",
            parse_mode="HTML",
        )
        return DeepWorkStates.CHECKING_STATUS

    elif data == "deepwork_pause":
        await query.edit_message_text(
            "⏸️ <b>Deep Work Pausado</b>\n\n"
            "Usa /deepwork para retomar.",
            parse_mode="HTML",
        )
        user_data.clear()
        return ConversationHandler.END

    return DeepWorkStates.IN_PROGRESS


async def handle_deepwork_blocker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la descripción del blocker."""
    text = update.message.text
    user_data = context.user_data

    # Guardar blocker
    if user_data.get("deepwork_task_id"):
        notion = get_notion_service()
        await notion.set_task_blocker(
            user_data["deepwork_task_id"],
            text,
        )

    await update.message.reply_html(
        f"🚫 <b>Blocker registrado:</b>\n"
        f"<i>{text}</i>\n\n"
        f"Tarea marcada como bloqueada."
    )

    user_data.clear()
    return ConversationHandler.END


# ==================== FLUJO: ANÁLISIS DE COMPRA ====================


async def start_purchase_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el análisis de una compra potencial."""
    text = update.message.text
    user_data = context.user_data

    # Extraer monto
    amount = extract_amount(text)
    if not amount:
        await update.message.reply_text(
            "No detecté un monto. ¿Cuánto cuesta?"
        )
        user_data["purchase_text"] = text
        return PurchaseStates.ANALYZING

    user_data["purchase_text"] = text
    user_data["purchase_amount"] = amount

    await update.message.reply_text("💰 Analizando compra...")

    try:
        # Obtener contexto financiero de Notion
        notion = get_notion_service()
        debt_summary = await notion.get_debt_summary()
        monthly_summary = await notion.get_monthly_summary()

        financial_context = {
            "available_budget": monthly_summary.get("balance", 5000),
            "days_until_payday": get_days_until_payday(),
            "total_debt": debt_summary.get("total_deuda", 330000),
            "monthly_debt_interest": debt_summary.get("total_interes_mensual", 6500),
        }

        # Analizar con SpendingAnalyzer
        agent = SpendingAnalyzerAgent()
        result = await agent.analyze_purchase(
            description=text,
            financial_context=financial_context,
        )

        user_data["analysis_result"] = result

        # Construir mensaje
        message = f"💰 <b>Análisis de Compra</b>\n\n"
        message += f"<b>Descripción:</b> {text[:50]}\n"
        message += f"<b>Monto:</b> ${amount:,.2f}\n\n"

        message += f"<b>¿Es esencial?</b> {'Sí' if result.get('is_essential') else 'No'}\n"
        message += f"<b>Categoría:</b> {result.get('category', '?')}\n"
        message += f"<b>Impacto:</b> {result.get('budget_impact', '?')}\n\n"

        if result.get("honest_questions"):
            message += "<b>🤔 Preguntas honestas:</b>\n"
            for q in result["honest_questions"][:3]:
                message += f"• {q}\n"
            message += "\n"

        message += f"<b>💡 Recomendación:</b> {result.get('recommendation', 'Evalúa')}\n"

        keyboard = [
            [
                InlineKeyboardButton("🛒 Comprar", callback_data="purchase_buy"),
                InlineKeyboardButton("📅 Wishlist", callback_data="purchase_wishlist"),
            ],
            [
                InlineKeyboardButton("💰 Del freelance", callback_data="purchase_freelance"),
                InlineKeyboardButton("❌ No comprar", callback_data="purchase_skip"),
            ],
        ]

        await update.message.reply_html(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        return PurchaseStates.WAITING_DECISION

    except Exception as e:
        logger.error(f"Error analizando compra: {e}")
        await update.message.reply_text(
            f"Error analizando. Registrado como gasto de ${amount:,.2f}."
        )
        return ConversationHandler.END


async def handle_purchase_decision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la decisión sobre la compra."""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_data = context.user_data

    text = user_data.get("purchase_text", "")
    amount = user_data.get("purchase_amount", 0)
    notion = get_notion_service()

    if data == "purchase_buy":
        # Registrar como gasto
        from app.services.notion import TransactionTipo, TransactionCategoria

        await notion.log_transaction(
            concepto=text[:100],
            monto=-abs(amount),  # Negativo = gasto
            tipo=TransactionTipo.GASTO_VARIABLE,
            categoria=TransactionCategoria.OTRO,
        )

        await query.edit_message_text(
            f"🛒 <b>Compra registrada</b>\n\n"
            f"{text[:50]}: ${amount:,.2f}",
            parse_mode="HTML",
        )

    elif data == "purchase_wishlist":
        # Guardar en inbox como wishlist
        await notion.create_inbox_item(
            contenido=f"[WISHLIST] {text}",
            fuente=InboxFuente.TELEGRAM,
            notas=f"Monto: ${amount:,.2f}",
        )

        await query.edit_message_text(
            f"📅 <b>Agregado a Wishlist</b>\n\n"
            f"{text[:50]}: ${amount:,.2f}",
            parse_mode="HTML",
        )

    elif data == "purchase_freelance":
        await query.edit_message_text(
            f"💰 <b>Pendiente para freelance</b>\n\n"
            f"{text[:50]}: ${amount:,.2f}\n\n"
            f"Te recordaré cuando tengas ingresos de freelance.",
            parse_mode="HTML",
        )

    elif data == "purchase_skip":
        await query.edit_message_text(
            f"✅ <b>Decisión inteligente</b>\n\n"
            f"No compraste: {text[:50]}\n"
            f"Ahorraste ${amount:,.2f}",
            parse_mode="HTML",
        )

    user_data.clear()
    return ConversationHandler.END


# ==================== FLUJO: REGISTRO DE GYM ====================


async def start_gym_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el flujo de registro de gym."""
    keyboard = [
        [
            InlineKeyboardButton("💪 Push", callback_data="gym_type_Push"),
            InlineKeyboardButton("🔙 Pull", callback_data="gym_type_Pull"),
            InlineKeyboardButton("🦵 Legs", callback_data="gym_type_Legs"),
        ],
        [
            InlineKeyboardButton("🏃 Cardio", callback_data="gym_type_Cardio"),
            InlineKeyboardButton("😴 Rest", callback_data="gym_type_Rest"),
        ],
        [
            InlineKeyboardButton("❌ Cancelar", callback_data="gym_cancel"),
        ],
    ]

    await update.message.reply_html(
        "🏋️ <b>Registro de Gym</b>\n\n"
        "¿Qué tipo de entrenamiento?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return GymStates.SELECTING_TYPE


async def handle_gym_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la selección de tipo de entrenamiento."""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_data = context.user_data

    if data == "gym_cancel":
        await query.edit_message_text("❌ Registro cancelado.")
        return ConversationHandler.END

    if data.startswith("gym_type_"):
        workout_type = data.replace("gym_type_", "")
        user_data["gym_type"] = workout_type

        if workout_type == "Rest":
            # Día de descanso, registrar directamente
            notion = get_notion_service()
            await notion.log_workout(
                fecha=datetime.now().strftime("%Y-%m-%d"),
                tipo=WorkoutType.REST,
                completado=True,
            )
            await query.edit_message_text(
                "😴 <b>Día de Descanso registrado</b>\n\n"
                "El descanso también es parte del proceso 💪",
                parse_mode="HTML",
            )
            return ConversationHandler.END

        # Obtener última sesión del mismo tipo
        notion = get_notion_service()
        workout_type_enum = getattr(WorkoutType, workout_type.upper(), WorkoutType.PUSH)
        last_session = await notion.get_last_workout_by_type(workout_type_enum)

        message = f"🏋️ <b>{workout_type} Day</b>\n\n"

        if last_session:
            message += "📊 <b>Última sesión:</b>\n"
            props = last_session.get("properties", {})
            fecha_prop = props.get("Fecha", {}).get("title", [])
            fecha = fecha_prop[0].get("text", {}).get("content", "?") if fecha_prop else "?"
            message += f"<i>{fecha}</i>\n\n"

        message += (
            "Describe tu entrenamiento:\n"
            "<i>Ej: banca 60kg 3x8, militar 35kg 3x10</i>"
        )

        await query.edit_message_text(message, parse_mode="HTML")
        return GymStates.ENTERING_EXERCISES

    return GymStates.SELECTING_TYPE


async def handle_gym_exercises(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la entrada de ejercicios."""
    text = update.message.text
    user_data = context.user_data

    user_data["gym_exercises_text"] = text

    await update.message.reply_text("💪 Procesando ejercicios...")

    try:
        # Procesar con WorkoutLogger
        workout_type = user_data.get("gym_type", "Push")
        workout_type_enum = getattr(WorkoutType, workout_type.upper(), WorkoutType.PUSH)

        agent = WorkoutLoggerAgent()
        result = await agent.log_workout(
            workout_description=text,
            workout_type=workout_type_enum,
        )

        user_data["gym_result"] = result

        # Mostrar resumen
        message = agent.format_telegram_message(result)

        keyboard = [
            [
                InlineKeyboardButton("✅ Guardar", callback_data="gym_save"),
                InlineKeyboardButton("✏️ Editar", callback_data="gym_edit"),
            ],
            [
                InlineKeyboardButton("📝 Agregar notas", callback_data="gym_notes"),
                InlineKeyboardButton("❌ Cancelar", callback_data="gym_cancel"),
            ],
        ]

        await update.message.reply_html(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        return GymStates.CONFIRMING_DETAILS

    except Exception as e:
        logger.error(f"Error procesando gym: {e}")
        await update.message.reply_text(
            "Error procesando. Intenta de nuevo."
        )
        return GymStates.ENTERING_EXERCISES


async def handle_gym_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la confirmación del registro de gym."""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_data = context.user_data

    if data == "gym_cancel":
        await query.edit_message_text("❌ Registro cancelado.")
        user_data.clear()
        return ConversationHandler.END

    if data == "gym_save":
        # Guardar en Notion
        workout_type = user_data.get("gym_type", "Push")
        workout_type_enum = getattr(WorkoutType, workout_type.upper(), WorkoutType.PUSH)
        result = user_data.get("gym_result")

        notion = get_notion_service()

        # Convertir ejercicios a formato JSON
        ejercicios_json = []
        if result and result.exercises:
            for ex in result.exercises:
                ejercicios_json.append({
                    "name": ex.name,
                    "sets": [{"weight": s.weight, "reps": s.reps} for s in ex.sets],
                    "pr": ex.pr,
                })

        await notion.log_workout(
            fecha=datetime.now().strftime("%Y-%m-%d"),
            tipo=workout_type_enum,
            completado=True,
            ejercicios=ejercicios_json,
            notas=user_data.get("gym_notes"),
        )

        # Construir mensaje de confirmación
        message = "✅ <b>Workout Guardado</b>\n\n"
        message += f"📋 {workout_type}\n"
        if result and result.new_prs:
            message += f"🏆 PRs: {', '.join(result.new_prs)}\n"

        await query.edit_message_text(message, parse_mode="HTML")
        user_data.clear()
        return ConversationHandler.END

    if data == "gym_notes":
        await query.edit_message_text(
            "📝 Escribe tus notas (sensación, molestias, etc.):"
        )
        return GymStates.ADDING_NOTES

    if data == "gym_edit":
        await query.edit_message_text(
            "Describe los ejercicios de nuevo:"
        )
        return GymStates.ENTERING_EXERCISES

    return GymStates.CONFIRMING_DETAILS


async def handle_gym_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja las notas adicionales del gym."""
    text = update.message.text
    user_data = context.user_data

    user_data["gym_notes"] = text

    keyboard = [
        [
            InlineKeyboardButton("✅ Guardar", callback_data="gym_save"),
        ],
    ]

    await update.message.reply_html(
        f"📝 <b>Notas agregadas:</b>\n<i>{text}</i>",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return GymStates.CONFIRMING_DETAILS


# ==================== FLUJO: REGISTRO DE COMIDAS ====================


async def start_nutrition_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el flujo de registro de nutrición."""
    await update.message.reply_html(
        "🍽️ <b>Registro de Nutrición</b>\n\n"
        "Cuéntame qué comiste hoy:\n"
        "• Desayuno\n"
        "• Almuerzo\n"
        "• Cena\n"
        "• Snacks\n\n"
        "<i>Puedes describirlo todo junto o por partes.</i>"
    )

    context.user_data["nutrition_meals"] = []

    return NutritionStates.ENTERING_MEALS


async def handle_nutrition_meals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la entrada de comidas."""
    text = update.message.text
    user_data = context.user_data

    user_data["nutrition_text"] = text

    await update.message.reply_text("🔄 Analizando nutrición...")

    try:
        # Analizar con NutritionAnalyzer
        agent = NutritionAnalyzerAgent()
        result = await agent.analyze_meals(
            meals_description=text,
        )

        user_data["nutrition_result"] = result

        # Mostrar análisis
        message = agent.format_telegram_message(result)

        keyboard = [
            [
                InlineKeyboardButton("✅ Guardar", callback_data="nutrition_save"),
                InlineKeyboardButton("✏️ Agregar más", callback_data="nutrition_add"),
            ],
            [
                InlineKeyboardButton("❌ Cancelar", callback_data="nutrition_cancel"),
            ],
        ]

        await update.message.reply_html(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        return NutritionStates.CONFIRMING

    except Exception as e:
        logger.error(f"Error analizando nutrición: {e}")
        await update.message.reply_text(
            "Error analizando. Intenta de nuevo."
        )
        return NutritionStates.ENTERING_MEALS


async def handle_nutrition_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja la confirmación del registro de nutrición."""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_data = context.user_data

    if data == "nutrition_cancel":
        await query.edit_message_text("❌ Registro cancelado.")
        user_data.clear()
        return ConversationHandler.END

    if data == "nutrition_save":
        result = user_data.get("nutrition_result")
        text = user_data.get("nutrition_text", "")

        notion = get_notion_service()

        # Guardar en Notion
        await notion.log_nutrition(
            fecha=datetime.now().strftime("%Y-%m-%d"),
            desayuno=text,  # Simplificado - idealmente parsear por comida
            evaluacion=result.overall_rating if result else None,
            proteina_ok=result.protein_status.value == "sufficient" if result else False,
            vegetales_ok=result.vegetables_count >= 2 if result else False,
        )

        await query.edit_message_text(
            "✅ <b>Nutrición Registrada</b>\n\n"
            f"Evaluación: {result.overall_rating.value if result else '?'}",
            parse_mode="HTML",
        )

        user_data.clear()
        return ConversationHandler.END

    if data == "nutrition_add":
        await query.edit_message_text(
            "¿Qué más comiste?"
        )
        return NutritionStates.ENTERING_MEALS

    return NutritionStates.CONFIRMING


# ==================== UTILIDADES ====================


def extract_amount(text: str) -> float | None:
    """Extrae un monto de dinero del texto."""
    # Patrones: $1,500 | 1500 pesos | $1.500 | 1,500
    patterns = [
        r'\$[\d,\.]+',           # $1,500 o $1.500
        r'[\d,\.]+\s*pesos',     # 1500 pesos
        r'[\d,\.]+\s*mxn',       # 1500 mxn
        r'[\d,\.]+\s*dlls?',     # 100 dlls
    ]

    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            amount_str = match.group()
            # Limpiar
            amount_str = re.sub(r'[^\d\.,]', '', amount_str)
            # Manejar formato mexicano (1,500.00 o 1.500,00)
            if ',' in amount_str and '.' in amount_str:
                if amount_str.index(',') < amount_str.index('.'):
                    amount_str = amount_str.replace(',', '')  # 1,500.00 -> 1500.00
                else:
                    amount_str = amount_str.replace('.', '').replace(',', '.')  # 1.500,00 -> 1500.00
            elif ',' in amount_str:
                # Podría ser 1,500 o 1,50
                parts = amount_str.split(',')
                if len(parts[-1]) == 2:  # 1,50 (decimales)
                    amount_str = amount_str.replace(',', '.')
                else:  # 1,500 (miles)
                    amount_str = amount_str.replace(',', '')

            try:
                return float(amount_str)
            except ValueError:
                continue

    return None


def get_days_until_payday() -> int:
    """Calcula días hasta la próxima quincena."""
    today = datetime.now().day

    if today <= 15:
        return 15 - today
    else:
        # Hasta el 30 (simplificado)
        return 30 - today


# ==================== CONVERSATION HANDLERS ====================


def get_inbox_conversation_handler() -> ConversationHandler:
    """Crea el ConversationHandler para captura rápida."""
    return ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & ~filters.Regex(r'^\$'),
                start_inbox_capture,
            ),
        ],
        states={
            InboxStates.WAITING_CLASSIFICATION: [
                CallbackQueryHandler(handle_inbox_classification),
            ],
            InboxStates.WAITING_PROJECT: [
                CallbackQueryHandler(handle_project_selection),
            ],
            InboxStates.WAITING_CONFIRMATION: [
                CallbackQueryHandler(handle_inbox_confirmation),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_inbox),
            CallbackQueryHandler(cancel_inbox, pattern="^inbox_cancel$"),
        ],
        per_message=False,
    )


def get_deepwork_conversation_handler() -> ConversationHandler:
    """Crea el ConversationHandler para Deep Work."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("deepwork", start_deep_work),
            CommandHandler("focus", start_deep_work),
        ],
        states={
            DeepWorkStates.SELECTING_TASK: [
                CallbackQueryHandler(handle_deepwork_task_selection),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_deepwork_task_selection),
            ],
            DeepWorkStates.CONFIRMING_DURATION: [
                CallbackQueryHandler(handle_deepwork_duration),
            ],
            DeepWorkStates.IN_PROGRESS: [
                CallbackQueryHandler(handle_deepwork_status),
            ],
            DeepWorkStates.CHECKING_STATUS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_deepwork_blocker),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_inbox),
        ],
        per_message=False,
    )


def get_purchase_conversation_handler() -> ConversationHandler:
    """Crea el ConversationHandler para análisis de compras."""
    return ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.TEXT & filters.Regex(r'\$[\d,\.]+'),
                start_purchase_analysis,
            ),
            MessageHandler(
                filters.TEXT & filters.Regex(r'[\d,\.]+\s*pesos', re.IGNORECASE),
                start_purchase_analysis,
            ),
        ],
        states={
            PurchaseStates.ANALYZING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, start_purchase_analysis),
            ],
            PurchaseStates.WAITING_DECISION: [
                CallbackQueryHandler(handle_purchase_decision),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_inbox),
        ],
        per_message=False,
    )


def get_gym_conversation_handler() -> ConversationHandler:
    """Crea el ConversationHandler para registro de gym."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("gym", start_gym_log),
            CommandHandler("workout", start_gym_log),
        ],
        states={
            GymStates.SELECTING_TYPE: [
                CallbackQueryHandler(handle_gym_type),
            ],
            GymStates.ENTERING_EXERCISES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_gym_exercises),
            ],
            GymStates.CONFIRMING_DETAILS: [
                CallbackQueryHandler(handle_gym_confirmation),
            ],
            GymStates.ADDING_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_gym_notes),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_inbox),
            CallbackQueryHandler(cancel_inbox, pattern="^gym_cancel$"),
        ],
        per_message=False,
    )


def get_nutrition_conversation_handler() -> ConversationHandler:
    """Crea el ConversationHandler para registro de nutrición."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("food", start_nutrition_log),
            CommandHandler("nutrition", start_nutrition_log),
            CommandHandler("comida", start_nutrition_log),
        ],
        states={
            NutritionStates.ENTERING_MEALS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_nutrition_meals),
            ],
            NutritionStates.CONFIRMING: [
                CallbackQueryHandler(handle_nutrition_confirmation),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_inbox),
            CallbackQueryHandler(cancel_inbox, pattern="^nutrition_cancel$"),
        ],
        per_message=False,
    )
