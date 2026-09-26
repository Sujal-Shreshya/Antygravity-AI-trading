"""
Unit and integration tests for Pre-Trade Risk Engine and Circuit Breakers (Phase 6).
Tests:
- Kill switch gate rule
- Daily loss circuit breaker (3% limit)
- Max drawdown circuit breaker (10% limit)
- Max open positions limit (10 positions ceiling)
- Single asset exposure cap (15% limit)
- 1% per-trade risk sizing and automated resizing
- End-to-end RiskEngine orchestration
- API integration with /risk/evaluate and order submission rejection/audit logging
"""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.kill_switch import kill_switch
from backend.core.models import (
    AccountBalance,
    OrderRequest,
    OrderSide,
    OrderType,
    Position,
    RiskAction,
    TradeDirection,
)
from backend.main import app
from backend.risk.base import RiskContext
from backend.risk.engine import RiskEngine
from backend.risk.rules import (
    DailyLossCircuitBreakerRule,
    KillSwitchRiskRule,
    MaxDrawdownCircuitBreakerRule,
    MaxOpenPositionsRule,
    PositionSizingRiskRule,
    SinglePositionExposureRule,
)


@pytest.fixture(autouse=True)
def reset_kill_switch():
    """Ensure kill switch is disengaged for clean tests."""
    kill_switch.deactivate(operator_id="test_suite")
    yield
    kill_switch.deactivate(operator_id="test_suite")


def get_sample_context(
    equity: float = 100_000.0,
    daily_realized_loss: float = 0.0,
    daily_unrealized_loss: float = 0.0,
    peak_equity: float = 100_000.0,
    current_equity: float = 100_000.0,
    open_positions: list[Position] | None = None,
) -> RiskContext:
    return RiskContext(
        account_balance=AccountBalance(
            cash=equity,
            equity=equity,
            available_margin=equity,
        ),
        open_positions=open_positions or [],
        daily_realized_loss=daily_realized_loss,
        daily_unrealized_loss=daily_unrealized_loss,
        peak_portfolio_equity=peak_equity,
        current_portfolio_equity=current_equity,
    )


def test_kill_switch_rule():
    rule = KillSwitchRiskRule()
    order = OrderRequest(symbol="TCS", side=OrderSide.BUY, order_type=OrderType.MARKET, quantity=10)
    context = get_sample_context()

    # Disengaged
    decision = rule.evaluate(order, context)
    assert decision.is_approved is True
    assert decision.action == RiskAction.APPROVE

    # Engaged
    kill_switch.activate(reason="Black Swan Event", operator_id="risk_manager")
    decision2 = rule.evaluate(order, context)
    assert decision2.is_approved is False
    assert decision2.action == RiskAction.REJECT
    assert "Emergency kill switch is engaged" in decision2.reason


def test_daily_loss_circuit_breaker():
    rule = DailyLossCircuitBreakerRule()
    order = OrderRequest(symbol="INFY", side=OrderSide.BUY, order_type=OrderType.MARKET, quantity=5)

    # 100,000 equity, max 3% loss = 3,000 INR
    # Safe loss: 2,500 INR
    safe_context = get_sample_context(equity=100_000.0, daily_realized_loss=2_500.0)
    assert rule.evaluate(order, safe_context).is_approved is True

    # Breached loss: 3,100 INR
    tripped_context = get_sample_context(equity=100_000.0, daily_realized_loss=3_100.0)
    decision = rule.evaluate(order, tripped_context)
    assert decision.is_approved is False
    assert decision.action == RiskAction.REJECT
    assert "Daily loss limit reached" in decision.reason


def test_max_drawdown_circuit_breaker():
    rule = MaxDrawdownCircuitBreakerRule()
    order = OrderRequest(symbol="RELIANCE", side=OrderSide.BUY, order_type=OrderType.MARKET, quantity=5)

    # Peak: 100,000, Current: 92,000 (8% drawdown -> OK)
    ok_context = get_sample_context(peak_equity=100_000.0, current_equity=92_000.0)
    assert rule.evaluate(order, ok_context).is_approved is True

    # Peak: 100,000, Current: 88,000 (12% drawdown -> Exceeds 10% threshold)
    tripped_context = get_sample_context(peak_equity=100_000.0, current_equity=88_000.0)
    decision = rule.evaluate(order, tripped_context)
    assert decision.is_approved is False
    assert decision.action == RiskAction.REJECT
    assert "Portfolio drawdown limit tripped" in decision.reason


