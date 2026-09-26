"""
Phase 14 Comprehensive Live Trading Safety & Fail-Closed Gate Tests.
Exhaustively verifies all 7 pre-trade execution gates:
1. Gate 1: Master Configuration (LIVE_TRADING == False strictly blocks live execution)
2. Gate 2: Global Emergency Kill Switch (Engaged state rejects live orders)
3. Gate 3: Broker Credentials Validation (Missing/placeholder keys block live orders)
4. Gate 4: Market Calendar & Trading Session (Closed markets reject live orders)
5. Gate 5: Pre-Trade Risk Engine Clearance (Excessive risk rejects live orders)
6. Gate 6: Idempotency & In-Flight Deduplication Guard (Duplicate orders rejected)
7. Gate 7: Persistent Pre-Execution Audit Logging (Audit logs recorded before dispatch)
8. Emergency Kill Execution (Immediate cancellation of active working orders)
9. Live Readiness Diagnostics Inspection
"""

import time
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.brokers.base import BaseBroker
from backend.core.config import get_settings
from backend.core.exceptions import (
    BrokerConnectionError,
    DuplicateOrderError,
    KillSwitchActiveError,
    LiveTradingBlockedError,
    MarketClosedError,
    RiskLimitExceededError,
)
from backend.core.kill_switch import kill_switch
from backend.core.models import (
    OrderRequest,
    OrderResponse,
    OrderSide,
    OrderStatus,
    OrderType,
)
from backend.database.models import AuditLogModel, OrderModel
from backend.execution.coordinator import live_execution_coordinator
from backend.main import app


@pytest.fixture(autouse=True)
def reset_safety_state():
    """Guarantees clean safety state before and after every test."""
    kill_switch.deactivate()
    live_execution_coordinator._in_flight_tokens.clear()
    yield
    kill_switch.deactivate()
    live_execution_coordinator._in_flight_tokens.clear()


@pytest.mark.asyncio
async def test_gate1_default_live_trading_false_blocks_orders(test_db: AsyncSession):
    """Verify that by default (LIVE_TRADING=false), any live order is unconditionally rejected."""
    settings = get_settings()
    assert settings.LIVE_TRADING is False, "Default LIVE_TRADING must always be False"

    order = OrderRequest(
        client_order_id="test-live-gate1",
        symbol="RELIANCE",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=5.0,
        live_execution=True,
    )

    with pytest.raises(LiveTradingBlockedError) as exc_info:
        await live_execution_coordinator.execute_live_order(order=order, db=test_db)
    assert "LIVE_TRADING is false" in str(exc_info.value.message)


