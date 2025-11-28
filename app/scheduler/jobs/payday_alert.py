"""Payday Alert Jobs - Alertas de quincena."""

import logging
from datetime import datetime

from app.config import get_settings
from app.services.telegram import get_telegram_service
from app.services.notion import get_notion_service
from app.bot.keyboards import payday_actions_keyboard

logger = logging.getLogger(__name__)
settings = get_settings()

# Datos financieros de Carlos (de Documentacion.MD)
CARLOS_FINANCE = {
    "income_per_fortnight": 25000,  # Quincena PayCash
    "fixed_expenses": {
        "Carro": 12000,
        "Starlink": 1000,
        "Gym": 400,
        "Claude Max": 2000,
        "PS Plus": 150,
        "Comida Base": 8000,
    },
    "debt_minimums": {
        "Tarjeta Banco": 4000,
        "Coppel": 1800,
        "Mercado Libre": 1500,
    },
}


async def pre_payday_job() -> None:
    """
    Envía alerta pre-quincena para planificar distribución.

    Se ejecuta los días 13 y 28.
    """
    logger.info("Ejecutando Pre-Payday Alert...")

    telegram = get_telegram_service()
    notion = get_notion_service()

    try:
        # Obtener resumen financiero
        financial_summary = await notion.get_monthly_summary()
        debt_summary = await notion.get_debt_summary()

        # Generar plan de distribución
        distribution = _calculate_distribution(
            income=CARLOS_FINANCE["income_per_fortnight"],
            fixed=CARLOS_FINANCE["fixed_expenses"],
            debt_mins=CARLOS_FINANCE["debt_minimums"],
            debt_summary=debt_summary,
        )

        # Formatear mensaje
        message = _format_pre_payday_message(distribution, debt_summary)

        await telegram.send_message_with_keyboard(
            text=message,
            reply_markup=payday_actions_keyboard(),
        )

        logger.info("Pre-Payday Alert enviado")

    except Exception as e:
        logger.error(f"Error en Pre-Payday Alert: {e}")


async def post_payday_job() -> None:
    """
    Envía recordatorio post-quincena para registrar distribución.

    Se ejecuta los días 15 y 30/31.
    """
    logger.info("Ejecutando Post-Payday Alert...")

    telegram = get_telegram_service()

    try:
        message = _format_post_payday_message()

        await telegram.send_message(text=message)

        logger.info("Post-Payday Alert enviado")

    except Exception as e:
        logger.error(f"Error en Post-Payday Alert: {e}")


def _calculate_distribution(
    income: float,
    fixed: dict,
    debt_mins: dict,
    debt_summary: dict,
) -> dict:
    """Calcula la distribución recomendada del ingreso."""
    # Gastos fijos totales
    total_fixed = sum(fixed.values())

    # Pagos mínimos de deuda
    total_debt_min = sum(debt_mins.values())

    # Lo que queda después de fijos y mínimos
    remaining = income - total_fixed - total_debt_min

    # Recomendación: destinar 70% del restante a deuda extra
    recommended_extra_debt = remaining * 0.7
    available_for_variable = remaining * 0.3

    # Días hasta próxima quincena
    today = datetime.now().day
    if today <= 15:
        days_until_next = 15 - today
    else:
        # Hasta fin de mes (simplificado a 30)
        days_until_next = 30 - today

    # Presupuesto diario
    daily_budget = available_for_variable / max(days_until_next, 1)

    # Prioridad de deuda (la de mayor tasa primero)
    priority_debt = None
    if debt_summary.get("deudas"):
        # Ordenar por tasa de interés descendente
        sorted_debts = sorted(
            debt_summary["deudas"],
            key=lambda d: d.get("tasa", 0),
            reverse=True,
        )
        if sorted_debts:
            priority_debt = sorted_debts[0]

    return {
        "income": income,
        "total_fixed": total_fixed,
        "fixed_breakdown": fixed,
        "total_debt_min": total_debt_min,
        "debt_min_breakdown": debt_mins,
        "remaining": remaining,
        "recommended_extra_debt": recommended_extra_debt,
        "available_for_variable": available_for_variable,
        "daily_budget": daily_budget,
        "days_until_next": days_until_next,
        "priority_debt": priority_debt,
    }


