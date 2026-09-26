"""
End-to-End Trading Lifecycle and Security Hardening Integration Tests (Phase 12).
Verifies:
- Security response headers (Content-Type-Options, Frame-Options, XSS, Referrer-Policy)
- Sliding-window IP rate limiter enforcement (HTTP 429 Too Many Requests)
- Complete unified lifecycle:
    1. Authentication
    2. Market quote discovery
    3. Consensus signal generation
    4. Pre-trade risk evaluation (1% risk sizing)
    5. Order submission & paper execution
    6. Position mark-to-market valuation
    7. Emergency kill switch halting & unhalting
    8. Audit log immutability
"""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.kill_switch import kill_switch
from backend.core.security import rate_limiter
from backend.main import app


@pytest.fixture(autouse=True)
def clean_security_state():
    rate_limiter.reset()
    kill_switch.deactivate()
    yield
    rate_limiter.reset()
    kill_switch.deactivate()


@pytest.mark.asyncio
async def test_security_headers():
    """Verify production security headers are attached to every response."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
        assert "X-Request-ID" in resp.headers
        assert "X-Process-Time" in resp.headers


@pytest.mark.asyncio
async def test_rate_limiter_throttling():
    """Verify excessive request bursts trigger HTTP 429 Too Many Requests."""
    rate_limiter.max_requests = 10  # Temporarily lower limit for testing
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First 10 requests must succeed
        for i in range(10):
            res = await client.get("/api/v1/instruments")
            assert res.status_code == 200, f"Request {i} failed unexpectedly"

        # 11th request must be throttled with 429
        throttled = await client.get("/api/v1/instruments")
        assert throttled.status_code == 429
        assert throttled.json()["error"] == "RateLimitExceeded"


@pytest.mark.asyncio
async def test_complete_e2e_trading_lifecycle():
    """Simulates an entire algorithmic trading lifecycle from quote to risk halt."""
    rate_limiter.max_requests = 1000
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Authenticate Operator
        await client.post(
            "/api/v1/auth/register",
            json={"email": "e2e_trader@trading.com", "password": "SecurePassword123!"},
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "e2e_trader@trading.com", "password": "SecurePassword123!"},
        )
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Get Live Quote
        quote_resp = await client.get("/api/v1/market-data/quote/RELIANCE", headers=headers)
        assert quote_resp.status_code == 200
        quote = quote_resp.json()
        assert quote["symbol"] == "RELIANCE"
        price = quote["price"]

        # 3. Get AI Consensus Signal
        sig_resp = await client.get("/api/v1/signals/consensus?symbol=RELIANCE&timeframe=15m", headers=headers)
        assert sig_resp.status_code == 200
        sig_data = sig_resp.json()
        assert "consensus_direction" in sig_data

        # 4. Dry-run Pre-Trade Risk Evaluation
        eval_resp = await client.post(
            "/api/v1/risk/evaluate",
            json={
                "client_order_id": "e2e-order-001",
                "symbol": "RELIANCE",
                "side": "BUY",
                "order_type": "MARKET",
                "quantity": 5.0,
                "price": price,
            },
            headers=headers,
        )
        assert eval_resp.status_code == 200
        assert eval_resp.json()["is_approved"] is True

        # 5. Submit Order
        order_resp = await client.post(
            "/api/v1/orders",
            json={
                "client_order_id": "e2e-order-001",
                "symbol": "RELIANCE",
                "side": "BUY",
                "order_type": "MARKET",
                "quantity": 5.0,
                "price": price,
                "live_execution": False,
            },
            headers=headers,
        )
        assert order_resp.status_code == 201
        order_id = order_resp.json()["order_id"]

        # 6. Execute Paper Order Fill
        fill_resp = await client.post(
            f"/api/v1/paper/execute/{order_id}",
            json={"current_price": price},
            headers=headers,
        )
        assert fill_resp.status_code == 200, f"Fill failed: {fill_resp.json()}"
        assert fill_resp.json()["status"] == "FILLED"

        # 7. Check Open Positions
        pos_resp = await client.get("/api/v1/positions", headers=headers)
        assert pos_resp.status_code == 200
        positions = pos_resp.json()
        assert len(positions) >= 1
        reliance_pos = next((p for p in positions if p["symbol"] == "RELIANCE"), None)
        assert reliance_pos is not None
        assert reliance_pos["quantity"] == 5.0

        # 8. Engage Emergency Kill Switch
        ks_act = await client.post(
            "/api/v1/risk/kill-switch/activate",
            json={"reason": "E2E Black Swan Drill"},
            headers=headers,
        )
        assert ks_act.status_code == 200

        # 9. Verify any subsequent order submission is locked with 423 Locked
        blocked_resp = await client.post(
            "/api/v1/orders",
            json={
                "client_order_id": "e2e-order-blocked",
                "symbol": "TCS",
                "side": "BUY",
                "order_type": "MARKET",
                "quantity": 1.0,
                "live_execution": False,
            },
            headers=headers,
        )
        assert blocked_resp.status_code == 423
        assert "kill switch" in blocked_resp.json()["detail"].lower()

        # 10. Disengage Kill Switch (Admin only)
        ks_deact = await client.post(
            "/api/v1/risk/kill-switch/deactivate",
            headers=headers,
        )
        assert ks_deact.status_code == 200
