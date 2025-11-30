"""Teclados inline para el bot de Telegram."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ==================== CONFIRMACIÓN GENERAL ====================

def confirm_keyboard(
    confirm_data: str = "confirm",
    cancel_data: str = "cancel",
    confirm_text: str = "✅ Confirmar",
    cancel_text: str = "❌ Cancelar",
) -> InlineKeyboardMarkup:
    """Teclado de confirmación simple con textos personalizables."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(confirm_text, callback_data=confirm_data),
            InlineKeyboardButton(cancel_text, callback_data=cancel_data),
        ]
    ])


def yes_no_keyboard(
    yes_data: str = "yes",
    no_data: str = "no",
) -> InlineKeyboardMarkup:
    """Teclado de Sí/No."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👍 Sí", callback_data=yes_data),
            InlineKeyboardButton("👎 No", callback_data=no_data),
        ]
    ])


# ==================== TAREAS ====================

def task_actions_keyboard(task_id: str) -> InlineKeyboardMarkup:
    """Acciones disponibles para una tarea."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("▶️ Empezar", callback_data=f"task_start:{task_id}"),
            InlineKeyboardButton("✅ Completar", callback_data=f"task_done:{task_id}"),
        ],
        [
            InlineKeyboardButton("🚫 Bloquear", callback_data=f"task_block:{task_id}"),
            InlineKeyboardButton("📝 Editar", callback_data=f"task_edit:{task_id}"),
        ],
    ])


def task_status_keyboard(task_id: str) -> InlineKeyboardMarkup:
    """Cambiar estado de una tarea."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Pendiente", callback_data=f"status_pending:{task_id}"),
            InlineKeyboardButton("▶️ En Progreso", callback_data=f"status_progress:{task_id}"),
        ],
        [
            InlineKeyboardButton("✅ Completada", callback_data=f"status_done:{task_id}"),
            InlineKeyboardButton("🚫 Bloqueada", callback_data=f"status_blocked:{task_id}"),
        ],
    ])


def task_priority_keyboard(task_id: str) -> InlineKeyboardMarkup:
    """Seleccionar prioridad de una tarea."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔴 Alta", callback_data=f"priority_high:{task_id}"),
            InlineKeyboardButton("🟡 Media", callback_data=f"priority_medium:{task_id}"),
            InlineKeyboardButton("🟢 Baja", callback_data=f"priority_low:{task_id}"),
        ],
    ])


# ==================== INBOX / CLASIFICACIÓN ====================

def inbox_classification_keyboard(item_id: str) -> InlineKeyboardMarkup:
    """Opciones para clasificar un item del inbox."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Tarea", callback_data=f"classify_task:{item_id}"),
            InlineKeyboardButton("💡 Idea", callback_data=f"classify_idea:{item_id}"),
        ],
        [
            InlineKeyboardButton("📅 Evento", callback_data=f"classify_event:{item_id}"),
            InlineKeyboardButton("📝 Nota", callback_data=f"classify_note:{item_id}"),
        ],
        [
            InlineKeyboardButton("🗑️ Descartar", callback_data=f"classify_discard:{item_id}"),
        ],
    ])


def project_selection_keyboard(
    projects: list[tuple[str, str]],  # Lista de (id, nombre)
    item_id: str,
) -> InlineKeyboardMarkup:
    """Seleccionar proyecto para una tarea."""
    buttons = []
    for project_id, project_name in projects[:6]:  # Máximo 6 proyectos
        buttons.append([
            InlineKeyboardButton(
                f"📁 {project_name[:20]}",
                callback_data=f"project:{item_id}:{project_id[:8]}",
            )
        ])
    buttons.append([
        InlineKeyboardButton("➕ Sin proyecto", callback_data=f"project:{item_id}:none"),
    ])
    return InlineKeyboardMarkup(buttons)


# ==================== RECORDATORIOS ====================

def reminder_actions_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    """Acciones para un recordatorio."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Hecho", callback_data=f"reminder_done:{reminder_id}"),
            InlineKeyboardButton("⏰ Snooze 30m", callback_data=f"reminder_snooze:{reminder_id}:30"),
        ],
        [
            InlineKeyboardButton("⏰ Snooze 1h", callback_data=f"reminder_snooze:{reminder_id}:60"),
            InlineKeyboardButton("🗑️ Cancelar", callback_data=f"reminder_cancel:{reminder_id}"),
        ],
    ])


def snooze_options_keyboard(reminder_id: int) -> InlineKeyboardMarkup:
    """Opciones de snooze para un recordatorio."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("15 min", callback_data=f"snooze:{reminder_id}:15"),
            InlineKeyboardButton("30 min", callback_data=f"snooze:{reminder_id}:30"),
            InlineKeyboardButton("1 hora", callback_data=f"snooze:{reminder_id}:60"),
        ],
        [
            InlineKeyboardButton("2 horas", callback_data=f"snooze:{reminder_id}:120"),
            InlineKeyboardButton("Mañana", callback_data=f"snooze:{reminder_id}:tomorrow"),
        ],
    ])


# ==================== GYM ====================

def gym_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Confirmación de ir al gym."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💪 Ya voy", callback_data="gym_going"),
            InlineKeyboardButton("⏰ 15 min más", callback_data="gym_snooze:15"),
        ],
        [
            InlineKeyboardButton("🔄 Reprogramar", callback_data="gym_reschedule"),
            InlineKeyboardButton("❌ Skip hoy", callback_data="gym_skip"),
        ],
    ])


def workout_rating_keyboard() -> InlineKeyboardMarkup:
    """Calificación del workout."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("😫 Malo", callback_data="workout_rating:1"),
            InlineKeyboardButton("😐 Regular", callback_data="workout_rating:2"),
            InlineKeyboardButton("🙂 Bueno", callback_data="workout_rating:3"),
        ],
        [
            InlineKeyboardButton("😄 Muy bueno", callback_data="workout_rating:4"),
            InlineKeyboardButton("🔥 Excelente", callback_data="workout_rating:5"),
        ],
    ])


