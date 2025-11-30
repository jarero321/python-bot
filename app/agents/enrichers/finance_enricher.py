"""
Finance Enricher - Enriquece intents de finanzas.

Integra:
- SpendingAnalyzerAgent: Analiza compras potenciales
- DebtStrategistAgent: Estrategia de deudas
"""

import logging
import re
from typing import Any

from app.agents.enrichers.base import BaseEnricher, EnrichmentResult
from app.agents.intent_router import UserIntent
from app.agents.spending_analyzer import SpendingAnalyzerAgent
from app.agents.debt_strategist import DebtStrategistAgent

logger = logging.getLogger(__name__)


class FinanceEnricher(BaseEnricher):
    """Enricher para finanzas - usa SpendingAnalyzer y DebtStrategist."""

    name = "FinanceEnricher"
    intents = [
        UserIntent.EXPENSE_ANALYZE,
        UserIntent.EXPENSE_LOG,
        UserIntent.DEBT_QUERY,
    ]

    def __init__(self):
        super().__init__()
        self._spending_analyzer: SpendingAnalyzerAgent | None = None
        self._debt_strategist: DebtStrategistAgent | None = None

    @property
    def spending_analyzer(self) -> SpendingAnalyzerAgent:
        if self._spending_analyzer is None:
            self._spending_analyzer = SpendingAnalyzerAgent()
        return self._spending_analyzer

    @property
    def debt_strategist(self) -> DebtStrategistAgent:
        if self._debt_strategist is None:
            self._debt_strategist = DebtStrategistAgent()
        return self._debt_strategist

    async def enrich(
        self,
        intent: UserIntent,
        message: str,
        entities: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> EnrichmentResult:
        """Enriquece intent de finanzas."""
        result = EnrichmentResult(enricher_name=self.name)

        if intent == UserIntent.EXPENSE_ANALYZE:
            await self._enrich_expense_analyze(message, entities, result)
        elif intent == UserIntent.DEBT_QUERY:
            await self._enrich_debt_query(message, entities, result, context)
        elif intent == UserIntent.EXPENSE_LOG:
            self._enrich_expense_log(message, entities, result)

        return result

    async def _enrich_expense_analyze(
        self,
        message: str,
        entities: dict[str, Any],
        result: EnrichmentResult,
    ) -> None:
        """Enriquece análisis de compra potencial."""
        # Extraer monto si no está en entities
        amount = entities.get("amount")
        if not amount:
            amount = self._extract_amount(message)

        item = entities.get("item", message)

        try:
            # Obtener contexto financiero (aquí deberías obtener de Notion)
            financial_context = {
                "monthly_budget": 15000,  # TODO: Obtener de Notion
                "current_savings": 5000,
                "pending_debts": 3000,
            }

            analysis = await self.spending_analyzer.analyze_purchase(
                description=item,
                amount=float(amount) if amount else 0,
                financial_context=financial_context,
            )

            result.financial_analysis = {
                "item": item,
                "amount": amount,
                "is_essential": analysis.is_essential,
                "category": analysis.category,
                "impact": analysis.budget_impact,
                "recommendation": analysis.recommendation,
                "honest_questions": analysis.honest_questions,
                "alternatives": analysis.alternatives,
                "wait_suggestion": analysis.wait_suggestion,
            }
            result.agents_used.append("SpendingAnalyzer")

        except Exception as e:
            self.logger.warning(f"Error en SpendingAnalyzer: {e}")
            result.financial_analysis = {
                "item": item,
                "amount": amount,
                "error": str(e),
            }

    async def _enrich_debt_query(
        self,
        message: str,
        entities: dict[str, Any],
        result: EnrichmentResult,
        context: dict[str, Any] | None,
    ) -> None:
        """Enriquece consulta de deudas."""
        try:
            # TODO: Obtener deudas de Notion
            debts = []  # Deberían venir de Notion

            if debts:
                strategy = await self.debt_strategist.create_strategy(
                    debts=debts,
                    monthly_payment_capacity=5000,
                )

                result.financial_analysis = {
                    "total_debt": strategy.total_debt,
                    "recommended_strategy": strategy.strategy.value,
                    "payment_plan": [
                        {
                            "debt": p.debt_name,
                            "monthly_payment": p.monthly_payment,
                            "months_to_payoff": p.months_to_payoff,
                        }
                        for p in strategy.payment_plan
                    ],
                    "monthly_savings": strategy.monthly_savings,
                    "motivation": strategy.motivation_message,
                }
                result.agents_used.append("DebtStrategist")
            else:
                result.financial_analysis = {
                    "message": "No hay deudas registradas",
                }

        except Exception as e:
            self.logger.warning(f"Error en DebtStrategist: {e}")

    def _enrich_expense_log(
        self,
        message: str,
        entities: dict[str, Any],
        result: EnrichmentResult,
    ) -> None:
        """Enriquece registro de gasto."""
        amount = entities.get("amount") or self._extract_amount(message)
        result.financial_analysis = {
            "amount": amount,
            "description": entities.get("item", message),
            "type": "expense_log",
        }

    def _extract_amount(self, message: str) -> str | None:
        """Extrae monto del mensaje."""
        patterns = [
            r'\$\s*([\d,]+(?:\.\d{2})?)',
            r'([\d,]+)\s*pesos',
            r'([\d,]+)\s*mxn',
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1).replace(",", "")

        return None
