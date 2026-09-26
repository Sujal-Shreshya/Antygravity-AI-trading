"""
Risk Management Engine Orchestrator.
Chains all pre-trade risk rules into an atomic evaluation pipeline.
Guarantees that no order can be placed without explicit risk approval.
"""

import logging

from backend.core.models import OrderRequest, RiskAction
from backend.risk.base import BaseRiskRule, RiskContext, RiskDecision
from backend.risk.rules import (
    DailyLossCircuitBreakerRule,
    KillSwitchRiskRule,
    MaxDrawdownCircuitBreakerRule,
    MaxOpenPositionsRule,
    PositionSizingRiskRule,
    SinglePositionExposureRule,
)

logger = logging.getLogger("trading.risk.engine")


class RiskEngine:
    """Pre-Trade Risk Management Coordinator."""

    def __init__(self) -> None:
        self.rules: list[BaseRiskRule] = [
            KillSwitchRiskRule(),
            DailyLossCircuitBreakerRule(),
            MaxDrawdownCircuitBreakerRule(),
            MaxOpenPositionsRule(),
            SinglePositionExposureRule(),
            PositionSizingRiskRule(),
        ]

    def evaluate_order(self, order: OrderRequest, context: RiskContext) -> RiskDecision:
        """
        Sequentially validates an order against all configured pre-trade risk constraints.
        Returns RiskDecision. If any rule rejects, the order is immediately rejected.
        """
        adjusted_qty = order.quantity

        for rule in self.rules:
            decision = rule.evaluate(order, context)

            if decision.action == RiskAction.REJECT:
                logger.warning(
                    f"[RISK REJECTION] Order {order.client_order_id} ({order.symbol} {order.side}) "
                    f"failed rule '{decision.rule_name}': {decision.reason}"
                )
                return decision

            if decision.action == RiskAction.MODIFY and decision.adjusted_quantity:
                logger.info(
                    f"[RISK MODIFICATION] Order {order.client_order_id} ({order.symbol}) "
                    f"quantity resized from {order.quantity} to {decision.adjusted_quantity} by '{decision.rule_name}'"
                )
                adjusted_qty = decision.adjusted_quantity

        if adjusted_qty != order.quantity:
            return RiskDecision(
                action=RiskAction.MODIFY,
                rule_name="RISK_ENGINE_RESIZED",
                is_approved=True,
                reason=f"Order approved with adjusted position size {adjusted_qty}.",
                adjusted_quantity=adjusted_qty,
            )

        return RiskDecision(
            action=RiskAction.APPROVE,
            rule_name="ALL_RISK_CHECKS_PASSED",
            is_approved=True,
            reason="All pre-trade risk and capital boundary checks passed successfully.",
        )


# Global singleton instance
risk_engine = RiskEngine()
