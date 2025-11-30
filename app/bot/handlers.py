"""Handlers del bot de Telegram."""

import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.bot.keyboards import (
    main_menu_keyboard,
    task_actions_keyboard,
    task_priority_keyboard,
    confirm_keyboard,
)
from app.bot.conversations import (
    get_inbox_conversation_handler,
    get_deepwork_conversation_handler,
    get_purchase_conversation_handler,
    get_gym_conversation_handler,
    get_nutrition_conversation_handler,
)
from app.config import get_settings
from app.services.notion import get_notion_service, TaskEstado, TaskPrioridad

logger = logging.getLogger(__name__)
settings = get_settings()

# Application singleton
_application: Application | None = None
_initialized: bool = False


# ==================== COMMAND HANDLERS ====================


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /start."""
    user = update.effective_user
    await update.message.reply_html(
        f"Hola <b>{user.first_name}</b>! Soy Carlos Command.\n\n"
        "Tu asistente personal para gestión de vida.\n\n"
        "<b>Comandos disponibles:</b>\n"
        "/today - Tareas de hoy\n"
        "/add [tarea] - Agregar tarea rápida\n"
        "/doing - Marcar tarea en progreso\n"
        "/done - Completar tarea actual\n"
        "/status - Estado del sistema\n"
        "/help - Ver ayuda completa",
        reply_markup=main_menu_keyboard(),
    )
    logger.info(f"Usuario {user.id} ejecutó /start")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /help."""
    await update.message.reply_html(
        "<b>Ayuda - Carlos Command</b>\n\n"
        "Puedes enviarme mensajes y los procesaré automáticamente.\n\n"
        "<b>Comandos de Tareas:</b>\n"
        "/today - Ver tareas para hoy\n"
        "/add [tarea] - Agregar tarea rápida\n"
        "/doing [tarea] - Marcar en progreso\n"
        "/done - Completar tarea actual\n"
        "/block [razón] - Marcar como bloqueada\n\n"
        "<b>Otros:</b>\n"
        "/status - Estado del sistema\n"
        "/inbox - Ver inbox pendiente\n"
        "/projects - Listar proyectos\n\n"
        "<b>Tips:</b>\n"
        "• Envía cualquier texto para capturarlo en el inbox\n"
        "• Menciona un precio ($) para análisis de compra\n"
        "• Di 'gym' para registrar tu workout"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /status."""
    notion = get_notion_service()

    # Test conexión Notion
    notion_status = "✅ Conectado" if await notion.test_connection() else "❌ Error"

    await update.message.reply_html(
        "<b>Estado del Sistema</b>\n\n"
        f"<b>Entorno:</b> {settings.app_env}\n"
        f"<b>Bot:</b> ✅ Online\n"
        f"<b>Notion:</b> {notion_status}\n"
        f"<b>Hora:</b> {datetime.now().strftime('%H:%M:%S')}"
    )


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /today - muestra tareas de hoy."""
    await update.message.reply_text("Obteniendo tareas de hoy...")

    notion = get_notion_service()
    tasks = await notion.get_tasks_for_today()

    if not tasks:
        await update.message.reply_html(
            "📋 <b>Tareas de hoy</b>\n\n"
            "No hay tareas programadas para hoy.\n\n"
            "Usa /add [tarea] para agregar una."
        )
        return

    # Formatear tareas
    message = "📋 <b>Tareas de hoy</b>\n\n"
    for i, task in enumerate(tasks, 1):
        props = task.get("properties", {})
        # Campo correcto: "Tarea" (Title)
        title_prop = props.get("Tarea", {}).get("title", [])
        task_name = title_prop[0].get("text", {}).get("content", "Sin título") if title_prop else "Sin título"

        # Campo correcto: "Estado" (Select)
        estado_prop = props.get("Estado", {}).get("select", {})
        estado = estado_prop.get("name", "?") if estado_prop else "?"

        # Campo correcto: "Prioridad" (Select)
        prioridad_prop = props.get("Prioridad", {}).get("select", {})
        prioridad = prioridad_prop.get("name", "") if prioridad_prop else ""

        # Emojis según estado
        status_emoji = {
            "📥 Backlog": "⬜",
            "📋 Planned": "📋",
            "🎯 Today": "🎯",
            "⚡ Doing": "🔵",
            "⏸️ Paused": "⏸️",
            "✅ Done": "✅",
            "❌ Cancelled": "❌",
        }.get(estado, "⬜")

        message += f"{status_emoji} {task_name}\n"

    await update.message.reply_html(message)


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /add - agrega una tarea rápida."""
    if not context.args:
        await update.message.reply_html(
            "Uso: /add [descripción de la tarea]\n\n"
            "Ejemplo: /add Revisar emails"
        )
        return

    task_title = " ".join(context.args)
    await update.message.reply_text(f"Creando tarea: {task_title}...")

    notion = get_notion_service()
    result = await notion.create_task(
        tarea=task_title,
        estado=TaskEstado.BACKLOG,
    )

    if result:
        task_id = result.get("id", "")
        await update.message.reply_html(
            f"✅ Tarea creada: <b>{task_title}</b>\n\n"
            "¿Qué prioridad tiene?",
            reply_markup=task_priority_keyboard(task_id[:8]),
        )
    else:
        await update.message.reply_text(
            "❌ Error creando la tarea. Intenta de nuevo."
        )


async def doing_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /doing - marca tarea en progreso."""
    if context.args:
        # Si se especifica una tarea, buscarla
        task_name = " ".join(context.args)
        await update.message.reply_text(
            f"Buscando tarea: {task_name}...\n"
            "(Funcionalidad de búsqueda próximamente)"
        )
    else:
        # Mostrar tareas pendientes para seleccionar
        notion = get_notion_service()
        tasks = await notion.get_pending_tasks(limit=5)

        if not tasks:
            await update.message.reply_text(
                "No hay tareas pendientes. Usa /add para crear una."
            )
            return

        message = "Selecciona la tarea que vas a empezar:\n\n"
        for i, task in enumerate(tasks, 1):
            props = task.get("properties", {})
            title_prop = props.get("Tarea", {}).get("title", [])
            task_name = title_prop[0].get("text", {}).get("content", "Sin título") if title_prop else "Sin título"
            message += f"{i}. {task_name}\n"

        await update.message.reply_text(message)


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /done - completa la tarea actual."""
    # Por ahora, mostrar mensaje básico
    await update.message.reply_html(
        "✅ <b>Marcar como completada</b>\n\n"
        "(En desarrollo: se mostrará la tarea en progreso actual)"
    )


async def block_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /block - marca tarea como bloqueada."""
    reason = " ".join(context.args) if context.args else None

    message = "🚫 <b>Marcar como bloqueada</b>\n\n"
    if reason:
        message += f"Razón: {reason}\n\n"
    message += "(En desarrollo: se mostrará la tarea en progreso actual)"

    await update.message.reply_html(message)


async def inbox_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /inbox - muestra items del inbox."""
    notion = get_notion_service()
    items = await notion.get_inbox_items(limit=10)

    if not items:
        await update.message.reply_html(
            "📥 <b>Inbox</b>\n\n"
            "Tu inbox está vacío."
        )
        return

    message = "📥 <b>Inbox</b>\n\n"
    for item in items:
        props = item.get("properties", {})
        # Campo correcto: "Contenido" (Title)
        title_prop = props.get("Contenido", {}).get("title", [])
        item_name = title_prop[0].get("text", {}).get("content", "Sin título") if title_prop else "Sin título"
        message += f"• {item_name}\n"

    await update.message.reply_html(message)


async def projects_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para el comando /projects - lista proyectos."""
    notion = get_notion_service()
    projects = await notion.get_projects(active_only=True)

    if not projects:
        await update.message.reply_html(
            "📁 <b>Proyectos</b>\n\n"
            "No hay proyectos activos."
        )
        return

    message = "📁 <b>Proyectos Activos</b>\n\n"
    for project in projects:
        props = project.get("properties", {})
        # Campo correcto: "Proyecto" (Title)
        title_prop = props.get("Proyecto", {}).get("title", [])
        project_name = title_prop[0].get("text", {}).get("content", "Sin título") if title_prop else "Sin título"
        message += f"• {project_name}\n"

    await update.message.reply_html(message)


# ==================== VOICE HANDLER ====================


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler para mensajes de voz.
    Transcribe el audio y lo procesa como mensaje de texto.
    """
    try:
        voice = update.message.voice or update.message.audio
        if not voice:
            await update.message.reply_text("No se detectó audio en el mensaje.")
            return

        user = update.effective_user
        logger.info(f"Mensaje de voz de {user.id}, duración: {voice.duration}s")

        # Notificar que estamos procesando
        processing_msg = await update.message.reply_text(
            "Transcribiendo audio...",
        )

        # Procesar voz
        from app.services.telegram import get_telegram_service

        telegram_service = get_telegram_service()
        result = await telegram_service.process_voice_message(voice)

        if result["status"] != "success":
            await processing_msg.edit_text(
                f"No se pudo transcribir el audio: {result.get('error', 'Error desconocido')}"
            )
            return

        transcription = result["transcription"]

        # Mostrar transcripción
        await processing_msg.edit_text(
            f"Transcripción:\n<i>{transcription}</i>\n\n"
            "Procesando mensaje...",
            parse_mode="HTML",
        )

        # Procesar como mensaje de texto normal
        # Crear un update simulado con el texto transcrito
        update.message.text = transcription
        await handle_message(update, context)

    except Exception as e:
        logger.exception(f"Error procesando mensaje de voz: {e}")
        await update.message.reply_text(
            "Hubo un error procesando tu mensaje de voz. Por favor intenta de nuevo."
        )


# ==================== MESSAGE HANDLERS ====================


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler principal para mensajes de texto.
    Usa ConversationalOrchestrator para mantener contexto y coordinar agentes.
    """
    try:
        text = update.message.text
        user = update.effective_user
        user_id = user.id

        logger.info(f"Mensaje de {user_id}: {text[:50]}...")

        # Intentar usar ConversationalOrchestrator primero
        try:
            from app.agents.conversational_orchestrator import get_conversational_orchestrator

            orchestrator = get_conversational_orchestrator()
            response = await orchestrator.process_message(user_id=user_id, message=text)

            # Si es respuesta contextual, manejarla directamente
            if response.is_contextual or response.keyboard_options:
                # Construir teclado si hay opciones
                keyboard = None
                if response.keyboard_options:
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(opt["text"], callback_data=opt["callback"]) for opt in row]
                        for row in response.keyboard_options
                    ])

                await update.message.reply_html(
                    response.message,
                    reply_markup=keyboard,
                )
                return

            # Si no es contextual, usar el routing tradicional con el intent detectado
            from app.agents.intent_router import UserIntent, IntentResult

            # Crear IntentResult compatible
            intent_result = IntentResult(
                intent=response.intent,
                confidence=0.8,
                entities={},
                suggested_response=None,
                raw_message=text,
            )

            await route_by_intent(update, context, intent_result)
            return

        except Exception as e:
            logger.warning(f"ConversationalOrchestrator falló, usando fallback: {e}")
            # Continuar con el flujo tradicional

        # Fallback: Usar IntentRouter directamente
        from app.agents.intent_router import get_intent_router, UserIntent

        router = get_intent_router()

        # Obtener contexto de conversación si existe
        conversation_context = context.user_data.get("last_messages", "")

        # Clasificar intención con AI
        try:
            intent_result = await router.execute(text, conversation_context)
        except Exception as e:
            logger.exception(f"Error en IntentRouter, usando fallback: {e}")
            intent_result = await router.get_fallback_intent(text)

        # Guardar mensaje en contexto para futuras clasificaciones
        last_messages = context.user_data.get("last_messages_list", [])
        last_messages.append(text[:100])
        if len(last_messages) > 5:
            last_messages = last_messages[-5:]
        context.user_data["last_messages_list"] = last_messages
        context.user_data["last_messages"] = " | ".join(last_messages)

        # Log de la clasificación
        logger.info(
            f"Intent: {intent_result.intent.value}, "
            f"Confidence: {intent_result.confidence:.2f}, "
            f"Entities: {intent_result.entities}"
        )

        # Enrutar según la intención
        await route_by_intent(update, context, intent_result)
    except Exception as e:
        logger.exception(f"Error en handle_message: {e}")
        await update.message.reply_text(
            "Ocurrió un error procesando tu mensaje. Por favor intenta de nuevo."
        )


