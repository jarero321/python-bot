"""SpendingAnalyzer Agent - Analiza compras potenciales."""

import logging
import re
from dataclasses import dataclass
from enum import Enum

import dspy

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class AnalyzeSpending(dspy.Signature):
    """Analiza una compra potencial."""

    purchase_description: str = dspy.InputField(
        desc="Descripción del item y precio"
    )
    monthly_budget: float = dspy.InputField(
        desc="Presupuesto mensual disponible"
    )
    current_debt: float = dspy.InputField(
        desc="Deuda actual total"
    )

    necessity_score: int = dspy.OutputField(
        desc="Puntuación de necesidad de 1-10"
    )
    budget_impact: str = dspy.OutputField(
        desc="Impacto en el presupuesto: minimal, moderate, significant, critical"
    )
    recommendation: str = dspy.OutputField(
        desc="Recomendación: buy, wait, wishlist, skip"
    )
    honest_questions: str = dspy.OutputField(
        desc="2-3 preguntas honestas para reflexionar sobre la compra"
    )


class SpendingRecommendation(str, Enum):
    """Recomendaciones de compra."""

    BUY = "buy"
    WAIT = "wait"
    WISHLIST = "wishlist"
    SKIP = "skip"


class BudgetImpact(str, Enum):
    """Impacto en el presupuesto."""

    MINIMAL = "minimal"
    MODERATE = "moderate"
    SIGNIFICANT = "significant"
    CRITICAL = "critical"


@dataclass
class SpendingAnalysisResult:
    """Resultado del análisis de una compra."""

    amount: float
    necessity_score: int  # 1-10
    budget_impact: BudgetImpact
    recommendation: SpendingRecommendation
    honest_questions: list[str]
    budget_after_purchase: float
    debt_payment_impact: str  # Cuánto retrasaría el pago de deuda


@dataclass
class SpendingAnalysisExtended(SpendingAnalysisResult):
    """Resultado extendido para integración con FinanceEnricher."""

    is_essential: bool = False
    category: str = "general"
    alternatives: list[str] | None = None
    wait_suggestion: str = ""

    def __post_init__(self):
        if self.alternatives is None:
            self.alternatives = []


