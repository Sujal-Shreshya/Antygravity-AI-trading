"""
System Telemetry, Health, and Audit Logging.
Tracks system uptime, memory footprints, execution latencies, risk triggers,
and persists audit trail events into PostgreSQL.
"""

import logging
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import AuditLogModel

logger = logging.getLogger("trading.monitoring.telemetry")


class TelemetryRegistry:
    """Central repository for platform operational telemetry and metrics."""

    def __init__(self) -> None:
        self.start_time = time.time()
        self.counters: dict[str, int] = {
            "orders_submitted": 0,
            "orders_filled": 0,
            "orders_rejected_by_risk": 0,
            "circuit_breakers_tripped": 0,
            "kill_switch_engagements": 0,
            "market_ticks_processed": 0,
            "signals_generated": 0,
        }
        self.latencies: dict[str, list[float]] = {
            "risk_evaluation_ms": [],
            "signal_generation_ms": [],
            "order_fill_ms": [],
        }

    def record_counter(self, name: str, delta: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + delta

    def record_latency(self, metric: str, duration_ms: float) -> None:
        if metric not in self.latencies:
            self.latencies[metric] = []
        # Keep ring buffer of last 100 measurements
        self.latencies[metric].append(duration_ms)
        if len(self.latencies[metric]) > 100:
            self.latencies[metric].pop(0)

    def get_metrics(self) -> dict[str, Any]:
        """Returns comprehensive telemetry snapshot."""
        uptime_seconds = int(time.time() - self.start_time)
        avg_latencies = {
            k: (round(sum(v) / len(v), 2) if v else 0.0)
            for k, v in self.latencies.items()
        }

        return {
            "uptime_seconds": uptime_seconds,
            "uptime_human": f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s",
            "counters": self.counters,
            "average_latencies_ms": avg_latencies,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    async def log_audit_event(
        self,
        db: AsyncSession,
        event_type: str,
        operator_id: str,
        details: dict[str, Any],
        ip_address: str | None = None,
    ) -> AuditLogModel:
        """Persists an immutable audit log entry into PostgreSQL."""
        record = AuditLogModel(
            event_type=event_type,
            operator_id=operator_id,
            details=details,
            ip_address=ip_address,
            created_at=datetime.now(UTC),
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        logger.info(f"[AUDIT LOG] {event_type} by {operator_id}: {details}")
        return record


telemetry = TelemetryRegistry()
