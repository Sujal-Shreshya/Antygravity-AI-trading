"""
Unit tests for configuration, fail-closed safety baseline, and kill switch.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.brokers.base import BaseBroker
from backend.core.config import Settings
from backend.core.exceptions import KillSwitchActiveError, LiveTradingBlockedError
from backend.core.kill_switch import EmergencyKillSwitch, kill_switch
from backend.core.models import (
    AccountBalance,
    OHLCVCandle,
    OrderRequest,
    OrderResponse,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    TimeFrame,
    Trade,
)


class MockBroker(BaseBroker):
    """Test broker adapter implementation."""

    def __init__(self) -> None:
        super().__init__("mock_broker")
        self.placed_orders: list[OrderRequest] = []

    async def connect(self) -> bool:
        return True

    async def disconnect(self) -> None:
        pass

    async def is_connected(self) -> bool:
        return True

    async def get_accounts(self) -> list[dict]:
        return [{"id": "ACC1", "currency": "INR"}]

    async def get_balance(self) -> AccountBalance:
        return AccountBalance(
            currency="INR",
            cash=100000.0,
            equity=100000.0,
            available_margin=100000.0,
            is_paper=True,
            updated_at=datetime.now(UTC),
        )

    async def get_positions(self) -> list[Position]:
        return []

    async def get_orders(self, symbol: str | None = None) -> list[OrderResponse]:
        return []

    async def get_instruments(self, market: str | None = None) -> list[dict]:
        return []

    async def get_quotes(self, symbols: list[str]) -> dict:
        return {}

    async def get_historical_data(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start_time,
        end_time,
    ) -> list[OHLCVCandle]:
        return []

    async def _execute_place_order(self, order: OrderRequest) -> OrderResponse:
        self.placed_orders.append(order)
        return OrderResponse(
            order_id="ORD123",
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price,
            filled_quantity=order.quantity,
            average_price=order.price or 100.0,
            status=OrderStatus.FILLED,
            is_paper=not order.live_execution,
        )

    async def modify_order(
        self, order_id: str, new_quantity=None, new_price=None, new_stop_price=None
    ) -> OrderResponse:
        raise NotImplementedError

    async def cancel_order(self, order_id: str) -> OrderResponse:
        raise NotImplementedError

    async def get_order_status(self, order_id: str) -> OrderResponse:
        raise NotImplementedError

    async def get_margin(self, order: OrderRequest) -> dict:
        return {"required_margin": 1000.0}

    async def get_trade_history(self, symbol: str | None = None) -> list[Trade]:
        return []


def test_settings_default_live_trading_is_false():
    """Verify default LIVE_TRADING is False and cannot be accidentally enabled."""
    settings = Settings(_env_file=None)
    assert settings.LIVE_TRADING is False
    assert settings.is_live_trading_enabled is False


def test_settings_risk_boundaries_enforced():
    """Verify validation boundaries on risk limits."""
    # Excessive risk per trade should fail validation
    with pytest.raises(ValidationError):
        Settings(_env_file=None, RISK_MAX_RISK_PER_TRADE_PCT=0.20)  # > 5% max

    # Excessive daily loss limit should fail
    with pytest.raises(ValidationError):
        Settings(_env_file=None, RISK_MAX_DAILY_LOSS_PCT=0.50)  # > 10% max


def test_kill_switch_lifecycle():
    """Verify emergency kill switch activation and deactivation."""
    ks = EmergencyKillSwitch()
    assert not ks.is_active

    # Activate
    ks.activate(reason="Test volatility spike", operator_id="TEST_RUNNER")
    assert ks.is_active
    status = ks.get_status()
    assert status["is_active"] is True
    assert status["reason"] == "Test volatility spike"

    # Verify exception is raised
    with pytest.raises(KillSwitchActiveError):
        ks.verify_inactive()

    # Deactivate
    ks.deactivate(operator_id="ADMIN")
    assert not ks.is_active
    ks.verify_inactive()  # should not raise


@pytest.mark.asyncio
async def test_live_trading_blocked_by_default():
    """Verify that submitting a live order when LIVE_TRADING=false raises LiveTradingBlockedError."""
    # Ensure kill switch is deactivated
    kill_switch.deactivate()

    broker = MockBroker()
    order = OrderRequest(
        symbol="RELIANCE",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=10,
        live_execution=True,  # LIVE ORDER REQUEST
    )

    with pytest.raises(LiveTradingBlockedError):
        await broker.place_order(order)


@pytest.mark.asyncio
async def test_kill_switch_blocks_orders():
    """Verify that engaging the kill switch blocks all incoming orders."""
    kill_switch.activate("Operator emergency test")

    broker = MockBroker()
    order = OrderRequest(
        symbol="TCS",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=5,
        live_execution=False,
    )

    try:
        with pytest.raises(KillSwitchActiveError):
            await broker.place_order(order)
    finally:
        kill_switch.deactivate()


@pytest.mark.asyncio
async def test_paper_order_allowed_when_safe():
    """Verify paper order succeeds when system is healthy and kill switch is disengaged."""
    kill_switch.deactivate()

    broker = MockBroker()
    order = OrderRequest(
        symbol="INFY",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=20,
        live_execution=False,
    )

    response = await broker.place_order(order)
    assert response.status == OrderStatus.FILLED
    assert response.is_paper is True
    assert len(broker.placed_orders) == 1
