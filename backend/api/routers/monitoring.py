"""
Monitoring, Telemetry, and Alerting API Router.
Provides operational health metrics, latency stats, audit trails, and test notification dispatchers.
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import require_role
from backend.database.models import AuditLogModel, UserModel
from backend.database.session import get_db
from backend.monitoring.telemetry import telemetry
from backend.notifications.channels import NotificationEvent
from backend.notifications.dispatcher import notification_dispatcher

router = APIRouter(prefix="/monitoring", tags=["Monitoring & Observability"])


class TestAlertRequest(BaseModel):
    title: str = "Test System Alert"
    message: str = "This is a diagnostic notification from AI Trading Engine."
    level: str = "INFO"


@router.get("/metrics", summary="Get operational telemetry and performance metrics")
async def get_system_metrics() -> dict[str, Any]:
    """Returns uptime, order processing counters, and sub-millisecond latency profiles."""
    return telemetry.get_metrics()


@router.get("/audit-logs", summary="List immutable system audit logs")
async def get_audit_logs(
    limit: int = 50,
    current_user: UserModel = Depends(require_role(["ADMIN", "OPERATOR"])),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Retrieves immutable audit trail of operator logins, order routing, and circuit breaker events."""
    query = select(AuditLogModel).order_by(desc(AuditLogModel.created_at)).limit(limit)
    res = await db.execute(query)
    logs = res.scalars().all()

    return [
        {
            "id": log.id,
            "event_type": log.event_type,
            "operator_id": log.operator_id,
            "details": log.details,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


@router.post("/test-alert", summary="Broadcast a test alert across channels")
async def broadcast_test_alert(
    payload: TestAlertRequest,
    current_user: UserModel = Depends(require_role(["ADMIN"])),
) -> dict[str, Any]:
    """Dispatches a test notification to verify Telegram, Webhook, and Email alerting channels."""
    event = NotificationEvent(
        title=payload.title,
        message=payload.message,
        level=payload.level,
        event_type="SYSTEM_ALERT",
        details={"operator": current_user.email},
    )
    results = await notification_dispatcher.broadcast(event)
    return {"message": "Test alert broadcast complete", "channel_results": results}