def test_max_open_positions_rule():
    rule = MaxOpenPositionsRule()
    order_new = OrderRequest(symbol="NEW_STOCK", side=OrderSide.BUY, order_type=OrderType.MARKET, quantity=1)

    # 10 existing open positions
    existing = [
        Position(
            symbol=f"STOCK_{i}",
            direction=TradeDirection.LONG,
            quantity=10,
            entry_price=100.0,
            current_price=105.0,
        )
        for i in range(10)
    ]
    context_capped = get_sample_context(open_positions=existing)

    # New symbol rejected at cap
    dec_new = rule.evaluate(order_new, context_capped)
    assert dec_new.is_approved is False
    assert dec_new.action == RiskAction.REJECT
    assert "Maximum open positions cap reached" in dec_new.reason

    # Existing symbol can still add/reduce
    order_existing = OrderRequest(symbol="STOCK_0", side=OrderSide.BUY, order_type=OrderType.MARKET, quantity=2)
    dec_existing = rule.evaluate(order_existing, context_capped)
    assert dec_existing.is_approved is True


def test_single_position_exposure_rule():
    rule = SinglePositionExposureRule()
    # 100,000 equity, max 15% = 15,000 INR
    context = get_sample_context(equity=100_000.0)

    # Order notional = 10 * 1,000 = 10,000 <= 15,000 -> Approved
    safe_order = OrderRequest(
        symbol="TCS",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=10,
        price=1000.0,
    )
    assert rule.evaluate(safe_order, context).is_approved is True

    # Order notional = 20 * 1,000 = 20,000 > 15,000 -> Rejected
    excessive_order = OrderRequest(
        symbol="TCS",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=20,
        price=1000.0,
    )
    decision = rule.evaluate(excessive_order, context)
    assert decision.is_approved is False
    assert decision.action == RiskAction.REJECT
    assert "exceeds single position cap" in decision.reason


def test_position_sizing_rule_and_auto_resize():
    rule = PositionSizingRiskRule()
    # Equity = 100,000. Max risk per trade (1%) = 1,000 INR
    context = get_sample_context(equity=100_000.0)

    # Entry = 100, Stop Loss = 90. Risk per unit = 10 INR
    # Quantity = 50 -> Potential loss = 50 * 10 = 500 INR <= 1,000 INR -> Approved
    safe_order = OrderRequest(
        symbol="HDFC",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=50,
        price=100.0,
        stop_price=90.0,
    )
    assert rule.evaluate(safe_order, context).is_approved is True

    # Quantity = 200 -> Potential loss = 200 * 10 = 2,000 INR > 1,000 INR
    # Rule should auto-resize to 1000 / 10 = 100 units!
    large_order = OrderRequest(
        symbol="HDFC",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=200,
        price=100.0,
        stop_price=90.0,
    )
    decision = rule.evaluate(large_order, context)
    assert decision.is_approved is True
    assert decision.action == RiskAction.MODIFY
    assert decision.adjusted_quantity == 100.0
    assert "Position size resized" in decision.reason


def test_risk_engine_orchestration():
    engine = RiskEngine()
    context = get_sample_context(equity=100_000.0)

    # Valid order that passes all rules
    order = OrderRequest(
        symbol="TCS",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=10,
        price=500.0,
        stop_price=480.0,
    )
    decision = engine.evaluate_order(order, context)
    assert decision.is_approved is True
    assert decision.action == RiskAction.APPROVE


@pytest.mark.asyncio
async def test_risk_api_evaluate_and_order_rejection_audit():
    """Verify /risk/evaluate API and pre-trade order rejection with audit trail."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register and login operator
        await client.post(
            "/api/v1/auth/register",
            json={"email": "risk_tester@trading.com", "password": "SecurePassword123!"},
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "risk_tester@trading.com", "password": "SecurePassword123!"},
        )
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Test /risk/evaluate dry-run endpoint
        eval_resp = await client.post(
            "/api/v1/risk/evaluate",
            json={
                "client_order_id": "dryrun-001",
                "symbol": "INFY",
                "side": "BUY",
                "order_type": "LIMIT",
                "quantity": 10,
                "price": 100.0,
            },
            headers=headers,
        )
        assert eval_resp.status_code == 200
        assert eval_resp.json()["is_approved"] is True

        # 2. Submit order exceeding single position exposure (15% equity = 15,000 INR)
        # 100 qty @ 250 price = 25,000 INR -> Must reject with 422
        excessive_order = {
            "client_order_id": "risk-breach-001",
            "symbol": "EXPENSIVE_STOCK",
            "side": "BUY",
            "order_type": "LIMIT",
            "quantity": 100,
            "price": 250.0,
            "live_execution": False,
        }
        order_resp = await client.post("/api/v1/orders", json=excessive_order, headers=headers)
        assert order_resp.status_code == 422
        assert "Pre-trade risk rejected" in order_resp.json()["detail"]

        # 3. Verify risk event was persisted in audit log
        events_resp = await client.get("/api/v1/risk/events", headers=headers)
        assert events_resp.status_code == 200
        events = events_resp.json()
        assert len(events) >= 1
        rejected_event = next((e for e in events if e["action"] == "REJECT"), None)
        assert rejected_event is not None
        assert rejected_event["rule_name"] == "SINGLE_POSITION_EXPOSURE_EXCEEDED"
