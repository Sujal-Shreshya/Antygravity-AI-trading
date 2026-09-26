"""
Orders API router.
Manages order submission, order status querying, and cancellation.
Strictly routes through paper execution or validates live execution safety invariants.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import require_role
from backend.core.config import get_settings
from backend.core.kill_switch import kill_switch
from backend.core.models import (
    AccountBalance,
    OrderRequest,
    OrderResponse,
    OrderStatus,
    Position,
    RiskAction,
    TradeDirection,
)
from backend.database.models import OrderModel, PositionModel, RiskEventModel, UserModel
from backend.database.session import get_db
from backend.risk.base import RiskContext
from backend.risk.engine import risk_engine

router = APIRouter(prefix="/orders", tags=["Orders & Execution"])


@router.post(
    "", response_model=OrderResponse, status_code=status.HTTP_201_CREATED, summary="Submit order"
)
async def submit_order(
    order_in: OrderRequest,
    current_user: UserModel = Depends(require_role(["ADMIN", "OPERATOR"])),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    """
    Submits an order.
    Enforces that:
    1. If kill switch is active -> Rejects with 423 Locked.
    2. If live_execution=True while LIVE_TRADING=False -> Rejects with 403 Forbidden.
    3. Idempotent: rejects duplicate client_order_id.
    4. Evaluates Pre-Trade Risk Engine constraints (1% trade risk, daily loss, drawdown, max positions, exposure).
    """
    # 1. Kill Switch Check
    if kill_switch.is_active:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Order submission blocked: Emergency kill switch is active. Reason: {kill_switch.get_status()['reason']}",
        )

    # 2. Live Trading Guard
    settings = get_settings()
    if order_in.live_execution and not settings.LIVE_TRADING:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Live trading order rejected: System configuration has LIVE_TRADING=false.",
        )

    # 3. Duplicate Order Check
    existing_query = select(OrderModel).where(
        OrderModel.client_order_id == order_in.client_order_id
    )
    existing_res = await db.execute(existing_query)
    if existing_res.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate client order ID detected: {order_in.client_order_id}",
        )

    # 4. Pre-trade Risk Context Construction & Evaluation
    pos_res = await db.execute(select(PositionModel))
    db_positions = pos_res.scalars().all()

    risk_positions = [
        Position(
            symbol=p.symbol,
            direction=TradeDirection(p.direction),
            quantity=p.quantity,
            entry_price=p.entry_price,
            current_price=p.current_price,
            unrealized_pnl=p.unrealized_pnl,
            realized_pnl=p.realized_pnl,
            stop_loss=p.stop_loss,
            take_profit=p.take_profit,
        )
        for p in db_positions
    ]

    total_realized_loss = sum(abs(p.realized_pnl) for p in db_positions if p.realized_pnl < 0)
    total_unrealized_loss = sum(abs(p.unrealized_pnl) for p in db_positions if p.unrealized_pnl < 0)
    baseline_equity = 100_000.0 + sum(p.realized_pnl + p.unrealized_pnl for p in db_positions)

    risk_context = RiskContext(
        account_balance=AccountBalance(
            cash=100_000.0,
            equity=max(baseline_equity, 10_000.0),
            available_margin=max(baseline_equity, 10_000.0),
        ),
        open_positions=risk_positions,
        daily_realized_loss=total_realized_loss,
        daily_unrealized_loss=total_unrealized_loss,
        peak_portfolio_equity=max(baseline_equity, 100_000.0),
        current_portfolio_equity=max(baseline_equity, 10_000.0),
    )

    risk_decision = risk_engine.evaluate_order(order_in, risk_context)

    if not risk_decision.is_approved or risk_decision.action == RiskAction.REJECT:
        # Persist risk rejection event
        risk_event = RiskEventModel(
            rule_name=risk_decision.rule_name,
            action=risk_decision.action.value,
            reason=risk_decision.reason,
            details={
                "client_order_id": order_in.client_order_id,
                "symbol": order_in.symbol,
                "side": order_in.side.value,
                "quantity": order_in.quantity,
                "metrics": risk_decision.metrics,
            },
        )
        db.add(risk_event)
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Pre-trade risk rejected: {risk_decision.reason}",
        )

    # If risk resized order quantity
    effective_quantity = (
        risk_decision.adjusted_quantity
        if (risk_decision.action == RiskAction.MODIFY and risk_decision.adjusted_quantity)
        else order_in.quantity
    )
    db_order = OrderModel(
        client_order_id=order_in.client_order_id,
        symbol=order_in.symbol,
        side=order_in.side.value,
        order_type=order_in.order_type.value,
        quantity=effective_quantity,
        price=order_in.price,
        stop_price=order_in.stop_price,
        filled_quantity=0.0,
        average_price=None,
        status=OrderStatus.SUBMITTED.value,
        is_paper=not order_in.live_execution,
        strategy_id=order_in.strategy_id,
        broker_message="Order accepted into execution queue",
    )
    db.add(db_order)
    await db.commit()
    await db.refresh(db_order)

    return OrderResponse(
        order_id=db_order.order_id,
        client_order_id=db_order.client_order_id,
        symbol=db_order.symbol,
        side=order_in.side,
        order_type=order_in.order_type,
        quantity=db_order.quantity,
        price=db_order.price,
        filled_quantity=db_order.filled_quantity,
        average_price=db_order.average_price,
        status=OrderStatus(db_order.status),
        is_paper=db_order.is_paper,
        created_at=db_order.created_at,
        updated_at=db_order.updated_at,
        broker_message=db_order.broker_message,
    )


@router.get("", response_model=list[OrderResponse], summary="List orders")
async def list_orders(
    symbol: str | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> list[OrderResponse]:
    """Retrieves orders with optional filtering by symbol and status."""
    query = select(OrderModel).order_by(desc(OrderModel.created_at)).limit(limit)
    if symbol:
        query = query.where(OrderModel.symbol == symbol)
    if status_filter:
        query = query.where(OrderModel.status == status_filter)

    result = await db.execute(query)
    orders = result.scalars().all()

    return [
        OrderResponse(
            order_id=o.order_id,
            client_order_id=o.client_order_id,
            symbol=o.symbol,
            side=o.side,
            order_type=o.order_type,
            quantity=o.quantity,
            price=o.price,
            filled_quantity=o.filled_quantity,
            average_price=o.average_price,
            status=OrderStatus(o.status),
            is_paper=o.is_paper,
            created_at=o.created_at,
            updated_at=o.updated_at,
            broker_message=o.broker_message,
        )
        for o in orders
    ]


@router.delete("/{order_id}", response_model=OrderResponse, summary="Cancel order")
async def cancel_order(
    order_id: str,
    current_user: UserModel = Depends(require_role(["ADMIN", "OPERATOR"])),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    """Cancels an open working order."""
    order = await db.get(OrderModel, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if order.status in (
        OrderStatus.FILLED.value,
        OrderStatus.CANCELLED.value,
        OrderStatus.REJECTED.value,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel order in state {order.status}",
        )

    order.status = OrderStatus.CANCELLED.value
    order.broker_message = "Order cancelled by user"
    await db.commit()
    await db.refresh(order)

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
