"""
Positions router.
Retrieves open positions across all traded symbols and markets.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import PositionModel
from backend.database.session import get_db

router = APIRouter(prefix="/positions", tags=["Portfolio & Positions"])


@router.get("", summary="List open positions")
async def list_positions(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """Retrieves all active open positions."""
    query = select(PositionModel)
    result = await db.execute(query)
    positions = result.scalars().all()
    return [
        {
            "id": p.id,
            "symbol": p.symbol,
            "direction": p.direction,
            "quantity": p.quantity,
            "entry_price": p.entry_price,
            "current_price": p.current_price,
            "unrealized_pnl": p.unrealized_pnl,
            "realized_pnl": p.realized_pnl,
            "stop_loss": p.stop_loss,
            "take_profit": p.take_profit,
            "is_paper": p.is_paper,
            "updated_at": p.updated_at.isoformat(),
        }
        for p in positions
    ]
