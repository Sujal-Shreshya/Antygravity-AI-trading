"""
Risk management router.
Provides endpoints for emergency kill switch control, limit inspections, and risk events.
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import require_role
from backend.core.config import get_settings
from backend.core.kill_switch import kill_switch
from backend.database.models import RiskEventModel, UserModel
from backend.database.session import get_db

router = APIRouter(prefix="/risk", tags=["Risk Management & Kill Switch"])


class KillSwitchRequest(BaseModel):
    reason: str = Field(
        ..., min_length=3, description="Operational justification for kill switch action"
    )


@router.get("/status", summary="Get risk engine parameters and kill switch state")
async def get_risk_status() -> dict[str, Any]:
    """Returns current risk parameters, active limits, and kill switch status."""
    settings = get_settings()
    return {
        "kill_switch": kill_switch.get_status(),
        "live_trading_enabled": settings.LIVE_TRADING,
        "parameters": {
            "max_risk_per_trade_pct": settings.RISK_MAX_RISK_PER_TRADE_PCT,
            "max_daily_loss_pct": settings.RISK_MAX_DAILY_LOSS_PCT,
            "max_portfolio_drawdown_pct": settings.RISK_MAX_PORTFOLIO_DRAWDOWN_PCT,
            "max_open_positions": settings.RISK_MAX_OPEN_POSITIONS,
            "max_single_position_pct": settings.RISK_MAX_SINGLE_POSITION_PCT,
            "min_risk_reward_ratio": settings.RISK_MIN_RISK_REWARD_RATIO,
        },
    }


@router.post("/kill-switch/activate", summary="Engage emergency kill switch")
async def activate_kill_switch(
    payload: KillSwitchRequest,
    current_user: UserModel = Depends(require_role(["ADMIN", "OPERATOR"])),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Engages the global emergency kill switch. Rejects new orders immediately."""
    kill_switch.activate(reason=payload.reason, operator_id=current_user.email)

    event = RiskEventModel(
        rule_name="EMERGENCY_KILL_SWITCH",
        action="TRIGGER_KILL_SWITCH",
        reason=payload.reason,
        details={"operator": current_user.email},
    )
    db.add(event)
    await db.commit()

    return {
        "message": "Emergency kill switch engaged successfully.",
        "status": kill_switch.get_status(),
    }


@router.post("/kill-switch/deactivate", summary="Disengage emergency kill switch")
async def deactivate_kill_switch(
    current_user: UserModel = Depends(require_role(["ADMIN"])),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Disengages the emergency kill switch (Admin only)."""
    kill_switch.deactivate(operator_id=current_user.email)

    event = RiskEventModel(
        rule_name="EMERGENCY_KILL_SWITCH",
        action="DISENGAGE_KILL_SWITCH",
        reason="Manual operator deactivation",
        details={"operator": current_user.email},
    )
    db.add(event)
    await db.commit()

    return {
        "message": "Emergency kill switch disengaged successfully.",
        "status": kill_switch.get_status(),
    }


@router.get("/events", summary="List historical risk events")
async def list_risk_events(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Returns audit trail of risk rejection and circuit breaker events."""
    query = select(RiskEventModel).order_by(desc(RiskEventModel.created_at)).limit(limit)
    result = await db.execute(query)
    events = result.scalars().all()
    return [
        {
            "id": e.id,
            "rule_name": e.rule_name,
            "action": e.action,
            "reason": e.reason,
            "details": e.details,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]
