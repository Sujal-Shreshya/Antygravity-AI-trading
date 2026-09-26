"""
Health and readiness monitoring endpoints.
Provides kubernetes/docker-compatible liveness, readiness, and subsystem status probes.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.core.kill_switch import kill_switch
from backend.database.session import get_db

router = APIRouter(prefix="/health", tags=["Health & Monitoring"])


@router.get("", summary="Liveness probe")
async def liveness() -> dict[str, Any]:
    """Basic liveness check verifying the application process is running."""
    settings = get_settings()
    return {
        "status": "healthy",
        "live_trading_enabled": settings.LIVE_TRADING,
        "kill_switch_active": kill_switch.is_active,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/ready", summary="Readiness probe")
async def readiness(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Readiness probe verifying persistent storage and engine readiness."""
    try:
        await db.execute(text("SELECT 1"))
        db_healthy = True
    except Exception as e:
        db_healthy = False
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database readiness check failed: {e}",
        ) from e

    return {
        "status": "ready",
        "database": "connected" if db_healthy else "unavailable",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/status", summary="Detailed system telemetry")
async def detailed_status(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Detailed operational telemetry for system operators."""
    settings = get_settings()

    db_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    return {
        "engine": "AI Trading Engine",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
        "live_trading": {
            "enabled": settings.LIVE_TRADING,
            "mode": "REAL_CAPITAL" if settings.LIVE_TRADING else "PAPER_SIMULATION",
        },
        "kill_switch": kill_switch.get_status(),
        "database": {
            "status": "healthy" if db_ok else "unhealthy",
            "host": settings.POSTGRES_HOST,
        },
        "risk_limits": {
            "max_risk_per_trade_pct": settings.RISK_MAX_RISK_PER_TRADE_PCT,
            "max_daily_loss_pct": settings.RISK_MAX_DAILY_LOSS_PCT,
            "max_portfolio_drawdown_pct": settings.RISK_MAX_PORTFOLIO_DRAWDOWN_PCT,
            "max_open_positions": settings.RISK_MAX_OPEN_POSITIONS,
        },
        "timestamp": datetime.now(UTC).isoformat(),
    }
