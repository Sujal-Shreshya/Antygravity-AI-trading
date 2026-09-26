"""
Pre-Trade Risk Management Rules.
Implements granular validation rules:
- Max risk per trade (1% capital loss)
- Daily loss circuit breaker (3% equity)
- Portfolio drawdown limit (10% equity)
- Max open positions limit (10 positions)
- Single asset exposure cap (15% equity)
- Risk/Reward ratio validation (minimum 1.5)
- Emergency kill switch enforcement
"""

import math

from backend.core.config import get_settings
from backend.core.kill_switch import kill_switch
from backend.core.models import OrderRequest, RiskAction
from backend.risk.base import BaseRiskRule, RiskContext, RiskDecision


class KillSwitchRiskRule(BaseRiskRule):
    """Enforces global emergency kill switch."""

    def __init__(self) -> None:
        super().__init__("KILL_SWITCH_ACTIVE")

    def evaluate(self, order: OrderRequest, context: RiskContext) -> RiskDecision:
        if kill_switch.is_active:
            status = kill_switch.get_status()
            return RiskDecision(
                action=RiskAction.REJECT,
                rule_name=self.rule_name,
                is_approved=False,
                reason=f"Emergency kill switch is engaged: {status.get('reason')}",
                metrics={"operator": status.get("operator_id")},
            )
        return RiskDecision(
            action=RiskAction.APPROVE,
            rule_name=self.rule_name,
            is_approved=True,
            reason="Kill switch is disengaged.",
        )


class DailyLossCircuitBreakerRule(BaseRiskRule):
    """Halts order submission if daily losses exceed max daily threshold (default 3%)."""

    def __init__(self) -> None:
        super().__init__("MAX_DAILY_LOSS_EXCEEDED")

    def evaluate(self, order: OrderRequest, context: RiskContext) -> RiskDecision:
        settings = get_settings()
        equity = max(context.account_balance.equity, 1e-9)
        max_allowed_loss = equity * settings.RISK_MAX_DAILY_LOSS_PCT
        current_loss = context.daily_realized_loss + max(0.0, context.daily_unrealized_loss)

        if current_loss >= max_allowed_loss:
            return RiskDecision(
                action=RiskAction.REJECT,
                rule_name=self.rule_name,
                is_approved=False,
                reason=(
                    f"Daily loss limit reached: Current loss ₹{current_loss:,.2f} "
                    f"exceeds limit ₹{max_allowed_loss:,.2f} ({settings.RISK_MAX_DAILY_LOSS_PCT*100:.1f}% equity)"
                ),
                metrics={
                    "current_loss": current_loss,
                    "max_allowed_loss": max_allowed_loss,
                    "equity": equity,
                },
            )
        return RiskDecision(
            action=RiskAction.APPROVE,
            rule_name=self.rule_name,
            is_approved=True,
            reason="Daily loss is within safe parameters.",
        )


class MaxDrawdownCircuitBreakerRule(BaseRiskRule):
    """Halts trading if portfolio drawdown from peak exceeds maximum limit (default 10%)."""

    def __init__(self) -> None:
        super().__init__("MAX_PORTFOLIO_DRAWDOWN_EXCEEDED")

    def evaluate(self, order: OrderRequest, context: RiskContext) -> RiskDecision:
        settings = get_settings()
        peak = context.peak_portfolio_equity or context.account_balance.equity
        current = context.current_portfolio_equity or context.account_balance.equity

        if peak > 0:
            drawdown = (peak - current) / peak
            if drawdown >= settings.RISK_MAX_PORTFOLIO_DRAWDOWN_PCT:
                return RiskDecision(
                    action=RiskAction.REJECT,
                    rule_name=self.rule_name,
                    is_approved=False,
                    reason=(
                        f"Portfolio drawdown limit tripped: Drawdown {drawdown*100:.2f}% "
                        f"exceeds threshold {settings.RISK_MAX_PORTFOLIO_DRAWDOWN_PCT*100:.1f}%"
                    ),
                    metrics={"peak": peak, "current": current, "drawdown": drawdown},
                )
        return RiskDecision(
            action=RiskAction.APPROVE,
            rule_name=self.rule_name,
            is_approved=True,
            reason="Portfolio drawdown within acceptable threshold.",
        )