class SpendingAnalyzerAgent(BaseAgent):
    """Agent para analizar compras potenciales."""

    name = "SpendingAnalyzer"

    def __init__(
        self,
        monthly_budget: float = 15000.0,  # Default para México
        current_debt: float = 0.0,
    ):
        super().__init__()
        self.analyzer = dspy.ChainOfThought(AnalyzeSpending)
        self.monthly_budget = monthly_budget
        self.current_debt = current_debt

    def set_financial_context(
        self,
        monthly_budget: float,
        current_debt: float,
    ) -> None:
        """Actualiza el contexto financiero."""
        self.monthly_budget = monthly_budget
        self.current_debt = current_debt

    async def execute(
        self,
        message: str,
        monthly_budget: float | None = None,
        current_debt: float | None = None,
    ) -> SpendingAnalysisResult:
        """
        Analiza una compra potencial.

        Args:
            message: Descripción de la compra (debe incluir precio)
            monthly_budget: Presupuesto mensual (usa default si no se especifica)
            current_debt: Deuda actual (usa default si no se especifica)

        Returns:
            SpendingAnalysisResult con el análisis completo
        """
        budget = monthly_budget or self.monthly_budget
        debt = current_debt or self.current_debt

        # Extraer monto del mensaje
        amount = self._extract_amount(message)
        if amount is None:
            self.logger.warning("No se pudo extraer monto del mensaje")
            amount = 0.0

        self.logger.info(f"Analizando compra de ${amount:,.2f}")

        # Ejecutar análisis con DSPy
        analysis = self.analyzer(
            purchase_description=message,
            monthly_budget=budget,
            current_debt=debt,
        )

        # Parsear resultados
        try:
            necessity_score = int(analysis.necessity_score)
            necessity_score = max(1, min(10, necessity_score))
        except (ValueError, TypeError):
            necessity_score = 5

        try:
            budget_impact = BudgetImpact(analysis.budget_impact.lower())
        except ValueError:
            budget_impact = self._calculate_budget_impact(amount, budget)

        try:
            recommendation = SpendingRecommendation(analysis.recommendation.lower())
        except ValueError:
            recommendation = self._calculate_recommendation(
                necessity_score, budget_impact
            )

        # Parsear preguntas honestas
        questions = self._parse_questions(analysis.honest_questions)

        # Calcular impacto en deuda
        debt_impact = self._calculate_debt_impact(amount, debt)

        return SpendingAnalysisResult(
            amount=amount,
            necessity_score=necessity_score,
            budget_impact=budget_impact,
            recommendation=recommendation,
            honest_questions=questions,
            budget_after_purchase=budget - amount,
            debt_payment_impact=debt_impact,
        )

    def _extract_amount(self, message: str) -> float | None:
        """Extrae el monto de un mensaje."""
        # Patrones comunes de precios en español/México
        patterns = [
            r"\$\s*([\d,]+(?:\.\d{2})?)",  # $1,500 o $1500.00
            r"([\d,]+(?:\.\d{2})?)\s*(?:pesos|mxn)",  # 1500 pesos
            r"([\d,]+(?:\.\d{2})?)\s*(?:dlls?|usd|dólares)",  # USD
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(",", "")
                try:
                    return float(amount_str)
                except ValueError:
                    continue

        return None

    def _calculate_budget_impact(
        self,
        amount: float,
        budget: float,
    ) -> BudgetImpact:
        """Calcula el impacto en el presupuesto."""
        if budget == 0:
            return BudgetImpact.CRITICAL

        percentage = (amount / budget) * 100

        if percentage < 5:
            return BudgetImpact.MINIMAL
        elif percentage < 15:
            return BudgetImpact.MODERATE
        elif percentage < 30:
            return BudgetImpact.SIGNIFICANT
        else:
            return BudgetImpact.CRITICAL

    def _calculate_recommendation(
        self,
        necessity_score: int,
        budget_impact: BudgetImpact,
    ) -> SpendingRecommendation:
        """Calcula la recomendación basada en necesidad e impacto."""
        impact_scores = {
            BudgetImpact.MINIMAL: 1,
            BudgetImpact.MODERATE: 2,
            BudgetImpact.SIGNIFICANT: 3,
            BudgetImpact.CRITICAL: 4,
        }

        impact_score = impact_scores.get(budget_impact, 2)

        # Matriz de decisión simple
        if necessity_score >= 8 and impact_score <= 2:
            return SpendingRecommendation.BUY
        elif necessity_score >= 6 and impact_score <= 3:
            return SpendingRecommendation.WAIT
        elif necessity_score >= 4:
            return SpendingRecommendation.WISHLIST
        else:
            return SpendingRecommendation.SKIP

    def _parse_questions(self, questions_str: str) -> list[str]:
        """Parsea las preguntas honestas del string."""
        # Intentar dividir por varios separadores
        questions = []

        if "|" in questions_str:
            questions = questions_str.split("|")
        elif "\n" in questions_str:
            questions = questions_str.split("\n")
        elif "?" in questions_str:
            # Dividir por signos de interrogación
            parts = questions_str.split("?")
            questions = [p.strip() + "?" for p in parts if p.strip()]
        else:
            questions = [questions_str]

        # Limpiar y filtrar
        questions = [q.strip() for q in questions if q.strip()]
        return questions[:3]  # Máximo 3 preguntas

    def _calculate_debt_impact(self, amount: float, debt: float) -> str:
        """Calcula el impacto en el pago de la deuda."""
        if debt == 0:
            return "Sin impacto (sin deuda activa)"

        # Asumiendo que se destinaría el monto a pagar deuda
        debt_percentage = (amount / debt) * 100

        if debt_percentage >= 10:
            return f"Podrías reducir tu deuda un {debt_percentage:.1f}% con este dinero"
        elif debt_percentage >= 5:
            return f"Representa {debt_percentage:.1f}% de tu deuda actual"
        else:
            return "Impacto mínimo en tu deuda"

    async def analyze_purchase(
        self,
        description: str,
        amount: float,
        financial_context: dict | None = None,
    ) -> "SpendingAnalysisExtended":
        """
        Analiza una compra potencial con contexto financiero.

        Este método es un wrapper para integrarse con el FinanceEnricher.

        Args:
            description: Descripción del item
            amount: Monto de la compra
            financial_context: Contexto financiero opcional

        Returns:
            SpendingAnalysisExtended con análisis completo
        """
        budget = (financial_context or {}).get("monthly_budget", self.monthly_budget)
        debt = (financial_context or {}).get("pending_debts", self.current_debt)

        # Construir mensaje con monto
        message = f"{description} por ${amount:,.0f}"

        # Ejecutar análisis base
        base_result = await self.execute(message, budget, debt)

        # Extender con más información
        return SpendingAnalysisExtended(
            amount=base_result.amount,
            necessity_score=base_result.necessity_score,
            budget_impact=base_result.budget_impact,
            recommendation=base_result.recommendation,
            honest_questions=base_result.honest_questions,
            budget_after_purchase=base_result.budget_after_purchase,
            debt_payment_impact=base_result.debt_payment_impact,
            is_essential=base_result.necessity_score >= 8,
            category=self._guess_category(description),
            alternatives=self._generate_alternatives(description, amount),
            wait_suggestion=self._generate_wait_suggestion(base_result.recommendation),
        )

    def _guess_category(self, description: str) -> str:
        """Intenta adivinar la categoría del gasto."""
        description_lower = description.lower()

        categories = {
            "tecnología": ["phone", "celular", "laptop", "tablet", "airpods", "headphones", "audifonos"],
            "entretenimiento": ["juego", "game", "netflix", "spotify", "suscripcion"],
            "ropa": ["ropa", "zapato", "tenis", "camisa", "pantalon", "vestido"],
            "comida": ["comida", "restaurante", "cafe", "almuerzo"],
            "transporte": ["uber", "taxi", "gasolina", "pasaje"],
            "salud": ["medicina", "doctor", "gym", "vitamina"],
        }

        for category, keywords in categories.items():
            if any(kw in description_lower for kw in keywords):
                return category

        return "general"

    def _generate_alternatives(self, description: str, amount: float) -> list[str]:
        """Genera alternativas a la compra."""
        alternatives = []

        if amount >= 3000:
            alternatives.append(f"Esperar al Buen Fin o Black Friday para descuentos")

        if amount >= 1000:
            alternatives.append("Buscar opciones reacondicionadas o de segunda mano")

        alternatives.append("Comparar precios en diferentes tiendas antes de decidir")

        return alternatives

    def _generate_wait_suggestion(self, recommendation: SpendingRecommendation) -> str:
        """Genera sugerencia de espera según la recomendación."""
        suggestions = {
            SpendingRecommendation.BUY: "Si realmente lo necesitas, adelante. Solo asegúrate de que cabe en tu presupuesto.",
            SpendingRecommendation.WAIT: "Aplica la regla de las 24-48 horas. Si sigues queriéndolo, reconsidera.",
            SpendingRecommendation.WISHLIST: "Agrégalo a tu wishlist y revísalo el día de pago.",
            SpendingRecommendation.SKIP: "Mejor destina ese dinero a tus deudas o ahorros.",
        }
        return suggestions.get(recommendation, "")

    def format_analysis_message(self, result: SpendingAnalysisResult) -> str:
        """Formatea el resultado como mensaje para el usuario."""
        # Emojis según recomendación
        rec_emoji = {
            SpendingRecommendation.BUY: "✅",
            SpendingRecommendation.WAIT: "⏳",
            SpendingRecommendation.WISHLIST: "📋",
            SpendingRecommendation.SKIP: "❌",
        }

        rec_text = {
            SpendingRecommendation.BUY: "Comprar",
            SpendingRecommendation.WAIT: "Esperar",
            SpendingRecommendation.WISHLIST: "Agregar a wishlist",
            SpendingRecommendation.SKIP: "No comprar",
        }

        impact_emoji = {
            BudgetImpact.MINIMAL: "🟢",
            BudgetImpact.MODERATE: "🟡",
            BudgetImpact.SIGNIFICANT: "🟠",
            BudgetImpact.CRITICAL: "🔴",
        }

        message = f"""
💰 <b>Análisis de Compra</b>

<b>Monto:</b> ${result.amount:,.2f}
<b>Necesidad:</b> {result.necessity_score}/10
<b>Impacto:</b> {impact_emoji[result.budget_impact]} {result.budget_impact.value.capitalize()}
<b>Recomendación:</b> {rec_emoji[result.recommendation]} {rec_text[result.recommendation]}

<b>Después de comprar:</b> ${result.budget_after_purchase:,.2f} disponibles
<b>Deuda:</b> {result.debt_payment_impact}

<b>Preguntas para reflexionar:</b>
"""
        for i, q in enumerate(result.honest_questions, 1):
            message += f"{i}. {q}\n"

        return message.strip()


# Singleton
_spending_analyzer: SpendingAnalyzerAgent | None = None


def get_spending_analyzer(
    monthly_budget: float = 15000.0,
    current_debt: float = 0.0,
) -> SpendingAnalyzerAgent:
    """Obtiene la instancia del SpendingAnalyzer."""
    global _spending_analyzer
    if _spending_analyzer is None:
        _spending_analyzer = SpendingAnalyzerAgent(monthly_budget, current_debt)
    return _spending_analyzer