async def route_by_intent(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    intent_result
) -> None:
    """Enruta el mensaje al handler correcto según la intención."""
    from app.agents.intent_router import UserIntent
    from app.services.notion import InboxFuente

    intent = intent_result.intent
    entities = intent_result.entities
    confidence = intent_result.confidence
    text = intent_result.raw_message

    # ==================== SALUDOS Y AYUDA ====================
    if intent == UserIntent.GREETING:
        response = intent_result.suggested_response or "¡Hola! ¿En qué te puedo ayudar hoy?"
        await update.message.reply_text(response)
        return

    if intent == UserIntent.HELP:
        await help_command(update, context)
        return

    if intent == UserIntent.STATUS:
        await status_command(update, context)
        return

    # ==================== TAREAS ====================
    if intent == UserIntent.TASK_CREATE:
        # Extraer título de la tarea
        task_title = entities.get("task", text[:100])

        await update.message.reply_html(
            f"📋 <b>Nueva tarea detectada</b>\n\n"
            f"<i>{task_title}</i>\n\n"
            f"Confianza: {confidence:.0%}",
            reply_markup=confirm_keyboard(
                confirm_data=f"task_create:{task_title[:50]}",
                cancel_data="task_cancel",
                confirm_text="✅ Crear tarea",
                cancel_text="📥 Guardar en Inbox",
            ),
        )
        # Guardar en context para cuando confirme
        context.user_data["pending_task"] = task_title
        return

    if intent == UserIntent.TASK_QUERY:
        await today_command(update, context)
        return

    if intent == UserIntent.TASK_DELETE:
        # Buscar la tarea mencionada y ofrecer completarla/eliminarla
        task_name = entities.get("task", text)
        notion = get_notion_service()

        # Buscar tareas que coincidan
        tasks = await notion.get_pending_tasks(limit=10)
        matching_tasks = []

        for task in tasks:
            props = task.get("properties", {})
            title_prop = props.get("Tarea", {}).get("title", [])
            title = title_prop[0].get("text", {}).get("content", "") if title_prop else ""

            # Buscar coincidencia parcial
            if task_name.lower() in title.lower() or title.lower() in task_name.lower():
                matching_tasks.append({
                    "id": task.get("id"),
                    "title": title,
                })

        if matching_tasks:
            keyboard = []
            for task in matching_tasks[:5]:
                short_id = task["id"][:8]
                keyboard.append([
                    InlineKeyboardButton(
                        f"✅ {task['title'][:30]}",
                        callback_data=f"task_complete:{short_id}",
                    ),
                ])
            keyboard.append([
                InlineKeyboardButton("❌ Cancelar", callback_data="task_delete_cancel"),
            ])

            await update.message.reply_html(
                f"📋 <b>Completar/Eliminar tarea</b>\n\n"
                f"Encontré estas tareas que coinciden con \"{task_name[:30]}\":\n\n"
                f"Selecciona la que quieres marcar como completada:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            context.user_data["pending_delete_tasks"] = matching_tasks
        else:
            await update.message.reply_html(
                f"🔍 No encontré tareas que coincidan con:\n"
                f"<i>{task_name[:50]}</i>\n\n"
                f"Usa /today para ver tus tareas pendientes."
            )
        return

    # ==================== RECORDATORIOS ====================
    if intent == UserIntent.REMINDER_CREATE:
        # Extraer información del recordatorio
        reminder_text = entities.get("reminder", text)
        reminder_time = entities.get("time", "")
        reminder_date = entities.get("date", "")

        # Guardar en context
        context.user_data["pending_reminder"] = {
            "text": reminder_text,
            "time": reminder_time,
            "date": reminder_date,
        }

        # Si no hay tiempo especificado, preguntar
        if not reminder_time and not reminder_date:
            keyboard = [
                [
                    InlineKeyboardButton("⏰ 30 min", callback_data="reminder_time:30m"),
                    InlineKeyboardButton("⏰ 1 hora", callback_data="reminder_time:1h"),
                ],
                [
                    InlineKeyboardButton("⏰ 3 horas", callback_data="reminder_time:3h"),
                    InlineKeyboardButton("📅 Mañana 9AM", callback_data="reminder_time:tomorrow"),
                ],
                [
                    InlineKeyboardButton("✏️ Personalizado", callback_data="reminder_time:custom"),
                ],
                [
                    InlineKeyboardButton("❌ Cancelar", callback_data="reminder_cancel"),
                ],
            ]

            await update.message.reply_html(
                f"⏰ <b>Crear Recordatorio</b>\n\n"
                f"<i>{reminder_text[:100]}</i>\n\n"
                f"¿Cuándo quieres que te recuerde?",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            # Crear el recordatorio directamente
            from datetime import timedelta

            await update.message.reply_html(
                f"⏰ <b>Recordatorio creado</b>\n\n"
                f"<i>{reminder_text[:100]}</i>\n\n"
                f"Te recordaré: {reminder_time or reminder_date or 'pronto'}",
            )
            # TODO: Integrar con scheduler para crear recordatorio real
        return

    if intent == UserIntent.REMINDER_QUERY:
        await update.message.reply_html(
            "⏰ <b>Tus Recordatorios</b>\n\n"
            "(Funcionalidad de listar recordatorios próximamente)"
        )
        return

    # ==================== FINANZAS ====================
    if intent == UserIntent.EXPENSE_ANALYZE:
        amount = entities.get("amount", "?")
        item = entities.get("item", text[:50])

        await update.message.reply_html(
            f"💰 <b>Análisis de compra</b>\n\n"
            f"Item: <i>{item}</i>\n"
            f"Precio: ${amount}\n\n"
            f"Analizando si es buena idea...",
        )

        # TODO: Llamar a SpendingAnalyzer
        # Por ahora, mostrar mensaje de placeholder
        await update.message.reply_html(
            "🤔 <b>Preguntas para reflexionar:</b>\n\n"
            "• ¿Realmente lo necesitas o solo lo quieres?\n"
            "• ¿Tienes algo similar que cumpla la función?\n"
            "• ¿Cómo te sentirías en una semana si no lo compras?\n\n"
            "<i>(SpendingAnalyzer completo próximamente)</i>"
        )
        return

    if intent == UserIntent.EXPENSE_LOG:
        amount = entities.get("amount", "?")

        await update.message.reply_html(
            f"💸 <b>Registrar gasto</b>\n\n"
            f"<i>{text}</i>\n"
            f"Monto detectado: ${amount}\n\n"
            "¿Confirmar registro?",
            reply_markup=confirm_keyboard(
                confirm_data="expense_log",
                cancel_data="expense_cancel",
            ),
        )
        context.user_data["pending_expense"] = {
            "text": text,
            "amount": amount,
        }
        return

    if intent == UserIntent.DEBT_QUERY:
        notion = get_notion_service()
        summary = await notion.get_debt_summary()

        if summary and summary.get("deudas"):
            msg = "💳 <b>Resumen de Deudas</b>\n\n"
            for debt in summary["deudas"]:
                msg += f"• {debt['nombre']}: ${debt['monto']:,.0f}\n"
            msg += f"\n<b>Total:</b> ${summary['total_deuda']:,.0f}"
            msg += f"\n<b>Pago mínimo mensual:</b> ${summary['total_pago_minimo']:,.0f}"
        else:
            msg = "💳 No tienes deudas registradas. ¡Excelente!"

        await update.message.reply_html(msg)
        return

    # ==================== FITNESS ====================
    if intent == UserIntent.GYM_LOG:
        await update.message.reply_html(
            f"💪 <b>Registrar workout</b>\n\n"
            f"<i>{text}</i>\n\n"
            "¿Qué tipo de entrenamiento hiciste?",
            reply_markup=workout_type_keyboard(),
        )
        context.user_data["pending_workout"] = text
        return

    if intent == UserIntent.GYM_QUERY:
        notion = get_notion_service()
        history = await notion.get_workout_history(weeks=2)

        if history:
            msg = "🏋️ <b>Últimos workouts</b>\n\n"
            for w in history[:7]:
                props = w.get("properties", {})
                fecha = props.get("Fecha", {}).get("title", [{}])[0].get("text", {}).get("content", "?")
                tipo = props.get("Tipo", {}).get("select", {}).get("name", "?")

                # Obtener ejercicios y pesos
                ejercicios_raw = props.get("Ejercicios", {}).get("rich_text", [])
                ejercicios_text = ejercicios_raw[0].get("text", {}).get("content", "") if ejercicios_raw else ""

                # Obtener PRs si hay
                prs_raw = props.get("PRs", {}).get("rich_text", [])
                prs_text = prs_raw[0].get("text", {}).get("content", "") if prs_raw else ""

                msg += f"<b>{fecha}</b> - {tipo}\n"

                # Parsear ejercicios si es JSON
                if ejercicios_text:
                    try:
                        import json
                        ejercicios_data = json.loads(ejercicios_text)
                        exercises = ejercicios_data.get("exercises", [])
                        for ex in exercises[:3]:  # Mostrar máximo 3 ejercicios
                            ex_name = ex.get("name", ex.get("exercise", "?"))
                            ex_weight = ex.get("weight", ex.get("peso", ""))
                            ex_reps = ex.get("reps", ex.get("reps", ""))
                            ex_sets = ex.get("sets", ex.get("series", ""))

                            detail = f"  • {ex_name}"
                            if ex_weight:
                                detail += f" - {ex_weight}kg"
                            if ex_sets and ex_reps:
                                detail += f" ({ex_sets}x{ex_reps})"
                            msg += f"{detail}\n"
                    except json.JSONDecodeError:
                        # No es JSON, mostrar como texto
                        msg += f"  {ejercicios_text[:50]}\n"

                if prs_text:
                    msg += f"  🏆 PRs: {prs_text}\n"

                msg += "\n"
        else:
            msg = "🏋️ No hay workouts registrados aún."

        await update.message.reply_html(msg)
        return

    # ==================== NUTRICIÓN ====================
    if intent == UserIntent.NUTRITION_LOG:
        meal = entities.get("meal", "comida")
        food = entities.get("food", text)

        # Mostrar que estamos procesando
        processing_msg = await update.message.reply_html(
            f"🍽️ <b>Analizando {meal}...</b>\n\n"
            f"<i>{food}</i>\n\n"
            "⏳ Estimando calorías con AI..."
        )

        try:
            # Usar AI para estimar calorías
            import dspy
            from app.agents.base import setup_dspy, EstimateMealCalories

            setup_dspy()
            estimator = dspy.ChainOfThought(EstimateMealCalories)

            result = estimator(
                meal_description=food,
                meal_type=meal,
            )

            # Parsear resultados
            try:
                calories = int(result.calories)
            except (ValueError, TypeError):
                calories = 500  # Default

            try:
                protein = int(result.protein_grams)
            except (ValueError, TypeError):
                protein = 0

            category_str = str(result.category).lower()
            feedback = str(result.feedback)

            # Mapear categoría
            from app.services.notion import NutritionCategoria
            category_map = {
                "saludable": NutritionCategoria.SALUDABLE,
                "moderado": NutritionCategoria.MODERADO,
                "pesado": NutritionCategoria.PESADO,
            }
            category = category_map.get(category_str, NutritionCategoria.MODERADO)

            # Guardar en Notion
            from datetime import datetime
            fecha = datetime.now().strftime("%Y-%m-%d")

            notion = get_notion_service()
            result_notion = await notion.update_meal(
                fecha=fecha,
                meal_type=meal,
                description=food,
                calories=calories,
                category=category,
            )

            # Emoji según categoría
            cat_emoji = {
                "saludable": "🟢",
                "moderado": "🟡",
                "pesado": "🔴",
            }.get(category_str, "🟡")

            if result_notion:
                await processing_msg.edit_text(
                    f"✅ <b>{meal.capitalize()} registrado</b>\n\n"
                    f"<i>{food}</i>\n\n"
                    f"📊 <b>Estimación AI:</b>\n"
                    f"• Calorías: ~{calories} kcal\n"
                    f"• Proteína: ~{protein}g\n"
                    f"• Categoría: {cat_emoji} {category_str.capitalize()}\n\n"
                    f"💡 {feedback}",
                    parse_mode="HTML",
                )
            else:
                await processing_msg.edit_text(
                    f"⚠️ <b>{meal.capitalize()} analizado</b>\n\n"
                    f"<i>{food}</i>\n\n"
                    f"📊 <b>Estimación AI:</b>\n"
                    f"• Calorías: ~{calories} kcal\n"
                    f"• Proteína: ~{protein}g\n"
                    f"• Categoría: {cat_emoji} {category_str.capitalize()}\n\n"
                    f"⚠️ No se pudo guardar en Notion\n\n"
                    f"💡 {feedback}",
                    parse_mode="HTML",
                )

        except Exception as e:
            logger.error(f"Error estimando calorías: {e}")
            # Fallback: preguntar categoría manual
            await processing_msg.edit_text(
                f"🍽️ <b>Registrar {meal}</b>\n\n"
                f"<i>{food}</i>\n\n"
                "No pude estimar las calorías. ¿Cómo categorizarías esta comida?",
                parse_mode="HTML",
                reply_markup=nutrition_category_keyboard(),
            )
            context.user_data["pending_nutrition"] = {
                "meal": meal,
                "food": food,
            }
        return

    if intent == UserIntent.NUTRITION_QUERY:
        notion = get_notion_service()
        history = await notion.get_nutrition_history(days=7)

        if history:
            msg = "🥗 <b>Nutrición últimos días</b>\n\n"
            for n in history[:5]:
                props = n.get("properties", {})
                fecha = props.get("Fecha", {}).get("title", [{}])[0].get("text", {}).get("content", "?")
                evaluacion = props.get("Evaluación", {}).get("select", {}).get("name", "?")
                msg += f"• {fecha}: {evaluacion}\n"
        else:
            msg = "🥗 No hay registros de nutrición aún."

        await update.message.reply_html(msg)
        return

    # ==================== ESTUDIO ====================
    if intent == UserIntent.STUDY_SESSION:
        await update.message.reply_html(
            "📚 <b>Sesión de estudio</b>\n\n"
            "¿En qué proyecto quieres enfocarte?\n\n"
            "(Deep Work session próximamente)"
        )
        return

    # ==================== IDEAS Y NOTAS ====================
    if intent in [UserIntent.IDEA, UserIntent.NOTE]:
        tipo = "idea" if intent == UserIntent.IDEA else "nota"
        emoji = "💡" if intent == UserIntent.IDEA else "📝"

        notion = get_notion_service()
        from app.services.notion import KnowledgeTipo

        knowledge_tipo = KnowledgeTipo.IDEA if intent == UserIntent.IDEA else KnowledgeTipo.NOTA

        result = await notion.create_knowledge(
            titulo=text[:100],
            contenido=text,
            tipo=knowledge_tipo,
        )

        if result:
            await update.message.reply_html(
                f"{emoji} <b>{tipo.capitalize()} guardada</b>\n\n"
                f"<i>{text[:150]}{'...' if len(text) > 150 else ''}</i>"
            )
        else:
            await update.message.reply_text(f"❌ Error guardando {tipo}.")
        return

    # ==================== PROYECTOS ====================
    if intent == UserIntent.PROJECT_CREATE:
        # Extraer nombre y tipo del proyecto
        project_name = entities.get("project_name", "")
        project_type = entities.get("project_type", "")

        if not project_name:
            # Si no se extrajo el nombre, usar el texto como nombre
            # Limpiar prefijos comunes
            import re
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

        # Si ya tenemos el tipo, mostrar confirmación directa
        if project_type:
            type_labels = {
                "trabajo": "💼 Trabajo",
                "freelance": "💰 Freelance",
                "personal": "🏠 Personal",
                "estudio": "📚 Estudio/Aprendizaje",
                "side_project": "🚀 Side Project",
            }

            await update.message.reply_html(
                f"📁 <b>Nuevo Proyecto</b>\n\n"
                f"<b>Nombre:</b> {project_name}\n"
                f"<b>Tipo detectado:</b> {type_labels.get(project_type, project_type)}\n"
                f"<b>Confianza:</b> {confidence:.0%}\n\n"
                f"¿Confirmar creación?",
                reply_markup=confirm_keyboard(
                    confirm_data="project_create",
                    cancel_data="project_cancel",
                    confirm_text="✅ Crear proyecto",
                    cancel_text="❌ Cancelar",
                ),
            )
        else:
            # Preguntar tipo de proyecto
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

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

            await update.message.reply_html(
                f"📁 <b>Nuevo Proyecto</b>\n\n"
                f"<b>Nombre:</b> {project_name}\n\n"
                f"¿Qué tipo de proyecto es?",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        return

    if intent == UserIntent.PROJECT_QUERY:
        await projects_command(update, context)
        return

    if intent == UserIntent.PROJECT_UPDATE:
        # Buscar proyecto para actualizar
        project_name = entities.get("project_name", text)
        notion = get_notion_service()

        projects = await notion.get_projects(active_only=True)
        matching_projects = []

        for project in projects:
            props = project.get("properties", {})
            title_prop = props.get("Proyecto", {}).get("title", [])
            title = title_prop[0].get("text", {}).get("content", "") if title_prop else ""

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
                InlineKeyboardButton("❌ Cancelar", callback_data="project_update_cancel"),
            ])

            await update.message.reply_html(
                f"📁 <b>Editar Proyecto</b>\n\n"
                f"Selecciona el proyecto que quieres editar:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            context.user_data["pending_edit_projects"] = matching_projects
        else:
            await update.message.reply_html(
                f"🔍 No encontré proyectos que coincidan con:\n"
                f"<i>{project_name[:50]}</i>\n\n"
                f"Usa /projects para ver tus proyectos."
            )
        return

    if intent == UserIntent.PROJECT_DELETE:
        # Buscar proyecto para eliminar/archivar
        project_name = entities.get("project_name", text)
        notion = get_notion_service()

        projects = await notion.get_projects(active_only=True)
        matching_projects = []

        for project in projects:
            props = project.get("properties", {})
            title_prop = props.get("Proyecto", {}).get("title", [])
            title = title_prop[0].get("text", {}).get("content", "") if title_prop else ""

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
                        f"📦 Archivar: {proj['title'][:25]}",
                        callback_data=f"project_archive:{short_id}",
                    ),
                ])
            keyboard.append([
                InlineKeyboardButton("❌ Cancelar", callback_data="project_delete_cancel"),
            ])

            await update.message.reply_html(
                f"📁 <b>Archivar/Cerrar Proyecto</b>\n\n"
                f"Selecciona el proyecto que quieres archivar:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            context.user_data["pending_delete_projects"] = matching_projects
        else:
            await update.message.reply_html(
                f"🔍 No encontré proyectos activos que coincidan con:\n"
                f"<i>{project_name[:50]}</i>\n\n"
                f"Usa /projects para ver tus proyectos."
            )
        return

    # ==================== PLANIFICACIÓN ====================
    if intent == UserIntent.PLAN_TOMORROW:
        await handle_plan_tomorrow(update, context, text)
        return

    if intent == UserIntent.PLAN_WEEK:
        await handle_plan_week(update, context)
        return

    if intent == UserIntent.WORKLOAD_CHECK:
        await handle_workload_check(update, context)
        return

    if intent == UserIntent.PRIORITIZE:
        await handle_prioritize(update, context, text, entities)
        return

    if intent == UserIntent.RESCHEDULE:
        await handle_reschedule_request(update, context, text, entities)
        return

    if intent == UserIntent.TASK_UPDATE:
        # Buscar tarea para actualizar
        task_name = entities.get("task", text)
        notion = get_notion_service()

        tasks = await notion.get_pending_tasks(limit=10)
        matching_tasks = []

        for task in tasks:
            props = task.get("properties", {})
            title_prop = props.get("Tarea", {}).get("title", [])
            title = title_prop[0].get("text", {}).get("content", "") if title_prop else ""

            if task_name.lower() in title.lower() or title.lower() in task_name.lower():
                matching_tasks.append({
                    "id": task.get("id"),
                    "title": title,
                })

        if matching_tasks:
            keyboard = []
            for task in matching_tasks[:5]:
                short_id = task["id"][:8]
                keyboard.append([
                    InlineKeyboardButton(
                        f"✏️ {task['title'][:30]}",
                        callback_data=f"task_edit:{short_id}",
                    ),
                ])
            keyboard.append([
                InlineKeyboardButton("❌ Cancelar", callback_data="task_update_cancel"),
            ])

            await update.message.reply_html(
                f"📋 <b>Editar Tarea</b>\n\n"
                f"Selecciona la tarea que quieres editar:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            context.user_data["pending_edit_tasks"] = matching_tasks
        else:
            await update.message.reply_html(
                f"🔍 No encontré tareas que coincidan con:\n"
                f"<i>{task_name[:50]}</i>\n\n"
                f"Usa /today para ver tus tareas."
            )
        return

    # ==================== FALLBACK: INBOX ====================
    # Si no se reconoce o es UNKNOWN, guardar en inbox
    notion = get_notion_service()
    result = await notion.create_inbox_item(
        contenido=text[:200],
        fuente=InboxFuente.TELEGRAM,
        notas=f"Intent: {intent.value} (confidence: {confidence:.2f})" if confidence < 0.5 else None,
    )

    if result:
        if confidence < 0.5:
            # Baja confianza, preguntar
            await update.message.reply_html(
                f"🤔 No estoy seguro de qué quieres hacer.\n\n"
                f"<i>{text[:100]}{'...' if len(text) > 100 else ''}</i>\n\n"
                f"Lo guardé en tu Inbox. ¿Qué quieres hacer?",
                reply_markup=intent_clarification_keyboard(),
            )
        else:
            await update.message.reply_html(
                f"📥 <b>Guardado en Inbox</b>\n\n"
                f"<i>{text[:100]}{'...' if len(text) > 100 else ''}</i>",
                reply_markup=confirm_keyboard(
                    confirm_data="inbox_classify",
                    cancel_data="inbox_done",
                    confirm_text="🤖 Clasificar con AI",
                    cancel_text="✅ Listo",
                ),
            )
    else:
        await update.message.reply_text("❌ Error guardando en inbox. Intenta de nuevo.")


def workout_type_keyboard():
    """Teclado para seleccionar tipo de workout."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = [
        [
            InlineKeyboardButton("💪 Push", callback_data="workout_type:push"),
            InlineKeyboardButton("🏋️ Pull", callback_data="workout_type:pull"),
        ],
        [
            InlineKeyboardButton("🦵 Legs", callback_data="workout_type:legs"),
            InlineKeyboardButton("🏃 Cardio", callback_data="workout_type:cardio"),
        ],
        [
            InlineKeyboardButton("❌ Cancelar", callback_data="workout_cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def nutrition_category_keyboard():
    """Teclado para seleccionar categoría de comida."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = [
        [
            InlineKeyboardButton("🟢 Saludable", callback_data="nutrition_cat:saludable"),
            InlineKeyboardButton("🟡 Moderado", callback_data="nutrition_cat:moderado"),
        ],
        [
            InlineKeyboardButton("🔴 Pesado", callback_data="nutrition_cat:pesado"),
            InlineKeyboardButton("❌ Cancelar", callback_data="nutrition_cancel"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def intent_clarification_keyboard():
    """Teclado para clarificar intención cuando hay baja confianza."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = [
        [
            InlineKeyboardButton("📋 Es una tarea", callback_data="clarify:task"),
            InlineKeyboardButton("💡 Es una idea", callback_data="clarify:idea"),
        ],
        [
            InlineKeyboardButton("💰 Es un gasto", callback_data="clarify:expense"),
            InlineKeyboardButton("📝 Es una nota", callback_data="clarify:note"),
        ],
        [
            InlineKeyboardButton("✅ Dejar en Inbox", callback_data="clarify:inbox"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# ==================== CALLBACK HANDLERS ====================


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para callbacks de botones inline."""
    query = update.callback_query

    # Siempre responder al callback para evitar el "loading" infinito
    try:
        await query.answer()
    except Exception as e:
        logger.warning(f"Error respondiendo callback: {e}")

    data = query.data
    logger.info(f"[CALLBACK] Recibido: {data}")
    print(f"[CALLBACK] Procesando: {data}")

    # Parsear callback data
    parts = data.split(":")
    action = parts[0]

    # ==================== MENÚ PRINCIPAL ====================
    if action == "menu_today":
        await query.message.reply_text("Obteniendo tareas de hoy...")
        notion = get_notion_service()
        tasks = await notion.get_tasks_for_today()
        await query.message.reply_text(
            f"Encontradas {len(tasks)} tareas para hoy."
        )

    elif action == "menu_add":
        await query.message.reply_text(
            "Usa /add [tarea] para agregar una tarea.\n\n"
            "Ejemplo: /add Revisar emails"
        )

    # ==================== CREAR TAREA ====================
    elif action == "task_create":
        # Obtener título de la tarea del context o del callback data
        task_title = context.user_data.get("pending_task")
        if not task_title and len(parts) > 1:
            task_title = ":".join(parts[1:])  # Reconstruir si tiene ":"

        if not task_title:
            await query.edit_message_text("❌ Error: No se encontró la tarea.")
            return

        await query.edit_message_text(f"⏳ Creando tarea: {task_title}...")

        # Analizar complejidad con AI
        from app.agents.complexity_analyzer import ComplexityAnalyzerAgent

        notion = get_notion_service()
        complexity_agent = ComplexityAnalyzerAgent()

        try:
            # Analizar complejidad
            complexity_result = await complexity_agent.analyze_task(task_title)

            # Mapear complejidad a enum de Notion
            from app.services.notion import TaskComplejidad, TaskEnergia

            complexity_map = {
                "quick": TaskComplejidad.QUICK,
                "standard": TaskComplejidad.STANDARD,
                "heavy": TaskComplejidad.HEAVY,
                "epic": TaskComplejidad.EPIC,
            }
            energy_map = {
                "deep_work": TaskEnergia.DEEP_WORK,
                "medium": TaskEnergia.MEDIUM,
                "low": TaskEnergia.LOW,
            }

            task_complexity = complexity_map.get(
                complexity_result.complexity.value, TaskComplejidad.STANDARD
            )
            task_energy = energy_map.get(
                complexity_result.energy_required.value, TaskEnergia.MEDIUM
            )

            # Crear tarea en Notion con estimación
            result = await notion.create_task(
                tarea=task_title,
                estado=TaskEstado.BACKLOG,
                complejidad=task_complexity,
                energia=task_energy,
            )

            if result:
                task_id = result.get("id", "")[:8]

                # Formatear mensaje con análisis
                message = f"✅ <b>Tarea creada:</b> {task_title}\n\n"
                message += complexity_agent.format_result_message(complexity_result)

                # Si sugiere dividir, ofrecer crear subtareas
                if complexity_result.should_divide and complexity_result.suggested_subtasks:
                    message += "\n¿Quieres crear las subtareas sugeridas?"

                    keyboard = [
                        [
                            InlineKeyboardButton(
                                "✅ Crear subtareas",
                                callback_data=f"create_subtasks:{task_id}",
                            ),
                            InlineKeyboardButton(
                                "❌ No, gracias",
                                callback_data="subtasks_skip",
                            ),
                        ],
                    ]

                    # Guardar subtareas en context
                    context.user_data["pending_subtasks"] = complexity_result.suggested_subtasks
                    context.user_data["parent_task_id"] = result.get("id")

                    await query.edit_message_text(
                        message,
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(keyboard),
                    )
                else:
                    # Sin subtareas, mostrar prioridad
                    message += "\n¿Qué prioridad tiene?"
                    await query.edit_message_text(
                        message,
                        parse_mode="HTML",
                        reply_markup=task_priority_keyboard(task_id),
                    )
            else:
                await query.edit_message_text("❌ Error creando la tarea.")

        except Exception as e:
            logger.error(f"Error en task_create callback: {e}")
            # Crear tarea sin análisis como fallback
            result = await notion.create_task(
                tarea=task_title,
                estado=TaskEstado.BACKLOG,
            )
            if result:
                task_id = result.get("id", "")[:8]
                await query.edit_message_text(
                    f"✅ <b>Tarea creada:</b> {task_title}\n\n"
                    "¿Qué prioridad tiene?",
                    parse_mode="HTML",
                    reply_markup=task_priority_keyboard(task_id),
                )
            else:
                await query.edit_message_text("❌ Error creando la tarea.")

        # Limpiar context
        context.user_data.pop("pending_task", None)

    elif action == "task_cancel":
        context.user_data.pop("pending_task", None)
        await query.edit_message_text("❌ Creación de tarea cancelada.")

    # ==================== CREAR SUBTAREAS ====================
    elif action == "create_subtasks":
        parent_task_id = context.user_data.get("parent_task_id")
        subtasks = context.user_data.get("pending_subtasks", [])

        if not parent_task_id or not subtasks:
            await query.edit_message_text("❌ Error: No hay subtareas pendientes.")
            return

        await query.edit_message_text("⏳ Creando subtareas...")

        notion = get_notion_service()
        created_count = 0

        for subtask_title in subtasks:
            result = await notion.create_task(
                tarea=subtask_title,
                estado=TaskEstado.BACKLOG,
                parent_task_id=parent_task_id,
            )
            if result:
                created_count += 1

        await query.edit_message_text(
            f"✅ <b>{created_count} subtareas creadas</b>\n\n"
            f"Vinculadas a la tarea principal.",
            parse_mode="HTML",
        )

        # Limpiar context
        context.user_data.pop("pending_subtasks", None)
        context.user_data.pop("parent_task_id", None)

    elif action == "subtasks_skip":
        context.user_data.pop("pending_subtasks", None)
        context.user_data.pop("parent_task_id", None)
        await query.edit_message_text("✅ Tarea creada sin subtareas.")

    # ==================== CREAR PROYECTO ====================
    elif action == "project_create":
        project_name = context.user_data.get("pending_project_name")
        project_type = context.user_data.get("pending_project_type")

        if not project_name:
            await query.edit_message_text("❌ Error: No se encontró el proyecto.")
            return

        await query.edit_message_text(f"⏳ Creando proyecto: {project_name}...")

        from app.services.notion import ProjectTipo, ProjectEstado

        # Mapear tipo
        type_map = {
            "trabajo": ProjectTipo.TRABAJO,
            "freelance": ProjectTipo.FREELANCE,
            "personal": ProjectTipo.PERSONAL,
            "estudio": ProjectTipo.APRENDIZAJE,
            "side_project": ProjectTipo.SIDE_PROJECT,
        }
        notion_type = type_map.get(project_type, ProjectTipo.PERSONAL)

        notion = get_notion_service()
        result = await notion.create_project(
            nombre=project_name,
            tipo=notion_type,
            estado=ProjectEstado.ACTIVO,
        )

        if result:
            project_id = result.get("id", "")
            context.user_data["current_project_id"] = project_id

            await query.edit_message_text(
                f"✅ <b>Proyecto creado:</b> {project_name}\n"
                f"<b>Tipo:</b> {notion_type.value}\n\n"
                f"¿Quieres agregar tareas a este proyecto?",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "➕ Agregar tareas",
                            callback_data="project_add_tasks",
                        ),
                        InlineKeyboardButton(
                            "✅ Listo",
                            callback_data="project_done",
                        ),
                    ],
                ]),
            )
        else:
            await query.edit_message_text("❌ Error creando el proyecto.")

        context.user_data.pop("pending_project_name", None)
        context.user_data.pop("pending_project_type", None)

    elif action == "project_cancel":
        context.user_data.pop("pending_project_name", None)
        context.user_data.pop("pending_project_type", None)
        await query.edit_message_text("❌ Creación de proyecto cancelada.")

    elif action == "project_add_tasks":
        await query.edit_message_text(
            "📝 <b>Agregar tareas al proyecto</b>\n\n"
            "Escribe las tareas que quieres agregar.\n"
            "Puedes escribir varias separadas por líneas.\n\n"
            "<i>Ejemplo:</i>\n"
            "<code>Diseñar interfaz de usuario\n"
            "Implementar API REST\n"
            "Configurar base de datos</code>\n\n"
            "Usa /done cuando termines.",
            parse_mode="HTML",
        )
        context.user_data["adding_tasks_to_project"] = True

    elif action == "project_done":
        context.user_data.pop("current_project_id", None)
        context.user_data.pop("adding_tasks_to_project", None)
        await query.edit_message_text("✅ Proyecto configurado correctamente.")

    # ==================== SELECCIÓN DE TIPO DE PROYECTO ====================
    elif action.startswith("project_type_"):
        project_type = action.replace("project_type_", "")
        context.user_data["pending_project_type"] = project_type

        project_name = context.user_data.get("pending_project_name", "")

        type_labels = {
            "trabajo": "💼 Trabajo",
            "freelance": "💰 Freelance",
            "personal": "🏠 Personal",
            "estudio": "📚 Estudio/Aprendizaje",
            "side_project": "🚀 Side Project",
        }

        await query.edit_message_text(
            f"📁 <b>Nuevo Proyecto</b>\n\n"
            f"<b>Nombre:</b> {project_name}\n"
            f"<b>Tipo:</b> {type_labels.get(project_type, project_type)}\n\n"
            f"¿Confirmar creación?",
            parse_mode="HTML",
            reply_markup=confirm_keyboard(
                confirm_data="project_create",
                cancel_data="project_cancel",
                confirm_text="✅ Crear proyecto",
                cancel_text="❌ Cancelar",
            ),
        )

    # ==================== PRIORIDAD DE TAREA ====================
    elif action.startswith("priority_"):
        priority = action.split("_")[1]
        task_id = parts[1] if len(parts) > 1 else None

        priority_map = {
            "high": ("🔥 Urgente", TaskPrioridad.URGENTE),
            "medium": ("🔄 Normal", TaskPrioridad.NORMAL),
            "low": ("🧊 Baja", TaskPrioridad.BAJA),
        }

        label, priority_enum = priority_map.get(priority, ("Normal", TaskPrioridad.NORMAL))

        # Actualizar en Notion si tenemos task_id
        if task_id:
            notion = get_notion_service()
            # Buscar la tarea completa por ID parcial
            # Por ahora solo mostramos confirmación

        await query.edit_message_text(
            f"✅ Prioridad establecida: {label}"
        )

    # ==================== INBOX ====================
    elif action == "inbox_classify":
        await query.edit_message_text(
            "📋 Clasificando...\n\n"
            "(InboxProcessor Agent próximamente)"
        )

    elif action == "inbox_done":
        await query.edit_message_text("✅ Guardado en inbox.")

    # ==================== CLARIFICACIÓN DE INTENT ====================
    elif action.startswith("clarify_"):
        clarify_type = action.replace("clarify_", "")

        if clarify_type == "task":
            await query.edit_message_text(
                "📋 Entendido, es una tarea.\n"
                "Procesando...",
            )
            # TODO: Crear como tarea
        elif clarify_type == "idea":
            await query.edit_message_text("💡 Guardado como idea.")
        elif clarify_type == "expense":
            await query.edit_message_text("💰 Guardado como gasto pendiente.")
        elif clarify_type == "note":
            await query.edit_message_text("📝 Guardado como nota.")
        elif clarify_type == "inbox":
            await query.edit_message_text("✅ Dejado en Inbox.")

    # ==================== GYM CALLBACKS (desde keyboards.py) ====================
    elif action == "gym_going":
        await query.edit_message_text("💪 ¡Excelente! Te espero de vuelta cuando termines.")

    elif action.startswith("gym_snooze"):
        minutes = parts[1] if len(parts) > 1 else "15"
        await query.edit_message_text(f"⏰ Ok, te recordaré en {minutes} minutos.")

    elif action == "gym_reschedule":
        await query.edit_message_text("🔄 Ok, ¿para cuándo quieres reprogramar?")

    elif action == "gym_skip":
        await query.edit_message_text("❌ Entendido, hoy descansas del gym.")

    elif action.startswith("workout_rating"):
        rating = parts[1] if len(parts) > 1 else "3"
        ratings = {"1": "😫 Malo", "2": "😐 Regular", "3": "🙂 Bueno", "4": "😄 Muy bueno", "5": "🔥 Excelente"}
        await query.edit_message_text(f"✅ Workout calificado: {ratings.get(rating, rating)}")

    elif action.startswith("workout_type"):
        workout_type = parts[1] if len(parts) > 1 else "push"
        context.user_data["pending_workout_type"] = workout_type
        await query.edit_message_text(
            f"🏋️ <b>Registrar {workout_type.upper()}</b>\n\n"
            "Describe tu entrenamiento (ejercicios, series, repeticiones):",
            parse_mode="HTML",
        )

    elif action == "workout_cancel":
        context.user_data.pop("pending_workout", None)
        context.user_data.pop("pending_workout_type", None)
        await query.edit_message_text("❌ Registro de workout cancelado.")

    # ==================== NUTRICIÓN CALLBACKS ====================
    elif action.startswith("meal_"):
        meal_type = action.replace("meal_", "")
        meal_names = {
            "breakfast": "🌅 Desayuno",
            "lunch": "🌞 Almuerzo",
            "dinner": "🌙 Cena",
            "snack": "🍎 Snack"
        }
        context.user_data["pending_meal_type"] = meal_type
        await query.edit_message_text(
            f"🍽️ <b>Registrar {meal_names.get(meal_type, meal_type)}</b>\n\n"
            "¿Qué comiste?",
            parse_mode="HTML",
        )

    elif action.startswith("nutrition_rating"):
        rating = parts[1] if len(parts) > 1 else "3"
        await query.edit_message_text(f"✅ Nutrición del día calificada: {rating}/5")

    elif action.startswith("nutrition_cat"):
        category = parts[1] if len(parts) > 1 else "moderado"
        categories = {"saludable": "🟢 Saludable", "moderado": "🟡 Moderado", "pesado": "🔴 Pesado"}
        await query.edit_message_text(f"✅ Registrado como: {categories.get(category, category)}")

    elif action == "nutrition_cancel":
        context.user_data.pop("pending_nutrition", None)
        context.user_data.pop("pending_meal_type", None)
        await query.edit_message_text("❌ Registro de comida cancelado.")

    # ==================== CHECK-IN CALLBACKS ====================
    elif action == "checkin_good":
        await query.edit_message_text("✅ ¡Genial! Sigue así 💪")

    elif action == "checkin_switch":
        await query.edit_message_text("🔄 Ok, ¿a qué tarea quieres cambiar?")

    elif action == "checkin_blocked":
        await query.edit_message_text("🚫 ¿Cuál es el blocker?")

    elif action == "checkin_break":
        await query.edit_message_text("☕ Ok, disfruta tu break. Te aviso en 15 min.")

    # ==================== ENERGY LEVEL ====================
    elif action.startswith("energy"):
        level = parts[1] if len(parts) > 1 else "3"
        await query.edit_message_text(f"⚡ Nivel de energía registrado: {level}/5")

    # ==================== STUDY CALLBACKS ====================
    elif action.startswith("study_start"):
        project_id = action.replace("study_start_", "")
        await query.edit_message_text("📚 ¡A estudiar! Te aviso cuando sea hora de descanso.")

    elif action.startswith("study_alt"):
        await query.edit_message_text("📖 Alternativa seleccionada.")

    elif action == "study_later_30":
        await query.edit_message_text("⏰ Ok, te recordaré en 30 minutos.")

    elif action == "study_skip":
        await query.edit_message_text("❌ Ok, sin estudio por hoy.")

    # ==================== PAYDAY CALLBACKS ====================
    elif action == "payday_follow_plan":
        await query.edit_message_text("✅ ¡Excelente! Siguiendo el plan de pagos.")

    elif action == "payday_adjust":
        await query.edit_message_text("✏️ ¿Qué ajustes quieres hacer al plan?")

    elif action == "payday_view_debts":
        notion = get_notion_service()
        summary = await notion.get_debt_summary()
        if summary and summary.get("deudas"):
            msg = "💳 <b>Resumen de Deudas</b>\n\n"
            for debt in summary["deudas"]:
                msg += f"• {debt['nombre']}: ${debt['monto']:,.0f}\n"
            msg += f"\n<b>Total:</b> ${summary['total_deuda']:,.0f}"
        else:
            msg = "💳 No tienes deudas registradas."
        await query.edit_message_text(msg, parse_mode="HTML")

    elif action == "payday_later":
        await query.edit_message_text("⏭️ Te recordaré más tarde.")

    # ==================== EXPENSE CALLBACKS ====================
    elif action == "expense_log":
        pending = context.user_data.get("pending_expense", {})
        await query.edit_message_text(
            f"✅ Gasto registrado: ${pending.get('amount', '?')}"
        )
        context.user_data.pop("pending_expense", None)

    elif action == "expense_cancel":
        context.user_data.pop("pending_expense", None)
        await query.edit_message_text("❌ Registro de gasto cancelado.")

    elif action.startswith("expense_"):
        category = action.replace("expense_", "")
        categories = {
            "food": "🍔 Comida",
            "transport": "🚗 Transporte",
            "home": "🏠 Casa",
            "entertainment": "🎮 Entretenimiento",
            "health": "💊 Salud",
            "education": "📚 Educación",
            "other": "🛒 Otro"
        }
        await query.edit_message_text(f"✅ Categoría: {categories.get(category, category)}")

    # ==================== SPENDING DECISION CALLBACKS ====================
    elif action == "spend_buy":
        await query.edit_message_text("🛒 Compra registrada.")

    elif action == "spend_wishlist":
        await query.edit_message_text("📋 Agregado a wishlist.")

    elif action == "spend_wait":
        await query.edit_message_text("⏳ Buena decisión, esperar antes de comprar.")

    elif action == "spend_skip":
        await query.edit_message_text("❌ No comprar - ¡Dinero ahorrado!")

    # ==================== REMINDER CALLBACKS ====================
    elif action.startswith("reminder_done"):
        reminder_id = parts[1] if len(parts) > 1 else "?"
        await query.edit_message_text(f"✅ Recordatorio {reminder_id} completado.")

    elif action.startswith("reminder_snooze"):
        reminder_id = parts[1] if len(parts) > 1 else "?"
        minutes = parts[2] if len(parts) > 2 else "30"
        await query.edit_message_text(f"⏰ Recordatorio pospuesto {minutes} minutos.")

    elif action.startswith("reminder_cancel"):
        reminder_id = parts[1] if len(parts) > 1 else "?"
        context.user_data.pop("pending_reminder", None)
        await query.edit_message_text(f"🗑️ Recordatorio cancelado.")

    elif action.startswith("reminder_time"):
        time_option = parts[1] if len(parts) > 1 else "30m"
        pending = context.user_data.get("pending_reminder", {})
        reminder_text = pending.get("text", "Recordatorio")

        from datetime import datetime, timedelta
        from app.scheduler.setup import add_one_time_job

        now = datetime.now()

        # Calcular tiempo del recordatorio
        time_labels = {
            "30m": ("30 minutos", timedelta(minutes=30)),
            "1h": ("1 hora", timedelta(hours=1)),
            "3h": ("3 horas", timedelta(hours=3)),
            "tomorrow": ("mañana a las 9:00 AM", None),
        }

        if time_option == "tomorrow":
            # Mañana a las 9 AM
            run_time = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0)
            label = "mañana a las 9:00 AM"
        elif time_option == "custom":
            await query.edit_message_text(
                f"⏰ <b>Recordatorio personalizado</b>\n\n"
                f"<i>{reminder_text[:100]}</i>\n\n"
                f"Escribe la hora o fecha del recordatorio:\n"
                f"Ejemplos: '3pm', 'mañana 10am', 'en 2 horas'",
                parse_mode="HTML",
            )
            context.user_data["awaiting_reminder_time"] = True
            return
        else:
            label, delta = time_labels.get(time_option, ("30 minutos", timedelta(minutes=30)))
            run_time = now + delta

        # Crear job de recordatorio
        async def send_reminder():
            from app.services.telegram import get_telegram_service
            telegram = get_telegram_service()
            await telegram.send_message(
                f"⏰ <b>Recordatorio</b>\n\n{reminder_text}",
                parse_mode="HTML",
            )

        job_id = f"reminder_{now.timestamp()}"
        add_one_time_job(send_reminder, run_time, job_id)

        await query.edit_message_text(
            f"✅ <b>Recordatorio creado</b>\n\n"
            f"<i>{reminder_text[:100]}</i>\n\n"
            f"Te recordaré en {label}",
            parse_mode="HTML",
        )
        context.user_data.pop("pending_reminder", None)

    # ==================== TASK COMPLETE/DELETE CALLBACKS ====================
    elif action.startswith("task_complete"):
        task_short_id = parts[1] if len(parts) > 1 else None
        pending_tasks = context.user_data.get("pending_delete_tasks", [])

        # Buscar tarea por ID parcial
        task_to_complete = None
        for task in pending_tasks:
            if task["id"].startswith(task_short_id):
                task_to_complete = task
                break

        if task_to_complete:
            notion = get_notion_service()
            success = await notion.update_task_status(
                task_to_complete["id"],
                TaskEstado.DONE,
            )

            if success:
                await query.edit_message_text(
                    f"✅ <b>Tarea completada</b>\n\n"
                    f"<s>{task_to_complete['title']}</s>",
                    parse_mode="HTML",
                )
            else:
                await query.edit_message_text(
                    f"❌ Error al completar la tarea."
                )
        else:
            await query.edit_message_text("❌ No se encontró la tarea.")

        context.user_data.pop("pending_delete_tasks", None)

    elif action == "task_delete_cancel":
        context.user_data.pop("pending_delete_tasks", None)
        await query.edit_message_text("❌ Operación cancelada.")

    elif action.startswith("task_edit"):
        task_short_id = parts[1] if len(parts) > 1 else None
        pending_tasks = context.user_data.get("pending_edit_tasks", [])

        # Buscar tarea por ID parcial
        task_to_edit = None
        for task in pending_tasks:
            if task["id"].startswith(task_short_id):
                task_to_edit = task
                break

        if task_to_edit:
            context.user_data["editing_task_id"] = task_to_edit["id"]

            keyboard = [
                [
                    InlineKeyboardButton("📝 Cambiar nombre", callback_data="task_edit_name"),
                    InlineKeyboardButton("🎯 Cambiar estado", callback_data="task_edit_status"),
                ],
                [
                    InlineKeyboardButton("🔥 Cambiar prioridad", callback_data="task_edit_priority"),
                    InlineKeyboardButton("📅 Cambiar fecha", callback_data="task_edit_date"),
                ],
                [
                    InlineKeyboardButton("❌ Cancelar", callback_data="task_update_cancel"),
                ],
            ]

            await query.edit_message_text(
                f"✏️ <b>Editar tarea</b>\n\n"
                f"<i>{task_to_edit['title']}</i>\n\n"
                f"¿Qué quieres modificar?",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            await query.edit_message_text("❌ No se encontró la tarea.")

    elif action == "task_edit_status":
        keyboard = [
            [
                InlineKeyboardButton("📥 Backlog", callback_data="task_set_status:backlog"),
                InlineKeyboardButton("🎯 Today", callback_data="task_set_status:today"),
            ],
            [
                InlineKeyboardButton("⚡ Doing", callback_data="task_set_status:doing"),
                InlineKeyboardButton("✅ Done", callback_data="task_set_status:done"),
            ],
            [
                InlineKeyboardButton("❌ Cancelar", callback_data="task_update_cancel"),
            ],
        ]
        await query.edit_message_text(
            "🎯 <b>Cambiar estado</b>\n\nSelecciona el nuevo estado:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif action.startswith("task_set_status"):
        status_key = parts[1] if len(parts) > 1 else "backlog"
        task_id = context.user_data.get("editing_task_id")

        status_map = {
            "backlog": TaskEstado.BACKLOG,
            "today": TaskEstado.TODAY,
            "doing": TaskEstado.DOING,
            "done": TaskEstado.DONE,
        }

        if task_id:
            notion = get_notion_service()
            success = await notion.update_task_status(
                task_id,
                status_map.get(status_key, TaskEstado.BACKLOG),
            )

            if success:
                await query.edit_message_text(
                    f"✅ Estado actualizado a: {status_key.upper()}"
                )
            else:
                await query.edit_message_text("❌ Error al actualizar estado.")

        context.user_data.pop("editing_task_id", None)
        context.user_data.pop("pending_edit_tasks", None)

    elif action == "task_update_cancel":
        context.user_data.pop("editing_task_id", None)
        context.user_data.pop("pending_edit_tasks", None)
        await query.edit_message_text("❌ Edición cancelada.")

    # ==================== PROJECT EDIT/ARCHIVE CALLBACKS ====================
    elif action.startswith("project_edit"):
        project_short_id = parts[1] if len(parts) > 1 else None
        pending_projects = context.user_data.get("pending_edit_projects", [])

        project_to_edit = None
        for proj in pending_projects:
            if proj["id"].startswith(project_short_id):
                project_to_edit = proj
                break

        if project_to_edit:
            context.user_data["editing_project_id"] = project_to_edit["id"]

            keyboard = [
                [
                    InlineKeyboardButton("📝 Cambiar nombre", callback_data="project_edit_name"),
                    InlineKeyboardButton("🏷️ Cambiar tipo", callback_data="project_edit_type"),
                ],
                [
                    InlineKeyboardButton("🎯 Cambiar estado", callback_data="project_edit_status"),
                ],
                [
                    InlineKeyboardButton("❌ Cancelar", callback_data="project_update_cancel"),
                ],
            ]

            await query.edit_message_text(
                f"✏️ <b>Editar proyecto</b>\n\n"
                f"<i>{project_to_edit['title']}</i>\n\n"
                f"¿Qué quieres modificar?",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            await query.edit_message_text("❌ No se encontró el proyecto.")

    elif action.startswith("project_archive"):
        project_short_id = parts[1] if len(parts) > 1 else None
        pending_projects = context.user_data.get("pending_delete_projects", [])

        project_to_archive = None
        for proj in pending_projects:
            if proj["id"].startswith(project_short_id):
                project_to_archive = proj
                break

        if project_to_archive:
            from app.services.notion import ProjectEstado

            notion = get_notion_service()
            success = await notion.update_project_status(
                project_to_archive["id"],
                ProjectEstado.COMPLETADO,
            )

            if success:
                await query.edit_message_text(
                    f"📦 <b>Proyecto archivado</b>\n\n"
                    f"<s>{project_to_archive['title']}</s>",
                    parse_mode="HTML",
                )
            else:
                await query.edit_message_text("❌ Error al archivar el proyecto.")
        else:
            await query.edit_message_text("❌ No se encontró el proyecto.")

        context.user_data.pop("pending_delete_projects", None)

    elif action == "project_update_cancel":
        context.user_data.pop("editing_project_id", None)
        context.user_data.pop("pending_edit_projects", None)
        await query.edit_message_text("❌ Edición cancelada.")

    elif action == "project_delete_cancel":
        context.user_data.pop("pending_delete_projects", None)
        await query.edit_message_text("❌ Operación cancelada.")

    elif action.startswith("snooze"):
        reminder_id = parts[1] if len(parts) > 1 else "?"
        time_val = parts[2] if len(parts) > 2 else "30"
        if time_val == "tomorrow":
            await query.edit_message_text("⏰ Recordatorio movido para mañana.")
        else:
            await query.edit_message_text(f"⏰ Recordatorio en {time_val} minutos.")

    # ==================== MENU CALLBACKS ====================
    elif action == "menu_gym":
        await query.edit_message_text(
            "🏋️ <b>Gym</b>\n\n"
            "Usa /gym para registrar tu workout.",
            parse_mode="HTML",
        )

    elif action == "menu_nutrition":
        await query.edit_message_text(
            "🍽️ <b>Nutrición</b>\n\n"
            "Usa /food para registrar tus comidas.",
            parse_mode="HTML",
        )

    elif action == "menu_finance":
        notion = get_notion_service()
        summary = await notion.get_debt_summary()
        if summary:
            msg = f"💰 <b>Finanzas</b>\n\n"
            msg += f"Deuda total: ${summary.get('total_deuda', 0):,.0f}\n"
            msg += f"Pago mínimo: ${summary.get('total_pago_minimo', 0):,.0f}/mes"
        else:
            msg = "💰 <b>Finanzas</b>\n\nNo hay datos de deudas."
        await query.edit_message_text(msg, parse_mode="HTML")

    elif action == "menu_summary":
        await query.edit_message_text(
            "📊 <b>Resumen</b>\n\n"
            "(Próximamente: resumen del día)",
            parse_mode="HTML",
        )

    # ==================== CONVERSATIONAL ORCHESTRATOR CALLBACKS ====================
    elif action == "confirm_subtasks":
        # Confirmar creación de subtareas desde ConversationalOrchestrator
        from app.agents.conversational_orchestrator import get_conversational_orchestrator

        orchestrator = get_conversational_orchestrator()
        user_id = update.effective_user.id
        response = await orchestrator.process_message(user_id, "sí, crear subtareas")

        await query.edit_message_text(response.message, parse_mode="HTML")

    elif action == "modify_subtasks":
        await query.edit_message_text(
            "✏️ <b>Modificar subtareas</b>\n\n"
            "Puedes decir:\n"
            "• 'quita la 3'\n"
            "• 'añade: revisar documentación'\n"
            "• 'cambia la 2 por: testing'\n",
            parse_mode="HTML",
        )

    elif action == "skip_subtasks":
        from app.agents.conversation_context import get_conversation_store

        store = get_conversation_store()
        user_id = update.effective_user.id
        ctx = store.get(user_id)
        ctx.clear_pending_action()
        store.save(ctx)

        await query.edit_message_text("Tarea creada sin subtareas.")

    elif action.startswith("project_type_"):
        project_type = action.replace("project_type_", "")
        from app.agents.conversation_context import get_conversation_store
        from app.services.notion import ProjectTipo, ProjectEstado

        store = get_conversation_store()
        user_id = update.effective_user.id
        ctx = store.get(user_id)

        if ctx.active_entity:
            project_name = ctx.active_entity.entity_name

            # Mapear tipo
            type_map = {
                "trabajo": ProjectTipo.TRABAJO,
                "freelance": ProjectTipo.FREELANCE,
                "estudio": ProjectTipo.APRENDIZAJE,
                "personal": ProjectTipo.PERSONAL,
            }
            project_tipo = type_map.get(project_type, ProjectTipo.PERSONAL)

            # Crear proyecto en Notion
            notion = get_notion_service()
            result = await notion.create_project(
                nombre=project_name,
                tipo=project_tipo,
                estado=ProjectEstado.ACTIVO,
                en_rotacion_estudio=(project_type == "estudio"),
            )

            if result:
                ctx.active_entity.entity_id = result.get("id")
                store.save(ctx)

                await query.edit_message_text(
                    f"✅ <b>Proyecto creado:</b> {project_name}\n"
                    f"📁 Tipo: {project_type.capitalize()}",
                    parse_mode="HTML",
                )
            else:
                await query.edit_message_text("❌ Error creando proyecto")
        else:
            await query.edit_message_text("❌ No hay proyecto pendiente")

    elif action.startswith("priority_"):
        priority_key = action.replace("priority_", "")
        from app.agents.conversation_context import get_conversation_store

        store = get_conversation_store()
        user_id = update.effective_user.id
        ctx = store.get(user_id)

        if ctx.active_entity and ctx.active_entity.entity_id:
            priority_map = {
                "urgente": TaskPrioridad.URGENTE,
                "alta": TaskPrioridad.ALTA,
                "normal": TaskPrioridad.NORMAL,
                "baja": TaskPrioridad.BAJA,
            }
            priority = priority_map.get(priority_key, TaskPrioridad.NORMAL)

            notion = get_notion_service()
            await notion.update_task_priority(ctx.active_entity.entity_id, priority)

            await query.edit_message_text(
                f"✅ Prioridad de '{ctx.active_entity.entity_name}' actualizada a: {priority.value}"
            )
        else:
            await query.edit_message_text("❌ No hay tarea activa para actualizar")

    elif action == "confirm_delete":
        from app.agents.conversational_orchestrator import get_conversational_orchestrator

        orchestrator = get_conversational_orchestrator()
        user_id = update.effective_user.id
        response = await orchestrator.process_message(user_id, "sí, eliminar")

        await query.edit_message_text(response.message, parse_mode="HTML")

    elif action == "cancel_delete":
        from app.agents.conversational_orchestrator import get_conversational_orchestrator

        orchestrator = get_conversational_orchestrator()
        user_id = update.effective_user.id
        response = await orchestrator.process_message(user_id, "no, cancelar")

        await query.edit_message_text(response.message, parse_mode="HTML")

    elif action.startswith("edit_"):
        edit_type = action.replace("edit_", "")
        if edit_type == "cancel":
            await query.edit_message_text("❌ Edición cancelada")
        else:
            await query.edit_message_text(
                f"Para editar {edit_type}, escribe el nuevo valor."
            )

    # ==================== PLANNING CALLBACKS ====================
    elif action == "planning_tomorrow":
        from app.agents.planning_assistant import get_planning_assistant

        await query.edit_message_text("🌙 Planificando mañana...")

        planning = get_planning_assistant()
        plan = await planning.plan_tomorrow()

        response = f"📋 <b>Plan para {plan.day_of_week}</b>\n\n"
        for i, task in enumerate(plan.selected_tasks[:7], 1):
            prioridad = task.get("prioridad", "")
            emoji = "🔥" if "Urgente" in prioridad else "⚡" if "Alta" in prioridad else "📌"
            response += f"{i}. {emoji} {task.get('name', 'Sin nombre')[:40]}\n"

        response += f"\n⏱️ Carga: {plan.estimated_workload_hours:.1f}h"

        await query.edit_message_text(response, parse_mode="HTML")

    elif action == "planning_week":
        from app.agents.planning_assistant import get_planning_assistant

        await query.edit_message_text("📊 Cargando semana...")

        planning = get_planning_assistant()
        overview = await planning.get_week_overview()

        response = f"📊 <b>Esta semana</b>\n"
        response += f"Total: {overview.get('total_tasks', 0)} tareas\n"
        response += f"Vencidas: {overview.get('overdue_count', 0)}\n"

        await query.edit_message_text(response, parse_mode="HTML")

    elif action == "planning_accept":
        await query.edit_message_text(
            "✅ <b>Plan aceptado</b>\n\n"
            "¡A trabajar! Usa /today para ver tus tareas.",
            parse_mode="HTML",
        )

    elif action == "planning_regenerate":
        await query.edit_message_text(
            "🔄 Para regenerar el plan, dime qué preferencias tienes.\n"
            "Por ejemplo: 'quiero día ligero' o 'necesito terminar urgentes'",
            parse_mode="HTML",
        )

    elif action == "planning_create_reminders":
        from app.agents.planning_assistant import get_planning_assistant
        from app.config import get_settings

        settings = get_settings()
        user_id = update.effective_user.id
        chat_id = str(settings.telegram_chat_id)

        # Obtener plan del contexto
        plan_data = context.user_data.get("current_plan")
        if not plan_data:
            await query.edit_message_text("❌ No hay plan activo.")
            return

        planning = get_planning_assistant()

        # Crear objeto TomorrowPlan simplificado
        from app.agents.planning_assistant import TomorrowPlan
        plan = TomorrowPlan(
            date=plan_data["date"],
            day_of_week="",
            selected_tasks=plan_data["tasks"],
            task_order=[],
            reasoning="",
            warnings=[],
            suggestions=[],
            estimated_workload_hours=plan_data["workload"],
        )

        reminder_ids = await planning.create_planning_reminders(
            chat_id=chat_id,
            user_id=str(user_id),
            plan=plan,
        )

        await query.edit_message_text(
            f"⏰ <b>{len(reminder_ids)} recordatorios creados</b>\n\n"
            "Te notificaré mañana para ayudarte a cumplir el plan.",
            parse_mode="HTML",
        )

    elif action == "planning_skip":
        await query.edit_message_text("👍 Listo, sin planificación por hoy.")

    elif action == "planning_suggest_today":
        from app.agents.planning_assistant import get_planning_assistant

        await query.edit_message_text("📋 Buscando tareas sugeridas...")

        planning = get_planning_assistant()
        plan = await planning.plan_tomorrow()  # Usa la misma lógica

        response = "📋 <b>Tareas sugeridas para hoy:</b>\n\n"
        for i, task in enumerate(plan.selected_tasks[:5], 1):
            response += f"{i}. {task.get('name', 'Sin nombre')[:40]}\n"

        await query.edit_message_text(response, parse_mode="HTML")

    elif action == "planning_adjust_today":
        await query.edit_message_text(
            "🔄 <b>Ajustar plan</b>\n\n"
            "Dime qué cambios quieres hacer:\n"
            "• 'quita la 3'\n"
            "• 'añade: revisar emails'\n"
            "• 'mueve X para mañana'",
            parse_mode="HTML",
        )

    elif action == "morning_ack":
        await query.edit_message_text("💪 ¡A trabajar! Éxito hoy.")

    elif action.startswith("reschedule_task:"):
        task_short_id = action.replace("reschedule_task:", "")

        keyboard = [
            [
                InlineKeyboardButton("📅 Mañana", callback_data=f"move_to:tomorrow:{task_short_id}"),
                InlineKeyboardButton("📅 Pasado", callback_data=f"move_to:day_after:{task_short_id}"),
            ],
            [
                InlineKeyboardButton("📅 Lunes", callback_data=f"move_to:monday:{task_short_id}"),
                InlineKeyboardButton("📅 Viernes", callback_data=f"move_to:friday:{task_short_id}"),
            ],
            [InlineKeyboardButton("❌ Cancelar", callback_data="reschedule_cancel")],
        ]

        await query.edit_message_text(
            "📅 <b>¿Para cuándo?</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif action.startswith("move_to:"):
        from datetime import timedelta

        parts = action.split(":")
        when = parts[1]
        task_short_id = parts[2] if len(parts) > 2 else None

        now = datetime.now()
        if when == "tomorrow":
            new_date = now + timedelta(days=1)
        elif when == "day_after":
            new_date = now + timedelta(days=2)
        elif when == "monday":
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            new_date = now + timedelta(days=days_until_monday)
        elif when == "friday":
            days_until_friday = (4 - now.weekday()) % 7
            if days_until_friday == 0:
                days_until_friday = 7
            new_date = now + timedelta(days=days_until_friday)
        else:
            new_date = now + timedelta(days=1)

        date_str = new_date.strftime("%Y-%m-%d")

        # Buscar tarea completa por ID parcial
        if task_short_id:
            notion = get_notion_service()
            tasks = await notion.get_pending_tasks(limit=30)

            for task in tasks:
                if task.get("id", "").startswith(task_short_id):
                    await notion.update_task_dates(task["id"], fecha_do=date_str)

                    props = task.get("properties", {})
                    title = props.get("Tarea", {}).get("title", [{}])[0].get("text", {}).get("content", "tarea")

                    await query.edit_message_text(
                        f"✅ <b>{title[:40]}</b>\n\nMovida para: {new_date.strftime('%d/%m (%A)')}",
                        parse_mode="HTML",
                    )
                    return

        await query.edit_message_text(
            f"✅ Tarea movida para: {new_date.strftime('%d/%m')}",
            parse_mode="HTML",
        )

    elif action == "reschedule_cancel":
        await query.edit_message_text("❌ Reprogramación cancelada")

    elif action == "workload_check":
        from app.agents.orchestrator import get_orchestrator

        orchestrator = get_orchestrator()
        summary = await orchestrator.get_workload_summary()

        response = f"📊 <b>Carga actual:</b> {summary.get('total_pending', 0)} tareas\n"
        response += f"⚠️ Vencidas: {summary.get('overdue', 0)}"

        await query.edit_message_text(response, parse_mode="HTML")

    elif action == "show_urgent_tasks":
        notion = get_notion_service()
        tasks = await notion.get_pending_tasks(limit=10)

        urgent = [t for t in tasks if "Urgente" in str(t.get("properties", {}).get("Prioridad", {}))]

        if urgent:
            response = "🔥 <b>Tareas urgentes:</b>\n\n"
            for t in urgent[:5]:
                name = t.get("properties", {}).get("Tarea", {}).get("title", [{}])[0].get("text", {}).get("content", "?")
                response += f"• {name[:40]}\n"
        else:
            response = "✅ No tienes tareas urgentes."

        await query.edit_message_text(response, parse_mode="HTML")

    # ==================== REMINDER CALLBACKS ====================
    elif action.startswith("reminder_done:"):
        reminder_id = int(action.replace("reminder_done:", ""))
        from app.services.reminder_service import get_reminder_service

        service = get_reminder_service()
        await service.mark_completed(reminder_id)

        await query.edit_message_text("✅ Recordatorio completado")

    elif action.startswith("reminder_snooze:"):
        parts = action.split(":")
        reminder_id = int(parts[1])
        minutes = int(parts[2]) if len(parts) > 2 else 30

        from app.services.reminder_service import get_reminder_service

        service = get_reminder_service()
        await service.snooze_reminder(reminder_id, minutes)

        await query.edit_message_text(f"⏰ Recordatorio pospuesto {minutes} minutos")

    elif action.startswith("reminder_dismiss:"):
        reminder_id = int(action.replace("reminder_dismiss:", ""))
        from app.services.reminder_service import get_reminder_service

        service = get_reminder_service()
        await service.mark_acknowledged(reminder_id)

        await query.edit_message_text("👍 Recordatorio descartado")

    # ==================== FALLBACKS ====================
    elif action.startswith("confirm"):
        await query.edit_message_text("✅ Confirmado")

    elif action.startswith("cancel"):
        await query.edit_message_text("❌ Cancelado")

    else:
        logger.warning(f"Callback no manejado: {data}")
        await query.edit_message_text(f"⚠️ Acción no implementada: {action}")


# ==================== PLANNING HANDLERS ====================


async def handle_plan_tomorrow(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    message: str,
) -> None:
    """Maneja la planificación del día siguiente."""
    from app.agents.planning_assistant import get_planning_assistant
    from app.config import get_settings

    settings = get_settings()

    # Mostrar que estamos procesando
    processing_msg = await update.message.reply_html(
        "🌙 <b>Planificando tu mañana...</b>\n\n"
        "⏳ Analizando tareas pendientes y prioridades..."
    )

    try:
        planning = get_planning_assistant()

        # Detectar nivel de energía del mensaje
        energy = "no_especificado"
        message_lower = message.lower()
        if any(w in message_lower for w in ["cansado", "poco", "ligero"]):
            energy = "bajo"
        elif any(w in message_lower for w in ["motivado", "energía", "productivo"]):
            energy = "alto"

        plan = await planning.plan_tomorrow(
            user_message=message,
            energy_level=energy,
        )

        # Formatear respuesta
        response = f"📋 <b>Plan para {plan.day_of_week} ({plan.date})</b>\n\n"

        if plan.warnings:
            response += "⚠️ <b>Alertas:</b>\n"
            for warning in plan.warnings[:3]:
                response += f"• {warning}\n"
            response += "\n"

        response += "<b>Tareas sugeridas:</b>\n"
        for i, task in enumerate(plan.selected_tasks[:7], 1):
            prioridad = task.get("prioridad", "")
            emoji = "🔥" if "Urgente" in prioridad else "⚡" if "Alta" in prioridad else "📌"
            response += f"{i}. {emoji} {task.get('name', 'Sin nombre')[:40]}\n"

        response += f"\n⏱️ Carga estimada: {plan.estimated_workload_hours:.1f} horas"

        if plan.suggestions:
            response += "\n\n💡 <b>Sugerencias:</b>\n"
            for sug in plan.suggestions[:2]:
                response += f"• {sug}\n"

        # Botones de acción
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Aceptar plan",
                    callback_data="planning_accept"
                ),
                InlineKeyboardButton(
                    "🔄 Regenerar",
                    callback_data="planning_regenerate"
                ),
            ],
            [
                InlineKeyboardButton(
                    "⏰ Crear recordatorios",
                    callback_data="planning_create_reminders"
                ),
            ],
        ]

        # Guardar plan en contexto
        context.user_data["current_plan"] = {
            "date": plan.date,
            "tasks": plan.selected_tasks,
            "workload": plan.estimated_workload_hours,
        }

        await processing_msg.edit_text(
            response,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    except Exception as e:
        logger.error(f"Error en plan_tomorrow: {e}")
        await processing_msg.edit_text(
            "❌ Error generando el plan. Intenta de nuevo.",
            parse_mode="HTML",
        )


async def handle_plan_week(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Maneja la vista semanal."""
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
            return

        response = f"📊 <b>Resumen Semanal</b>\n"
        response += f"<i>{overview['week_start']} al {overview['week_end']}</i>\n\n"

        # Carga por día
        response += "<b>Carga por día:</b>\n"
        for day, data in overview.get("workload_by_day", {}).items():
            if data["tasks"] > 0:
                bar = "█" * min(data["tasks"], 5)
                urgent = f" 🔥{data['urgent']}" if data["urgent"] > 0 else ""
                response += f"• {day}: {data['tasks']} tareas ({data['hours']:.1f}h){urgent}\n"

        response += f"\n<b>Por prioridad:</b>\n"
        prio = overview.get("by_priority", {})
        response += f"🔥 Urgente: {prio.get('urgente', 0)}\n"
        response += f"⚡ Alta: {prio.get('alta', 0)}\n"
        response += f"📌 Normal: {prio.get('normal', 0)}\n"
        response += f"🧊 Baja: {prio.get('baja', 0)}\n"

        if overview.get("overdue_count", 0) > 0:
            response += f"\n⚠️ <b>Vencidas:</b> {overview['overdue_count']}"

        if overview.get("unscheduled_count", 0) > 0:
            response += f"\n📥 <b>Sin programar:</b> {overview['unscheduled_count']}"

        response += f"\n\n<b>Total:</b> {overview.get('total_tasks', 0)} tareas (~{overview.get('total_hours', 0):.1f}h)"

        keyboard = [
            [
                InlineKeyboardButton(
                    "📋 Planificar mañana",
                    callback_data="planning_tomorrow"
                ),
            ],
        ]

        await processing_msg.edit_text(
            response,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    except Exception as e:
        logger.error(f"Error en plan_week: {e}")
        await processing_msg.edit_text(
            "❌ Error cargando resumen semanal.",
            parse_mode="HTML",
        )


async def handle_workload_check(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Revisa la carga de trabajo actual."""
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
                response += f"• {dl['due']}: {dl['name'][:30]}\n"

        # Evaluación
        if prio.get("urgente", 0) > 3 or overdue > 5:
            response += "\n\n⚠️ <b>Alerta:</b> Carga alta. Considera reprogramar o delegar."
        elif total < 10:
            response += "\n\n✅ Carga manejable. ¡Buen trabajo!"

        await update.message.reply_html(response)

    except Exception as e:
        logger.error(f"Error en workload_check: {e}")
        await update.message.reply_text("❌ Error revisando carga de trabajo.")


async def handle_prioritize(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    entities: dict,
) -> None:
    """Ayuda a priorizar entre tareas."""
    await update.message.reply_html(
        "🤔 <b>Ayuda para priorizar</b>\n\n"
        "Dime las dos tareas que quieres comparar.\n"
        "Por ejemplo: 'debería hacer primero X o Y?'\n\n"
        "O selecciona una tarea para cambiar su prioridad:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Ver tareas urgentes", callback_data="show_urgent_tasks")],
            [InlineKeyboardButton("📊 Ver mi carga", callback_data="workload_check")],
        ]),
    )