@pytest.mark.asyncio
async def test_gate1_api_returns_403_for_live_orders():
    """Verify POST /api/v1/orders returns HTTP 403 Forbidden when live_execution=True."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register and login
        await client.post(
            "/api/v1/auth/register",
            json={"email": "gate1_tester@trading.com", "password": "SecurePassword123!"},
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "gate1_tester@trading.com", "password": "SecurePassword123!"},
        )
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post(
            "/api/v1/orders",
            json={
                "client_order_id": "api-live-gate1-reject",
                "symbol": "TCS",
                "side": "BUY",
                "order_type": "MARKET",
                "quantity": 10.0,
                "live_execution": True,
            },
            headers=headers,
        )
        assert resp.status_code == 403
        assert "LIVE_TRADING" in resp.json()["detail"] or "live" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_gate2_emergency_kill_switch_blocks_live_orders(test_db: AsyncSession):
    """Verify that engaging kill switch halts live order execution even if LIVE_TRADING=True."""
    kill_switch.activate("Test emergency halt drill")
    order = OrderRequest(
        client_order_id="test-live-gate2",
        symbol="INFY",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=5.0,
        live_execution=True,
    )

    with patch("backend.execution.coordinator.get_settings") as mock_settings:
        mock_settings.return_value.LIVE_TRADING = True
        with pytest.raises(KillSwitchActiveError) as exc_info:
            await live_execution_coordinator.execute_live_order(order=order, db=test_db)
        assert "Emergency kill switch is ACTIVE" in exc_info.value.message


@pytest.mark.asyncio
async def test_gate3_missing_or_placeholder_broker_credentials_block_orders(test_db: AsyncSession):
    """Verify that missing or placeholder API credentials trigger BrokerConnectionError."""
    order = OrderRequest(
        client_order_id="test-live-gate3",
        symbol="RELIANCE",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=5.0,
        live_execution=True,
    )

    with patch("backend.execution.coordinator.get_settings") as mock_settings:
        mock_settings.return_value.LIVE_TRADING = True
        mock_settings.return_value.KITE_API_KEY = "your_kite_api_key_here"
        mock_settings.return_value.KITE_API_SECRET = "your_kite_secret_here"

        with pytest.raises(BrokerConnectionError) as exc_info:
            await live_execution_coordinator.execute_live_order(order=order, db=test_db)
        assert "Invalid or unconfigured credentials" in exc_info.value.message


@pytest.mark.asyncio
async def test_gate4_market_closed_hours_block_live_orders(test_db: AsyncSession):
    """Verify that market closed status halts live execution fail-closed."""
    order = OrderRequest(
        client_order_id="test-live-gate4",
        symbol="RELIANCE",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=5.0,
        live_execution=True,
    )

    with patch("backend.execution.coordinator.get_settings") as mock_settings:
        mock_settings.return_value.LIVE_TRADING = True
        mock_settings.return_value.KITE_API_KEY = "REAL_PRODUCTION_KEY_123"
        mock_settings.return_value.KITE_API_SECRET = "REAL_PRODUCTION_SECRET_456"

        with patch("backend.execution.coordinator.MarketCalendar.is_market_open", return_value=False):
            with pytest.raises(MarketClosedError) as exc_info:
                await live_execution_coordinator.execute_live_order(order=order, db=test_db)
            assert "is currently closed" in exc_info.value.message


@pytest.mark.asyncio
async def test_gate5_risk_engine_violation_blocks_live_orders(test_db: AsyncSession):
    """Verify that pre-trade risk engine violation raises RiskLimitExceededError and records event."""
    order = OrderRequest(
        client_order_id="test-live-gate5-risk",
        symbol="RELIANCE",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=100000.0,
        price=3000.0,
        live_execution=True,
    )

    with patch("backend.execution.coordinator.get_settings") as mock_settings:
        mock_settings.return_value.LIVE_TRADING = True
        mock_settings.return_value.KITE_API_KEY = "REAL_PRODUCTION_KEY_123"
        mock_settings.return_value.KITE_API_SECRET = "REAL_PRODUCTION_SECRET_456"

        with patch("backend.execution.coordinator.MarketCalendar.is_market_open", return_value=True):
            with pytest.raises(RiskLimitExceededError):
                await live_execution_coordinator.execute_live_order(order=order, db=test_db)


@pytest.mark.asyncio
async def test_gate6_duplicate_order_idempotency_guard(test_db: AsyncSession):
    """Verify that rapid duplicate order submission in flight is blocked by idempotency guard."""
    order = OrderRequest(
        client_order_id="test-live-gate6-dedup",
        symbol="RELIANCE",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=1.0,
        live_execution=True,
    )

    live_execution_coordinator._in_flight_tokens["test-live-gate6-dedup"] = time.monotonic()

    with patch("backend.execution.coordinator.get_settings") as mock_settings:
        mock_settings.return_value.LIVE_TRADING = True
        mock_settings.return_value.KITE_API_KEY = "REAL_PRODUCTION_KEY_123"
        mock_settings.return_value.KITE_API_SECRET = "REAL_PRODUCTION_SECRET_456"

        with patch("backend.execution.coordinator.MarketCalendar.is_market_open", return_value=True):
            with pytest.raises(DuplicateOrderError) as exc_info:
                await live_execution_coordinator.execute_live_order(order=order, db=test_db)
            assert "Duplicate order in-flight" in exc_info.value.message


@pytest.mark.asyncio
async def test_gate7_successful_execution_and_audit_logging(test_db: AsyncSession):
    """Verify that when all 7 gates pass, order executes and audit logs are recorded."""
    order = OrderRequest(
        client_order_id="test-live-gate7-success",
        symbol="RELIANCE",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=2.0,
        price=2500.0,
        live_execution=True,
    )

    mock_broker = AsyncMock(spec=BaseBroker)
    mock_broker.broker_name = "Kite"
    mock_broker.place_order.return_value = OrderResponse(
        order_id="broker-live-ord-777",
        client_order_id="test-live-gate7-success",
        symbol="RELIANCE",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=2.0,
        price=2500.0,
        filled_quantity=2.0,
        average_price=2500.0,
        status=OrderStatus.FILLED,
        is_paper=False,
        broker_message="Filled by Exchange",
    )

    with patch("backend.execution.coordinator.get_settings") as mock_settings:
        mock_settings.return_value.LIVE_TRADING = True
        mock_settings.return_value.KITE_API_KEY = "REAL_KEY_123"
        mock_settings.return_value.KITE_API_SECRET = "REAL_SECRET_456"

        with patch("backend.execution.coordinator.broker_factory.get_broker", return_value=mock_broker):
            with patch("backend.execution.coordinator.MarketCalendar.is_market_open", return_value=True):
                response = await live_execution_coordinator.execute_live_order(
                    order=order, db=test_db, operator_id="lead_quant@trading.com"
                )

                assert response.status == OrderStatus.FILLED
                assert response.is_paper is False
                assert response.filled_quantity == 2.0

                # Verify Audit Log persisted in DB
                audit_res = await test_db.execute(
                    select(AuditLogModel).where(
                        AuditLogModel.event_type == "LIVE_ORDER_PRE_DISPATCH"
                    )
                )
                audit_entry = audit_res.scalar_one_or_none()
                assert audit_entry is not None
                assert audit_entry.operator_id == "lead_quant@trading.com"
                assert audit_entry.details["client_order_id"] == "test-live-gate7-success"


@pytest.mark.asyncio
async def test_emergency_kill_switch_cancels_open_orders(test_db: AsyncSession):
    """Verify that execute_emergency_kill updates kill switch, cancels DB orders, and records audit."""
    order = OrderModel(
        client_order_id="working-order-kill-test",
        symbol="TCS",
        side="BUY",
        order_type="MARKET",
        quantity=10.0,
        status=OrderStatus.SUBMITTED.value,
        is_paper=True,
    )
    test_db.add(order)
    await test_db.commit()
    await test_db.refresh(order)

    result = await live_execution_coordinator.execute_emergency_kill(
        reason="Flash crash detected",
        operator_id="admin@trading.com",
        db=test_db,
    )

    assert result["status"] == "engaged"
    assert result["cancelled_orders"] >= 1
    assert kill_switch.is_active is True

    # Refresh order from DB
    await test_db.refresh(order)
    assert order.status == OrderStatus.CANCELLED.value
    assert "Flash crash detected" in order.broker_message


@pytest.mark.asyncio
async def test_live_readiness_diagnostics_endpoint():
    """Verify live readiness diagnostics API returns complete safety system assessment."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register and login
        await client.post(
            "/api/v1/auth/register",
            json={"email": "diag_tester@trading.com", "password": "SecurePassword123!"},
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "diag_tester@trading.com", "password": "SecurePassword123!"},
        )
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.get("/api/v1/orders/readiness", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["live_trading_master_switch"] is False
        assert data["kill_switch_active"] is False
        assert "broker_credentials" in data
        assert "market_hours" in data
        assert "risk_engine" in data
        assert data["overall_live_executable"] is False
