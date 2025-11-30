"""
Finance Entities - Transaction y Debt.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


# ==================== TRANSACTIONS ====================


class TransactionType(str, Enum):
    """Tipo de transacción."""
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"


class TransactionCategory(str, Enum):
    """Categoría de gasto."""
    FOOD = "food"
    TRANSPORT = "transport"
    ENTERTAINMENT = "entertainment"
    SHOPPING = "shopping"
    SERVICES = "services"
    HEALTH = "health"
    EDUCATION = "education"
    DEBT_PAYMENT = "debt_payment"
    SAVINGS = "savings"
    OTHER = "other"


@dataclass
class Transaction:
    """
    Entidad de Transacción.

    Representa un ingreso o gasto.
    """

    id: str
    date: date
    amount: Decimal
    type: TransactionType
    category: TransactionCategory = TransactionCategory.OTHER

    # Descripción
    description: str | None = None
    merchant: str | None = None

    # Método de pago
    payment_method: str | None = None  # Efectivo, Tarjeta X, etc.
    account: str | None = None

    # Relaciones
    debt_id: str | None = None  # Si es pago de deuda

    # Metadata
    created_at: datetime | None = None
    is_recurring: bool = False

    # Raw data
    _raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_expense(self) -> bool:
        """Verifica si es un gasto."""
        return self.type == TransactionType.EXPENSE

    @property
    def is_income(self) -> bool:
        """Verifica si es un ingreso."""
        return self.type == TransactionType.INCOME

    def to_dict(self) -> dict[str, Any]:
        """Convierte a diccionario."""
        return {
            "id": self.id,
            "date": self.date.isoformat(),
            "amount": float(self.amount),
            "type": self.type.value,
            "category": self.category.value,
            "description": self.description,
            "merchant": self.merchant,
            "is_expense": self.is_expense,
        }


# ==================== DEBTS ====================


class DebtStatus(str, Enum):
    """Estado de deuda."""
    ACTIVE = "active"
    PAID = "paid"
    DEFAULTED = "defaulted"


class DebtCreditor(str, Enum):
    """Tipo de acreedor."""
    BANK = "bank"
    CREDIT_CARD = "credit_card"
    FAMILY = "family"
    FRIEND = "friend"
    OTHER = "other"


@dataclass
class Debt:
    """
    Entidad de Deuda.

    Representa una deuda o crédito.
    """

    id: str
    name: str
    creditor: DebtCreditor
    status: DebtStatus = DebtStatus.ACTIVE

    # Montos
    original_amount: Decimal = Decimal("0")
    current_amount: Decimal = Decimal("0")
    minimum_payment: Decimal = Decimal("0")

    # Tasas
    interest_rate: float | None = None  # Porcentaje anual
    monthly_interest: float | None = None

    # Fechas
    start_date: date | None = None
    due_date: date | None = None  # Fecha límite de pago
    payment_day: int | None = None  # Día del mes para pagar

    # Pagos
    total_paid: Decimal = Decimal("0")
    last_payment_date: date | None = None
    payment_count: int = 0

    # Metadata
    notes: str | None = None
    created_at: datetime | None = None

    # Raw data
    _raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def progress(self) -> float:
        """Porcentaje pagado."""
        if self.original_amount == 0:
            return 0.0
        return float(self.total_paid / self.original_amount) * 100

    @property
    def remaining(self) -> Decimal:
        """Monto restante."""
        return self.current_amount

    @property
    def is_paid(self) -> bool:
        """Verifica si está pagada."""
        return self.status == DebtStatus.PAID or self.current_amount <= 0

    @property
    def is_overdue(self) -> bool:
        """Verifica si está vencida."""
        if not self.due_date:
            return False
        if self.is_paid:
            return False
        return self.due_date < date.today()

    def to_dict(self) -> dict[str, Any]:
        """Convierte a diccionario."""
        return {
            "id": self.id,
            "name": self.name,
            "creditor": self.creditor.value,
            "status": self.status.value,
            "original_amount": float(self.original_amount),
            "current_amount": float(self.current_amount),
            "minimum_payment": float(self.minimum_payment),
            "interest_rate": self.interest_rate,
            "progress": self.progress,
            "is_paid": self.is_paid,
            "is_overdue": self.is_overdue,
        }
