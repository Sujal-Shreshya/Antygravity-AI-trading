"""
Paper Trading API Router.
Provides endpoints for executing simulated orders, mark-to-market position updates,
and paper account lifecycle management.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import require_role
from backend.core.models import OrderResponse, OrderStatus
from backend.database.models import OrderModel, UserModel
from backend.database.session import get_db
from backend.paper_trading.engine import paper_engine

router = APIRouter(prefix="/paper", tags=["Paper Trading & Simulation"])


class ExecutePaperOrderRequest(BaseModel):
    current_price: float = Field(..., gt=0, description="Current market price for fill calculation")


class PriceUpdateRequest(BaseModel):
    quotes: dict[str, float] = Field(..., description="Mapping of symbol to current market price")


@router.post("/execute/{order_id}", response_model=OrderResponse, summary="Execute working paper order")
async def execute_paper_order(
    order_id: str,
    payload: ExecutePaperOrderRequest,
    current_user: UserModel = Depends(require_role(["ADMIN", "OPERATOR"])),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    """Simulates market or limit fill for a paper order at the provided market price."""
    order = await db.get(OrderModel, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if not order.is_paper:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot execute non-paper order through paper engine",
        )

    await paper_engine.execute_order(db, order, current_price=payload.current_price)

    return OrderResponse(
        order_id=order.order_id,
        client_order_id=order.client_order_id,
        symbol=order.symbol,
        side=order.side,
        order_type=order.order_type,
        quantity=order.quantity,
        price=order.price,
        filled_quantity=order.filled_quantity,
        average_price=order.average_price,
        status=OrderStatus(order.status),
        is_paper=order.is_paper,
        created_at=order.created_at,
        updated_at=order.updated_at,
        broker_message=order.broker_message,
    )


@router.post("/update-prices", summary="Update mark-to-market prices for paper positions")
async def update_paper_prices(
    payload: PriceUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Updates current market valuations and unrealized P&L across all paper positions."""
    await paper_engine.update_market_prices(db, payload.quotes)
    return {"message": f"Updated valuations for {len(payload.quotes)} symbols"}


@router.get("/portfolio", summary="Get paper trading portfolio snapshot")
async def get_paper_portfolio(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Returns comprehensive paper portfolio equity, cash, realized, and unrealized P&L."""
    return await paper_engine.get_portfolio_snapshot(db)


@router.post("/reset", summary="Reset paper trading account")
async def reset_paper_account(
    current_user: UserModel = Depends(require_role(["ADMIN"])),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Resets paper account, wiping simulated positions, trades, and orders."""
    await paper_engine.reset_paper_account(db)
    return {"message": "Paper trading account reset successfully to initial state"}