async def handle_reschedule_request(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    entities: dict,
) -> None:
    """Maneja solicitudes de reprogramación."""
    from app.agents.planning_assistant import get_planning_assistant

    task_name = entities.get("task", "")

    if not task_name:
        await update.message.reply_html(
            "📅 <b>Reprogramar tarea</b>\n\n"
            "¿Qué tarea quieres mover?\n"
            "Dime el nombre de la tarea o selecciona de tus pendientes:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Ver tareas de hoy", callback_data="show_today_for_reschedule")],
            ]),
        )
        return

    # Buscar la tarea
    notion = get_notion_service()
    tasks = await notion.get_pending_tasks(limit=15)

    matching = []
    for task in tasks:
        props = task.get("properties", {})
        title_prop = props.get("Tarea", {}).get("title", [])
        title = title_prop[0].get("text", {}).get("content", "") if title_prop else ""

        if task_name.lower() in title.lower():
            matching.append({"id": task.get("id"), "title": title})

    if matching:
        keyboard = []
        for task in matching[:5]:
            short_id = task["id"][:8]
            keyboard.append([
                InlineKeyboardButton(
                    f"📅 {task['title'][:30]}",
                    callback_data=f"reschedule_task:{short_id}"
                ),
            ])
        keyboard.append([
            InlineKeyboardButton("❌ Cancelar", callback_data="reschedule_cancel"),
        ])

        await update.message.reply_html(
            "📅 <b>Reprogramar tarea</b>\n\n"
            "Selecciona la tarea que quieres mover:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        context.user_data["pending_reschedule"] = matching
    else:
        await update.message.reply_html(
            f"🔍 No encontré tareas que coincidan con: <i>{task_name}</i>"
        )


# ==================== APPLICATION SETUP ====================


def create_application() -> Application:
    """Crea y configura la aplicación de Telegram."""
    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .build()
    )

    # Command handlers básicos
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("doing", doing_command))
    application.add_handler(CommandHandler("done", done_command))
    application.add_handler(CommandHandler("block", block_command))
    application.add_handler(CommandHandler("inbox", inbox_command))
    application.add_handler(CommandHandler("projects", projects_command))

    # Conversation handlers (flujos conversacionales)
    # Orden importante: los más específicos primero

    # 1. Deep Work (/deepwork, /focus)
    application.add_handler(get_deepwork_conversation_handler())

    # 2. Gym (/gym, /workout)
    application.add_handler(get_gym_conversation_handler())

    # 3. Nutrición (/food, /nutrition, /comida)
    application.add_handler(get_nutrition_conversation_handler())

    # 4. Análisis de compras (detecta $precio o "pesos")
    application.add_handler(get_purchase_conversation_handler())

    # 5. Voice handler - transcribe y procesa mensajes de voz
    application.add_handler(
        MessageHandler(filters.VOICE | filters.AUDIO, handle_voice)
    )

    # 6. Message handler principal - usa IntentRouter para clasificar y enrutar
    # (El inbox se maneja como fallback dentro de handle_message)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    # 7. Callback handler GLOBAL para todos los botones inline
    # IMPORTANTE: Este handler debe estar al final y capturar TODOS los callbacks
    # Los ConversationHandlers tienen sus propios CallbackQueryHandlers internos
    # pero este maneja los callbacks que no están dentro de una conversación activa
    application.add_handler(CallbackQueryHandler(handle_callback))

    return application


async def get_application() -> Application:
    """Obtiene la instancia de la aplicación inicializada."""
    global _application, _initialized

    if _application is None:
        _application = create_application()

    if not _initialized:
        await _application.initialize()
        _initialized = True

    return _application