# ==================== NUTRICIÓN ====================

def meal_type_keyboard() -> InlineKeyboardMarkup:
    """Tipo de comida."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌅 Desayuno", callback_data="meal_breakfast"),
            InlineKeyboardButton("🌞 Almuerzo", callback_data="meal_lunch"),
        ],
        [
            InlineKeyboardButton("🌙 Cena", callback_data="meal_dinner"),
            InlineKeyboardButton("🍎 Snack", callback_data="meal_snack"),
        ],
    ])


def nutrition_rating_keyboard() -> InlineKeyboardMarkup:
    """Calificación de nutrición del día."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("😬 Mal día", callback_data="nutrition_rating:1"),
            InlineKeyboardButton("😐 Regular", callback_data="nutrition_rating:2"),
            InlineKeyboardButton("👍 Bien", callback_data="nutrition_rating:3"),
        ],
        [
            InlineKeyboardButton("💪 Muy bien", callback_data="nutrition_rating:4"),
            InlineKeyboardButton("🏆 Perfecto", callback_data="nutrition_rating:5"),
        ],
    ])


# ==================== FINANZAS ====================

def spending_decision_keyboard() -> InlineKeyboardMarkup:
    """Decisión de compra."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Comprar", callback_data="spend_buy"),
            InlineKeyboardButton("📋 Wishlist", callback_data="spend_wishlist"),
        ],
        [
            InlineKeyboardButton("⏳ Esperar", callback_data="spend_wait"),
            InlineKeyboardButton("❌ No comprar", callback_data="spend_skip"),
        ],
    ])


def expense_category_keyboard() -> InlineKeyboardMarkup:
    """Categorías de gasto."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🍔 Comida", callback_data="expense_food"),
            InlineKeyboardButton("🚗 Transporte", callback_data="expense_transport"),
        ],
        [
            InlineKeyboardButton("🏠 Casa", callback_data="expense_home"),
            InlineKeyboardButton("🎮 Entretenimiento", callback_data="expense_entertainment"),
        ],
        [
            InlineKeyboardButton("💊 Salud", callback_data="expense_health"),
            InlineKeyboardButton("📚 Educación", callback_data="expense_education"),
        ],
        [
            InlineKeyboardButton("🛒 Otro", callback_data="expense_other"),
        ],
    ])


# ==================== CHECK-IN ====================

def checkin_status_keyboard() -> InlineKeyboardMarkup:
    """Estado del check-in horario."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Todo bien", callback_data="checkin_good"),
            InlineKeyboardButton("🔄 Cambio de tarea", callback_data="checkin_switch"),
        ],
        [
            InlineKeyboardButton("🚫 Bloqueado", callback_data="checkin_blocked"),
            InlineKeyboardButton("☕ Tomando break", callback_data="checkin_break"),
        ],
    ])


def energy_level_keyboard() -> InlineKeyboardMarkup:
    """Nivel de energía."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("😴 1", callback_data="energy:1"),
            InlineKeyboardButton("😔 2", callback_data="energy:2"),
            InlineKeyboardButton("😐 3", callback_data="energy:3"),
            InlineKeyboardButton("🙂 4", callback_data="energy:4"),
            InlineKeyboardButton("⚡ 5", callback_data="energy:5"),
        ],
    ])


# ==================== ESTUDIO ====================

def study_options_keyboard(suggestion: dict) -> InlineKeyboardMarkup:
    """Teclado de opciones de estudio."""
    buttons = []

    # Botón principal si hay sugerencia
    if suggestion.get("topic") and suggestion["topic"] != "Sin proyectos de estudio definidos":
        project_id = suggestion.get("project_id", "none")
        buttons.append([
            InlineKeyboardButton(
                f"✅ Estudiar {suggestion['topic'][:20]}",
                callback_data=f"study_start_{project_id[:8] if project_id else 'none'}",
            ),
        ])

    # Alternativas
    for i, alt in enumerate(suggestion.get("alternatives", [])[:2]):
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


# ==================== PAYDAY ====================

def payday_actions_keyboard() -> InlineKeyboardMarkup:
    """Teclado de acciones para payday."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Seguir plan", callback_data="payday_follow_plan"),
            InlineKeyboardButton("✏️ Ajustar", callback_data="payday_adjust"),
        ],
        [
            InlineKeyboardButton("📊 Ver deudas", callback_data="payday_view_debts"),
            InlineKeyboardButton("⏭️ Recordar después", callback_data="payday_later"),
        ],
    ])


# ==================== MENÚ PRINCIPAL ====================

def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Menú principal del bot."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Tareas de hoy", callback_data="menu_today"),
            InlineKeyboardButton("➕ Nueva tarea", callback_data="menu_add"),
        ],
        [
            InlineKeyboardButton("💪 Gym", callback_data="menu_gym"),
            InlineKeyboardButton("🍽️ Nutrición", callback_data="menu_nutrition"),
        ],
        [
            InlineKeyboardButton("💰 Finanzas", callback_data="menu_finance"),
            InlineKeyboardButton("📊 Resumen", callback_data="menu_summary"),
        ],
    ])