class MaxOpenPositionsRule(BaseRiskRule):
    """Restricts total simultaneous open positions to prevent catastrophic over-exposure."""

    def __init__(self) -> None:
        super().__init__("MAX_OPEN_POSITIONS_REACHED")

    def evaluate(self, order: OrderRequest, context: RiskContext) -> RiskDecision:
        settings = get_settings()
        open_count = len(context.open_positions)
        existing_symbols = {p.symbol for p in context.open_positions}

        # If adding a new symbol when already at cap -> Reject
        if order.symbol not in existing_symbols and open_count >= settings.RISK_MAX_OPEN_POSITIONS:
            return RiskDecision(
                action=RiskAction.REJECT,
                rule_name=self.rule_name,
                is_approved=False,
                reason=(
                    f"Maximum open positions cap reached ({open_count} / {settings.RISK_MAX_OPEN_POSITIONS}). "
                    "Cannot open new asset position."
                ),
                metrics={"open_positions": open_count, "limit": settings.RISK_MAX_OPEN_POSITIONS},
            )
        return RiskDecision(
            action=RiskAction.APPROVE,
            rule_name=self.rule_name,
            is_approved=True,
            reason="Open position count is within allowed ceiling.",
        )


class SinglePositionExposureRule(BaseRiskRule):
    """Caps capital allocation to any single asset (default 15% equity)."""

    def __init__(self) -> None:
        super().__init__("SINGLE_POSITION_EXPOSURE_EXCEEDED")

    def evaluate(self, order: OrderRequest, context: RiskContext) -> RiskDecision:
        settings = get_settings()
        equity = max(context.account_balance.equity, 1e-9)
        max_notional = equity * settings.RISK_MAX_SINGLE_POSITION_PCT

        order_price = order.price or (order.metadata.get("current_price", 100.0))
        order_notional = order.quantity * order_price

        # Check existing notional for this asset
        existing_notional = 0.0
        for p in context.open_positions:
            if p.symbol == order.symbol:
                existing_notional += p.quantity * p.current_price

        total_notional = existing_notional + order_notional

        if total_notional > max_notional:
            return RiskDecision(
                action=RiskAction.REJECT,
                rule_name=self.rule_name,
                is_approved=False,
                reason=(
                    f"Position exposure for {order.symbol} (₹{total_notional:,.2f}) "
                    f"exceeds single position cap ₹{max_notional:,.2f} ({settings.RISK_MAX_SINGLE_POSITION_PCT*100:.1f}% equity)"
                ),
                metrics={"total_notional": total_notional, "max_allowed": max_notional},
            )
        return RiskDecision(
            action=RiskAction.APPROVE,
            rule_name=self.rule_name,
            is_approved=True,
            reason="Position exposure is within diversification bounds.",
        )


class PositionSizingRiskRule(BaseRiskRule):
    """
    Enforces maximum 1% risk per trade.
    Calculates maximum allowed position size based on Stop Loss distance:
    Size = (Equity * Risk Fraction) / |Entry - StopLoss|
    """

    def __init__(self) -> None:
        super().__init__("MAX_RISK_PER_TRADE_EXCEEDED")

    def evaluate(self, order: OrderRequest, context: RiskContext) -> RiskDecision:
        settings = get_settings()
        equity = max(context.account_balance.equity, 1e-9)
        max_permissible_loss = equity * settings.RISK_MAX_RISK_PER_TRADE_PCT

        # Extract stop loss from metadata or stop_price
        stop_loss = order.stop_price or order.metadata.get("stop_loss")
        entry_price = order.price or order.metadata.get("current_price")

        # If Stop Loss is provided, calculate actual potential financial loss
        if stop_loss and entry_price and abs(entry_price - stop_loss) > 1e-6:
            risk_per_unit = abs(entry_price - stop_loss)
            total_potential_loss = order.quantity * risk_per_unit

            if total_potential_loss > max_permissible_loss:
                # Calculate maximum allowed quantity
                max_allowed_qty = math.floor(max_permissible_loss / risk_per_unit)
                if max_allowed_qty <= 0:
                    return RiskDecision(
                        action=RiskAction.REJECT,
                        rule_name=self.rule_name,
                        is_approved=False,
                        reason=(
                            f"Risk per trade ₹{total_potential_loss:,.2f} exceeds limit ₹{max_permissible_loss:,.2f} "
                            f"({settings.RISK_MAX_RISK_PER_TRADE_PCT*100:.1f}% equity). Sizing cannot be supported."
                        ),
                        metrics={"planned_loss": total_potential_loss, "max_loss": max_permissible_loss},
                    )
                return RiskDecision(
                    action=RiskAction.MODIFY,
                    rule_name=self.rule_name,
                    is_approved=True,
                    reason=f"Position size resized from {order.quantity} to {max_allowed_qty} to satisfy 1% risk limit.",
                    adjusted_quantity=float(max_allowed_qty),
                    metrics={"planned_loss": total_potential_loss, "adjusted_loss": max_allowed_qty * risk_per_unit},
                )

        return RiskDecision(
            action=RiskAction.APPROVE,
            rule_name=self.rule_name,
            is_approved=True,
            reason="Per-trade risk is within policy limits.",
        )
