"""
Finance Handlers - Gastos y deudas.

Handlers para análisis de compras, registro de gastos y consulta de deudas.
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
from app.core.parsing import DSPyParser
from app.services.notion import get_notion_service

logger = logging.getLogger(__name__)


@intent_handler(UserIntent.EXPENSE_ANALYZE)
class ExpenseAnalyzeHandler(BaseIntentHandler):
    """Handler para análisis de compras potenciales."""

    name = "ExpenseAnalyzeHandler"
    intents = [UserIntent.EXPENSE_ANALYZE]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        entities = self.get_entities(intent_result)
        text = self.get_raw_message(intent_result)

        amount = entities.get("amount", "?")
        item = entities.get("item", text[:50])

        # Enviar mensaje inicial de procesamiento
        await update.message.reply_html(
            f"💰 <b>Análisis de compra</b>\n\n"
            f"Item: <i>{item}</i>\n"
            f"Precio: ${amount}\n\n"
            f"Analizando si es buena idea...",
        )

        # TODO: Integrar con SpendingAnalyzer para análisis real
        # Por ahora, preguntas reflexivas

        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Sí, lo compro",
                    callback_data=f"expense_approve:{amount}:{item[:20]}",
                ),
                InlineKeyboardButton(
                    "⏳ Esperar 24h",
                    callback_data="expense_wait",
                ),
            ],
            [
                InlineKeyboardButton(
                    "❌ No lo necesito",
                    callback_data="expense_reject",
                ),
            ],
        ]

        message = (
            "🤔 <b>Preguntas para reflexionar:</b>\n\n"
            "• ¿Realmente lo necesitas o solo lo quieres?\n"
            "• ¿Tienes algo similar que cumpla la función?\n"
            "• ¿Cómo te sentirías en una semana si no lo compras?\n\n"
            "<i>Tip: La regla de las 24 horas funciona muy bien para "
            "compras impulsivas.</i>"
        )

        return HandlerResponse(
            message=message,
            keyboard=InlineKeyboardMarkup(keyboard),
            already_sent=True,  # Ya enviamos el primer mensaje
        )


@intent_handler(UserIntent.EXPENSE_LOG)
class ExpenseLogHandler(BaseIntentHandler):
    """Handler para registrar gastos."""

    name = "ExpenseLogHandler"
    intents = [UserIntent.EXPENSE_LOG]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
        entities = self.get_entities(intent_result)
        text = self.get_raw_message(intent_result)

        amount = DSPyParser.extract_price(text) or entities.get("amount", "?")
        category = entities.get("category", "general")
        description = entities.get("description", text[:50])

        # Guardar en context para confirmar
        context.user_data["pending_expense"] = {
            "amount": amount,
            "category": category,
            "description": description,
        }

        keyboard = [
            [
                InlineKeyboardButton(
                    "🍔 Comida",
                    callback_data="expense_cat:comida",
                ),
                InlineKeyboardButton(
                    "🚗 Transporte",
                    callback_data="expense_cat:transporte",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🛒 Compras",
                    callback_data="expense_cat:compras",
                ),
                InlineKeyboardButton(
                    "🎮 Entretenimiento",
                    callback_data="expense_cat:entretenimiento",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📦 Servicios",
                    callback_data="expense_cat:servicios",
                ),
                InlineKeyboardButton(
                    "💊 Salud",
                    callback_data="expense_cat:salud",
                ),
            ],
            [
                InlineKeyboardButton(
                    "❌ Cancelar",
                    callback_data="expense_cancel",
                ),
            ],
        ]

        message = (
            f"💸 <b>Registrar gasto</b>\n\n"
            f"Monto: <b>${amount}</b>\n"
            f"Descripción: <i>{description}</i>\n\n"
            f"Selecciona la categoría:"
        )

        return HandlerResponse(
            message=message,
            keyboard=InlineKeyboardMarkup(keyboard),
        )


@intent_handler(UserIntent.DEBT_QUERY)
class DebtQueryHandler(BaseIntentHandler):
    """Handler para consultar deudas."""

    name = "DebtQueryHandler"
    intents = [UserIntent.DEBT_QUERY]

    async def handle(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        intent_result: Any,
    ) -> HandlerResponse:
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

        return HandlerResponse(message=msg)
