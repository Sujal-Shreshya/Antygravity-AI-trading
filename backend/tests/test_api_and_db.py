"""
Integration tests for FastAPI endpoints, database persistence, authentication, and order safety.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest.mark.asyncio
async def test_health_endpoints():
    """Verify health and readiness probes."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["live_trading_enabled"] is False

        ready_resp = await client.get("/health/ready")
        assert ready_resp.status_code == 200
        assert ready_resp.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_auth_workflow_and_rbac():
    """Verify user registration, admin promotion, JWT login, and profile retrieval."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register first user -> should automatically become ADMIN
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "admin@trading.com", "password": "SecurePassword123!"},
        )
        assert reg_resp.status_code == 201
        admin_data = reg_resp.json()
        assert admin_data["role"] == "ADMIN"
        assert admin_data["email"] == "admin@trading.com"

        # Login
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@trading.com", "password": "SecurePassword123!"},
        )
        assert login_resp.status_code == 200
        token_data = login_resp.json()
        assert "access_token" in token_data
        token = token_data["access_token"]

        # Access /me with Bearer token
        me_resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == "admin@trading.com"

        # Access /me without token -> 401 Unauthorized
        anon_resp = await client.get("/api/v1/auth/me")
        assert anon_resp.status_code == 401


@pytest.mark.asyncio
async def test_instruments_crud():
    """Verify instrument creation and listing with market filters."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register and login admin
        await client.post(
            "/api/v1/auth/register",
            json={"email": "trader@trading.com", "password": "SecurePassword123!"},
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "trader@trading.com", "password": "SecurePassword123!"},
        )
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create instrument
        inst_payload = {
            "symbol": "RELIANCE",
            "name": "Reliance Industries Ltd",
            "market": "INDIAN_EQUITY",
            "exchange": "NSE",
            "tick_size": 0.05,
            "lot_size": 1,
            "is_active": True,
        }
        create_resp = await client.post("/api/v1/instruments", json=inst_payload, headers=headers)
        assert create_resp.status_code == 201
        assert create_resp.json()["symbol"] == "RELIANCE"

        # List instruments
        list_resp = await client.get("/api/v1/instruments?market=INDIAN_EQUITY")
        assert list_resp.status_code == 200
        items = list_resp.json()
        assert len(items) == 1
        assert items[0]["symbol"] == "RELIANCE"


@pytest.mark.asyncio
async def test_order_safety_guards_via_api():
    """
    Verify:
    1. Paper orders are accepted.
    2. Live orders are blocked when LIVE_TRADING=False.
    3. Kill switch blocks orders with 423 Locked.
    4. Duplicate orders are rejected with 409 Conflict.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register and login admin
        await client.post(
            "/api/v1/auth/register",
            json={"email": "operator@trading.com", "password": "SecurePassword123!"},
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "operator@trading.com", "password": "SecurePassword123!"},
        )
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Valid paper order
        order_payload = {
            "client_order_id": "test-order-001",
            "symbol": "TCS",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 10,
            "live_execution": False,
        }
        order_resp = await client.post("/api/v1/orders", json=order_payload, headers=headers)
        assert order_resp.status_code == 201
        data = order_resp.json()
        assert data["status"] == "SUBMITTED"
        assert data["is_paper"] is True

        # 2. Duplicate order check
        dup_resp = await client.post("/api/v1/orders", json=order_payload, headers=headers)
        assert dup_resp.status_code == 409

        # 3. Live order blocked
        live_payload = {
            "client_order_id": "test-order-002",
            "symbol": "INFY",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 5,
            "live_execution": True,  # LIVE ORDER REQUEST
        }
        live_resp = await client.post("/api/v1/orders", json=live_payload, headers=headers)
        assert live_resp.status_code == 403

        # 4. Activate Kill Switch via API
        ks_resp = await client.post(
            "/api/v1/risk/kill-switch/activate",
            json={"reason": "Market gap test"},
            headers=headers,
        )
        assert ks_resp.status_code == 200

        # 5. Order while kill switch is active -> 423 Locked
        ks_order = {
            "client_order_id": "test-order-003",
            "symbol": "TCS",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 10,
            "live_execution": False,
        }
        blocked_resp = await client.post("/api/v1/orders", json=ks_order, headers=headers)
        assert blocked_resp.status_code == 423