def _format_pre_payday_message(distribution: dict, debt_summary: dict) -> str:
    """Formatea el mensaje pre-quincena."""
    today = datetime.now()
    fortnight = "Q1" if today.day <= 15 else "Q2"
    month = today.strftime("%B")

    message = (
        f"💰 <b>Plan de Quincena</b>\n"
        f"{fortnight} - {month}\n\n"
    )

    # Ingreso
    message += f"📥 <b>Ingreso esperado:</b> ${distribution['income']:,.0f}\n\n"

    # Gastos fijos
    message += "<b>🏠 Gastos Fijos:</b>\n"
    for name, amount in distribution["fixed_breakdown"].items():
        message += f"• {name}: ${amount:,.0f}\n"
    message += f"<b>Total:</b> ${distribution['total_fixed']:,.0f}\n\n"

    # Pagos de deuda mínimos
    message += "<b>💳 Pagos Mínimos Deuda:</b>\n"
    for name, amount in distribution["debt_min_breakdown"].items():
        message += f"• {name}: ${amount:,.0f}\n"
    message += f"<b>Total:</b> ${distribution['total_debt_min']:,.0f}\n\n"

    # Lo que queda
    message += f"<b>💵 Disponible:</b> ${distribution['remaining']:,.0f}\n\n"

    # Recomendación
    message += "<b>📊 Recomendación:</b>\n"

    if distribution["priority_debt"]:
        debt = distribution["priority_debt"]
        message += (
            f"🎯 Abonar ${distribution['recommended_extra_debt']:,.0f} extra a "
            f"<b>{debt['nombre']}</b> (tasa {debt['tasa']}%)\n"
        )

    message += (
        f"💸 Dejar ${distribution['available_for_variable']:,.0f} "
        f"para gastos variables\n"
    )
    message += f"📆 Presupuesto diario: ${distribution['daily_budget']:,.0f}\n\n"

    # Resumen de deuda
    if debt_summary:
        total_debt = debt_summary.get("total_deuda", 0)
        monthly_interest = debt_summary.get("total_interes_mensual", 0)
        message += (
            f"<b>📉 Status Deuda Total:</b>\n"
            f"• Saldo: ${total_debt:,.0f}\n"
            f"• Interés mensual: ${monthly_interest:,.0f}\n"
        )

    message += "\n¿Cómo quieres proceder?"

    return message


def _format_post_payday_message() -> str:
    """Formatea el mensaje post-quincena."""
    message = (
        "✅ <b>Día de Quincena</b>\n\n"
        "¿Ya recibiste tu quincena?\n\n"
        "📝 Por favor registra:\n"
        "1. Monto recibido (si difiere de lo esperado)\n"
        "2. Pagos realizados\n"
        "3. Cualquier gasto extra\n\n"
        "Puedes usar:\n"
        "• /gasto [monto] [descripción]\n"
        "• /ingreso [monto] [descripción]\n"
        "• /deuda [monto] [nombre deuda]\n\n"
        "<i>O simplemente cuéntame qué pagaste y yo lo registro</i>"
    )

    return message


def payday_actions_keyboard():
    """Teclado de acciones para payday."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Seguir plan",
                callback_data="payday_follow_plan",
            ),
            InlineKeyboardButton(
                "✏️ Ajustar",
                callback_data="payday_adjust",
            ),
        ],
        [
            InlineKeyboardButton(
                "📊 Ver deudas",
                callback_data="payday_view_debts",
            ),
            InlineKeyboardButton(
                "⏭️ Recordar después",
                callback_data="payday_later",
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)
