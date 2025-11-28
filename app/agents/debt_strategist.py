"""DebtStrategist Agent - Optimiza estrategia de pago de deudas."""

import logging
from dataclasses import dataclass, field
from enum import Enum

import dspy

from app.agents.base import get_dspy_lm

logger = logging.getLogger(__name__)


class PaymentStrategy(str, Enum):
    """Estrategias de pago de deuda."""

    AVALANCHE = "avalanche"  # Mayor tasa primero
    SNOWBALL = "snowball"  # Menor monto primero
    HYBRID = "hybrid"  # Combinación


class AnalyzeDebtStrategy(dspy.Signature):
    """Analiza deudas y recomienda estrategia óptima de pago."""

    debts_info: str = dspy.InputField(
        desc="Lista de deudas con nombre, monto, tasa de interés y pago mínimo"
    )
    monthly_income: float = dspy.InputField(
        desc="Ingreso mensual total"
    )
    monthly_fixed_expenses: float = dspy.InputField(
        desc="Gastos fijos mensuales (sin deudas)"
    )
    available_for_debt: float = dspy.InputField(
        desc="Dinero mensual disponible para pagar deudas"
    )

    recommended_strategy: str = dspy.OutputField(
        desc="Estrategia recomendada: avalanche, snowball, o hybrid"
    )
    strategy_explanation: str = dspy.OutputField(
        desc="Explicación de por qué esta estrategia es mejor"
    )
    payment_order: str = dspy.OutputField(
        desc="Orden de ataque a las deudas, de primera a última"
    )
    monthly_payment_plan: str = dspy.OutputField(
        desc="Cuánto pagar a cada deuda mensualmente"
    )
    months_to_debt_free: int = dspy.OutputField(
        desc="Meses estimados para quedar libre de deuda"
    )
    total_interest_saved: float = dspy.OutputField(
        desc="Intereses ahorrados vs pagar solo mínimos"
    )


@dataclass
class Debt:
    """Representa una deuda."""

    name: str
    current_amount: float
    interest_rate: float  # Tasa anual como porcentaje
    minimum_payment: float
    priority: int = 0

    @property
    def monthly_interest(self) -> float:
        """Calcula el interés mensual."""
        return self.current_amount * (self.interest_rate / 100) / 12


@dataclass
class PaymentPlan:
    """Plan de pago para una deuda."""

    debt_name: str
    monthly_payment: float
    is_minimum: bool
    extra_payment: float = 0


@dataclass
class DebtStrategyResult:
    """Resultado del análisis de estrategia de deudas."""

    strategy: PaymentStrategy
    explanation: str
    payment_order: list[str]
    monthly_plan: list[PaymentPlan]
    months_to_freedom: int
    total_interest_if_minimum: float
    total_interest_with_plan: float
    interest_saved: float
    milestones: list[dict]


