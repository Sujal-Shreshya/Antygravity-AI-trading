"""
Unit and integration tests for Notifications & Monitoring Subsystems (Phase 11).
Tests:
- Multi-channel notification dispatcher (Telegram, Webhook, Email)
- Error isolation: failing channel does not impact execution
- System telemetry, counters, and latency profiling
- Audit log persistence in database
- API endpoints (/monitoring/metrics, /monitoring/audit-logs, /monitoring/test-alert)
"""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.monitoring.telemetry import TelemetryRegistry, telemetry
from backend.notifications.channels import (
    BaseNotificationChannel,
    NotificationEvent,
)
from backend.notifications.dispatcher import NotificationDispatcher


class MockFailingChannel(BaseNotificationChannel):
    """Test channel that deliberately raises an exception."""

    def __init__(self) -> None:
        super().__init__("MockFailing")

    async def send(self, event: NotificationEvent) -> bool:
        raise ConnectionResetError("Simulated upstream network partition")


@pytest.mark.asyncio
async def test_notification_dispatcher_isolation():
    dispatcher = NotificationDispatcher()
    failing = MockFailingChannel()
    dispatcher.register_channel("failing", failing)

    event = NotificationEvent(
        title="Test Event",
        message="System health check",
        level="INFO",
        event_type="TEST",
    )

    # Broadcast must NOT raise an exception despite the failing channel
    results = await dispatcher.broadcast(event)
    assert "telegram" in results
    assert results["telegram"] is True
    assert results["failing"] is False


@pytest.mark.asyncio
async def test_convenience_notifications():
    dispatcher = NotificationDispatcher()

    # Trade fill
    res_trade = await dispatcher.notify_trade_fill(
        symbol="RELIANCE",
        side="BUY",
        quantity=10,
        price=2500.0,
        order_id="test_ord_123",
        is_paper=True,
    )
    assert res_trade["telegram"] is True

    # Circuit breaker
    res_cb = await dispatcher.notify_circuit_breaker(
        breaker_name="MAX_DAILY_LOSS",
        reason="Daily loss exceeded 3%",
        metrics={"current_loss": 3500.0},
    )
    assert res_cb["telegram"] is True

    # Kill switch
    res_ks = await dispatcher.notify_kill_switch(
        is_active=True,
        operator="admin@trading.com",
        reason="Emergency halt",
    )
    assert res_ks["telegram"] is True


def test_telemetry_registry():
    registry = TelemetryRegistry()
    registry.record_counter("orders_submitted", 5)
    registry.record_counter("orders_filled", 4)
    registry.record_latency("risk_evaluation_ms", 1.25)
    registry.record_latency("risk_evaluation_ms", 1.75)

    metrics = registry.get_metrics()
    assert metrics["counters"]["orders_submitted"] == 5
    assert metrics["counters"]["orders_filled"] == 4
    assert metrics["average_latencies_ms"]["risk_evaluation_ms"] == 1.50
    assert "uptime_seconds" in metrics


@pytest.mark.asyncio
async def test_monitoring_api_and_audit_logs(test_db):
    """Verify /api/v1/monitoring routes and database audit persistence."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register and login admin
        await client.post(
            "/api/v1/auth/register",
            json={"email": "audit_admin@trading.com", "password": "SecurePassword123!"},
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "audit_admin@trading.com", "password": "SecurePassword123!"},
        )
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Get metrics
        m_resp = await client.get("/api/v1/monitoring/metrics")
        assert m_resp.status_code == 200
        m_data = m_resp.json()
        assert "uptime_seconds" in m_data
        assert "counters" in m_data

        # 2. Log an audit event
        await telemetry.log_audit_event(
            db=test_db,
            event_type="OPERATOR_OVERRIDE",
            operator_id="audit_admin@trading.com",
            details={"action": "threshold_adjustment"},
        )

        # 3. Query audit logs
        a_resp = await client.get("/api/v1/monitoring/audit-logs", headers=headers)
        assert a_resp.status_code == 200
        logs = a_resp.json()
        assert len(logs) >= 1
        assert any(log_entry["event_type"] == "OPERATOR_OVERRIDE" for log_entry in logs)

        # 4. Dispatch test alert
        alert_resp = await client.post(
            "/api/v1/monitoring/test-alert",
            json={"title": "Verification Alert", "message": "All channels operational", "level": "INFO"},
            headers=headers,
        )
        assert alert_resp.status_code == 200
        assert alert_resp.json()["channel_results"]["telegram"] is True
