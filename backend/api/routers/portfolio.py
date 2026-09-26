"""
Portfolio balance router.
Calculates and returns current cash balance, total portfolio equity, and available margin.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import PositionModel
from backend.database.session import get_db

router = APIRouter(prefix="/portfolio", tags=["Portfolio & Balances"])


@router.get("/balance", summary="Get portfolio account balance")
async def get_portfolio_balance(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Computes total equity and unrealized P&L from positions."""
    query = select(func.sum(PositionModel.unrealized_pnl), func.sum(PositionModel.realized_pnl))
    result = await db.execute(query)
    unrealized_sum, realized_sum = result.first() or (0.0, 0.0)

    unrealized = float(unrealized_sum or 0.0)
    realized = float(realized_sum or 0.0)

    # Base initial paper capital: 1,000,000 INR
    base_cash = 1000000.0 + realized
    equity = base_cash + unrealized

    return {
        "currency": "INR",
        "cash": round(base_cash, 2),
        "equity": round(equity, 2),
        "unrealized_pnl": round(unrealized, 2),
        "realized_pnl": round(realized, 2),
        "available_margin": round(base_cash * 0.8, 2),
        "is_paper": True,
        "timestamp": datetime.now(UTC).isoformat(),
    }