class DebtStrategistAgent:
    """Agente para optimizar pagos de deudas."""

    def __init__(self):
        self.lm = get_dspy_lm()
        dspy.configure(lm=self.lm)
        self.analyzer = dspy.ChainOfThought(AnalyzeDebtStrategy)

        # Datos de Carlos (de Documentacion.MD)
        self.carlos_debts = [
            Debt("Tarjeta Banco", 80000, 60, 4000, priority=1),
            Debt("Coppel", 30000, 50, 1800, priority=2),
            Debt("Mercado Libre", 20000, 40, 1500, priority=3),
            Debt("Carro", 200000, 15, 12000, priority=4),  # Fijo, no adelantar
        ]

    async def analyze_debts(
        self,
        debts: list[Debt] | None = None,
        monthly_income: float = 54500,
        monthly_fixed_expenses: float = 23550,
        available_for_debt: float | None = None,
    ) -> DebtStrategyResult:
        """
        Analiza las deudas y genera estrategia óptima.

        Args:
            debts: Lista de deudas (usa las de Carlos si no se provee)
            monthly_income: Ingreso mensual
            monthly_fixed_expenses: Gastos fijos mensuales
            available_for_debt: Dinero disponible para deudas

        Returns:
            DebtStrategyResult con la estrategia completa
        """
        if debts is None:
            debts = self.carlos_debts

        # Calcular disponible para deudas si no se especifica
        total_minimums = sum(d.minimum_payment for d in debts)
        if available_for_debt is None:
            available_for_debt = monthly_income - monthly_fixed_expenses

        try:
            # Formatear info de deudas para el LLM
            debts_info = self._format_debts_info(debts)

            # Obtener recomendación del LLM
            result = self.analyzer(
                debts_info=debts_info,
                monthly_income=monthly_income,
                monthly_fixed_expenses=monthly_fixed_expenses,
                available_for_debt=available_for_debt,
            )

            # Parsear estrategia
            strategy_map = {
                "avalanche": PaymentStrategy.AVALANCHE,
                "snowball": PaymentStrategy.SNOWBALL,
                "hybrid": PaymentStrategy.HYBRID,
            }
            strategy = strategy_map.get(
                str(result.recommended_strategy).lower(),
                PaymentStrategy.AVALANCHE,
            )

            # Calcular plan detallado
            payment_plan = self._calculate_payment_plan(
                debts, available_for_debt, strategy
            )

            # Calcular proyecciones
            months_minimum = self._calculate_months_minimum_only(debts)
            months_with_plan, interest_with_plan = self._calculate_months_with_plan(
                debts, payment_plan
            )
            interest_minimum = self._calculate_total_interest_minimum(
                debts, months_minimum
            )

            # Calcular milestones
            milestones = self._calculate_milestones(debts, payment_plan)

            # Parsear orden de pago
            payment_order = [
                p.strip()
                for p in str(result.payment_order).split(",")
                if p.strip()
            ]
            if not payment_order:
                payment_order = [d.name for d in sorted(
                    debts, key=lambda x: x.interest_rate, reverse=True
                )]

            return DebtStrategyResult(
                strategy=strategy,
                explanation=str(result.strategy_explanation),
                payment_order=payment_order,
                monthly_plan=payment_plan,
                months_to_freedom=months_with_plan,
                total_interest_if_minimum=interest_minimum,
                total_interest_with_plan=interest_with_plan,
                interest_saved=interest_minimum - interest_with_plan,
                milestones=milestones,
            )

        except Exception as e:
            logger.error(f"Error analizando deudas: {e}")
            return self._create_fallback_result(debts, available_for_debt)

    def _format_debts_info(self, debts: list[Debt]) -> str:
        """Formatea información de deudas para el LLM."""
        lines = []
        for debt in debts:
            lines.append(
                f"- {debt.name}: ${debt.current_amount:,.0f}, "
                f"tasa {debt.interest_rate}% anual, "
                f"pago mínimo ${debt.minimum_payment:,.0f}, "
                f"interés mensual ${debt.monthly_interest:,.0f}"
            )
        return "\n".join(lines)

    def _calculate_payment_plan(
        self,
        debts: list[Debt],
        available: float,
        strategy: PaymentStrategy,
    ) -> list[PaymentPlan]:
        """Calcula el plan de pagos mensuales."""
        plan = []
        total_minimums = sum(d.minimum_payment for d in debts)
        extra_available = available - total_minimums

        # Ordenar según estrategia
        if strategy == PaymentStrategy.AVALANCHE:
            # Mayor tasa primero
            sorted_debts = sorted(
                debts, key=lambda x: x.interest_rate, reverse=True
            )
        elif strategy == PaymentStrategy.SNOWBALL:
            # Menor monto primero
            sorted_debts = sorted(debts, key=lambda x: x.current_amount)
        else:
            # Hybrid: prioridad manual o combinación
            sorted_debts = sorted(debts, key=lambda x: x.priority)

        # Excluir carro del extra (es fijo)
        priority_debts = [d for d in sorted_debts if d.name != "Carro"]

        for debt in debts:
            is_priority = (
                priority_debts
                and debt.name == priority_debts[0].name
                and debt.name != "Carro"
            )

            if is_priority and extra_available > 0:
                extra = min(extra_available, debt.current_amount)
                plan.append(PaymentPlan(
                    debt_name=debt.name,
                    monthly_payment=debt.minimum_payment + extra,
                    is_minimum=False,
                    extra_payment=extra,
                ))
            else:
                plan.append(PaymentPlan(
                    debt_name=debt.name,
                    monthly_payment=debt.minimum_payment,
                    is_minimum=True,
                    extra_payment=0,
                ))

        return plan

    def _calculate_months_minimum_only(self, debts: list[Debt]) -> int:
        """Calcula meses pagando solo mínimos (puede ser infinito)."""
        # Simplificación: si el interés mensual > pago mínimo, nunca termina
        for debt in debts:
            if debt.monthly_interest >= debt.minimum_payment:
                return 999  # Nunca termina

        # Estimación simple (sin compounding exacto)
        total_debt = sum(d.current_amount for d in debts)
        total_payment = sum(d.minimum_payment for d in debts)
        avg_interest_rate = sum(
            d.interest_rate * d.current_amount for d in debts
        ) / total_debt if total_debt > 0 else 0

        monthly_interest = total_debt * (avg_interest_rate / 100) / 12
        net_payment = total_payment - monthly_interest

        if net_payment <= 0:
            return 999

        return int(total_debt / net_payment) + 1

    def _calculate_months_with_plan(
        self,
        debts: list[Debt],
        plan: list[PaymentPlan],
    ) -> tuple[int, float]:
        """Calcula meses con el plan y el total de intereses."""
        # Simulación simplificada
        remaining = {d.name: d.current_amount for d in debts}
        debt_info = {d.name: d for d in debts}
        total_interest = 0
        months = 0
        max_months = 240  # 20 años máximo

        payment_map = {p.debt_name: p.monthly_payment for p in plan}

        while any(r > 0 for r in remaining.values()) and months < max_months:
            months += 1

            for name, balance in list(remaining.items()):
                if balance <= 0:
                    continue

                debt = debt_info[name]
                interest = balance * (debt.interest_rate / 100) / 12
                total_interest += interest

                payment = payment_map.get(name, debt.minimum_payment)
                new_balance = balance + interest - payment

                remaining[name] = max(0, new_balance)

        return months, total_interest

    def _calculate_total_interest_minimum(
        self, debts: list[Debt], months: int
    ) -> float:
        """Calcula intereses totales pagando solo mínimos."""
        if months >= 999:
            # Estimar 10 años de intereses
            return sum(d.monthly_interest * 120 for d in debts)

        return sum(d.monthly_interest * months for d in debts)

    def _calculate_milestones(
        self,
        debts: list[Debt],
        plan: list[PaymentPlan],
    ) -> list[dict]:
        """Calcula hitos importantes (primera deuda liquidada, etc.)."""
        milestones = []

        # Simular para encontrar cuándo se liquida cada deuda
        remaining = {d.name: d.current_amount for d in debts}
        debt_info = {d.name: d for d in debts}
        payment_map = {p.debt_name: p.monthly_payment for p in plan}
        months = 0

        # Ordenar por cuál se paga primero
        while any(r > 0 for r in remaining.values()) and months < 240:
            months += 1

            for name, balance in list(remaining.items()):
                if balance <= 0:
                    continue

                debt = debt_info[name]
                interest = balance * (debt.interest_rate / 100) / 12
                payment = payment_map.get(name, debt.minimum_payment)
                new_balance = balance + interest - payment

                if new_balance <= 0 and remaining[name] > 0:
                    milestones.append({
                        "month": months,
                        "event": f"🎉 {name} liquidada",
                        "saved": debt.current_amount - (debt.minimum_payment * months),
                    })
                    remaining[name] = 0

        return milestones[:5]  # Máximo 5 milestones

    def _create_fallback_result(
        self, debts: list[Debt], available: float
    ) -> DebtStrategyResult:
        """Crea resultado de fallback."""
        plan = [
            PaymentPlan(d.name, d.minimum_payment, True)
            for d in debts
        ]

        return DebtStrategyResult(
            strategy=PaymentStrategy.AVALANCHE,
            explanation="Paga primero la deuda con mayor tasa de interés para minimizar costos.",
            payment_order=[d.name for d in sorted(
                debts, key=lambda x: x.interest_rate, reverse=True
            )],
            monthly_plan=plan,
            months_to_freedom=36,
            total_interest_if_minimum=0,
            total_interest_with_plan=0,
            interest_saved=0,
            milestones=[],
        )

    def format_telegram_message(self, result: DebtStrategyResult) -> str:
        """Formatea el resultado como mensaje de Telegram."""
        strategy_emoji = {
            PaymentStrategy.AVALANCHE: "🏔️",
            PaymentStrategy.SNOWBALL: "⛄",
            PaymentStrategy.HYBRID: "🔀",
        }

        message = f"{strategy_emoji.get(result.strategy, '📊')} <b>Estrategia de Deudas</b>\n\n"

        message += f"<b>Estrategia:</b> {result.strategy.value.title()}\n"
        message += f"<i>{result.explanation[:150]}</i>\n\n"

        message += "<b>🎯 Orden de Ataque:</b>\n"
        for i, debt in enumerate(result.payment_order, 1):
            message += f"  {i}. {debt}\n"

        message += "\n<b>💰 Plan Mensual:</b>\n"
        for plan in result.monthly_plan:
            extra = f" (+${plan.extra_payment:,.0f} extra)" if plan.extra_payment > 0 else ""
            message += f"  • {plan.debt_name}: ${plan.monthly_payment:,.0f}{extra}\n"

        message += f"\n<b>📅 Tiempo estimado:</b> {result.months_to_freedom} meses\n"

        if result.interest_saved > 0:
            message += f"<b>💵 Ahorras:</b> ${result.interest_saved:,.0f} en intereses\n"

        if result.milestones:
            message += "\n<b>🏆 Hitos:</b>\n"
            for milestone in result.milestones[:3]:
                message += f"  • Mes {milestone['month']}: {milestone['event']}\n"

        return message

    async def get_quick_recommendation(self, extra_money: float) -> str:
        """
        Genera recomendación rápida de qué hacer con dinero extra.

        Args:
            extra_money: Cantidad extra disponible

        Returns:
            Recomendación en texto
        """
        # Encontrar deuda prioritaria (mayor tasa, excluyendo carro)
        priority_debts = [d for d in self.carlos_debts if d.name != "Carro"]
        priority_debts.sort(key=lambda x: x.interest_rate, reverse=True)

        if not priority_debts:
            return "No hay deudas prioritarias. ¡Considera ahorrar!"

        top_debt = priority_debts[0]
        monthly_interest_saved = extra_money * (top_debt.interest_rate / 100) / 12

        return (
            f"💡 <b>Recomendación:</b>\n"
            f"Abona ${extra_money:,.0f} a <b>{top_debt.name}</b>\n"
            f"(tasa {top_debt.interest_rate}%)\n\n"
            f"Esto te ahorra ~${monthly_interest_saved:,.0f}/mes en intereses."
        )
