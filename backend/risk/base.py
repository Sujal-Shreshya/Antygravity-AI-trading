"""
Risk Rule Base Architecture.
Defines risk context, pre-trade risk evaluation protocol, and decision structures.
Every order must pass through risk rule evaluations before reaching execution.
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from backend.core.models import AccountBalance, OrderRequest, Position, RiskAction


class RiskContext(BaseModel):
    """Runtime account, portfolio, and session metrics required for risk evaluation."""

    account_balance: AccountBalance
    open_positions: list[Position] = Field(default_factory=list)
    daily_realized_loss: float = 0.0
    daily_unrealized_loss: float = 0.0
    peak_portfolio_equity: float = 0.0
    current_portfolio_equity: float = 0.0
    pending_orders_count: int = 0
    extra: dict[str, Any] = Field(default_factory=dict)


class RiskDecision(BaseModel):
    """Result of a pre-trade risk rule evaluation."""

    action: RiskAction
    rule_name: str
    is_approved: bool
    reason: str
    adjusted_quantity: float | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class BaseRiskRule(ABC):
    """Abstract interface for pre-trade risk gate rules."""

    def __init__(self, rule_name: str) -> None:
        self.rule_name = rule_name

    @abstractmethod
    def evaluate(self, order: OrderRequest, context: RiskContext) -> RiskDecision:
        """
        Evaluate an order against risk constraints.
        Returns RiskDecision with APPROVE or REJECT action.
        """
        pass
