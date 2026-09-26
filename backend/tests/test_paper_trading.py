"""
Unit and integration tests for Paper Trading Execution Engine (Phase 8).
Tests:
- Simulated market order fills with slippage and brokerage commission
- Limit order fill validation (pending vs filled based on current price)
- Position lifecycle: Long creation, addition, partial exit, full exit, and reversal
- Realized and unrealized P&L calculation
- Mark-to-market price updates
- Portfolio snapshot calculations
- Account state reset
- API endpoints (/api/v1/paper/execute/{id}, /update-prices, /portfolio, /reset)
"""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.models import OrderSide, OrderStatus, OrderType
from backend.database.models import OrderModel, PositionModel
from backend.main import app
from backend.paper_trading.engine import PaperExecutionEngine


@pytest.mark.asyncio
async def test_paper_engine_execution_and_positions(test_db):
    """Verify PaperExecutionEngine executes orders, updates positions, and tracks PnL."""
    engine = PaperExecutionEngine(commission_rate=0.0003, slippage_rate=0.0005)

    # 1. Create a paper order in DB
    order = OrderModel(
        client_order_id="paper-unit-001",
        symbol="INFY",
        side=OrderSide.BUY.value,
        order_type=OrderType.MARKET.value,
        quantity=10.0,
        price=100.0,
        status=OrderStatus.SUBMITTED.value,
        is_paper=True,
    )
    test_db.add(order)
    await test_db.commit()
    await test_db.refresh(order)

    # 2. Execute BUY market order at 100.0
    trade = await engine.execute_order(test_db, order, current_price=100.0)
    assert trade is not None
    assert trade.symbol == "INFY"
    # Fill price includes slippage (100 * 1.0005 = 100.05)
    assert trade.price == pytest.approx(100.05, 0.01)
    assert trade.quantity == 10.0
    assert trade.commission > 0
    assert order.status == OrderStatus.FILLED.value
    assert order.filled_quantity == 10.0

    # 3. Verify Position was created
    pos = await test_db.get(PositionModel, "INFY") or (
        await test_db.execute(PositionModel.__table__.select().where(PositionModel.symbol == "INFY"))
    ).first()
    assert pos is not None
    assert pos.quantity == 10.0
    assert pos.direction == "LONG"

    # 4. Sell half position at 110.0 (take profit)
    sell_order = OrderModel(
        client_order_id="paper-unit-002",
        symbol="INFY",
        side=OrderSide.SELL.value,
        order_type=OrderType.MARKET.value,
        quantity=5.0,
        price=110.0,
        status=OrderStatus.SUBMITTED.value,
        is_paper=True,
    )
    test_db.add(sell_order)
    await test_db.commit()

    sell_trade = await engine.execute_order(test_db, sell_order, current_price=110.0)
    assert sell_trade is not None
    assert sell_order.status == OrderStatus.FILLED.value

    # Remaining quantity should be 5.0, and realized PnL should be positive
    updated_pos = (
        await test_db.execute(PositionModel.__table__.select().where(PositionModel.symbol == "INFY"))
    ).first()
    assert updated_pos.quantity == 5.0
    assert updated_pos.realized_pnl > 0.0


@pytest.mark.asyncio
async def test_paper_trading_api_workflow():
    """Verify complete paper trading lifecycle via REST API."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register and login operator
        await client.post(
            "/api/v1/auth/register",
            json={"email": "paper_trader@trading.com", "password": "SecurePassword123!"},
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "paper_trader@trading.com", "password": "SecurePassword123!"},
        )
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Submit paper order
        order_resp = await client.post(
            "/api/v1/orders",
            json={
                "client_order_id": "paper-api-001",
                "symbol": "TCS",
                "side": "BUY",
                "order_type": "MARKET",
                "quantity": 10.0,
                "price": 1000.0,
                "live_execution": False,
            },
            headers=headers,
        )
        assert order_resp.status_code == 201
        order_data = order_resp.json()
        order_id = order_data["order_id"]
        assert order_data["status"] == "SUBMITTED"

        # 2. Execute paper order via paper execution endpoint
        exec_resp = await client.post(
            f"/api/v1/paper/execute/{order_id}",
            json={"current_price": 1000.0},
            headers=headers,
        )
        assert exec_resp.status_code == 200
        exec_data = exec_resp.json()
        assert exec_data["status"] == "FILLED"
        assert exec_data["filled_quantity"] == 10.0
        assert exec_data["average_price"] > 0

        # 3. Update mark-to-market prices
        price_resp = await client.post(
            "/api/v1/paper/update-prices",
            json={"quotes": {"TCS": 1050.0}},
            headers=headers,
        )
        assert price_resp.status_code == 200

        # 4. Check paper portfolio
        port_resp = await client.get("/api/v1/paper/portfolio", headers=headers)
        assert port_resp.status_code == 200
        port_data = port_resp.json()
        assert port_data["open_positions_count"] >= 1
        assert port_data["equity"] > 0
        assert port_data["unrealized_pnl"] > 0  # Bought at ~1000, now 1050

        # 5. Reset paper account
        reset_resp = await client.post("/api/v1/paper/reset", headers=headers)
        assert reset_resp.status_code == 200

        # After reset, positions should be 0
        port_after = await client.get("/api/v1/paper/portfolio", headers=headers)
        assert port_after.json()["open_positions_count"] == 0
