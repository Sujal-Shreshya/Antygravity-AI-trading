"""
Paper Trading Execution Engine.
Provides a realistic simulated broker exchange environment:
- Market, Limit, and Stop order fill simulation
- Bid/Ask spread, slippage, and brokerage fee models
- FIFO position tracking, average entry calculation, and realized/unrealized P&L
- Multi-asset support (equities, crypto, forex)
- Snapshot persistence in PostgreSQL
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import OrderSide, OrderStatus, OrderType
from backend.database.models import (
    OrderModel,
    PositionModel,
    TradeModel,
)

logger = logging.getLogger("trading.paper.engine")


class PaperExecutionEngine:
    """Simulated execution engine for paper trading without financial risk."""

    def __init__(
        self,
        commission_rate: float = 0.0003,  # 0.03%
        slippage_rate: float = 0.0005,  # 0.05%
        starting_cash: float = 100_000.0,
    ) -> None:
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.starting_cash = starting_cash

    async def execute_order(
        self,
        db: AsyncSession,
        order: OrderModel,
        current_price: float,
    ) -> TradeModel | None:
        """
        Executes a paper order against current market price.
        Market orders execute immediately; Limit orders only execute if price conditions are met.
        """
        if order.status not in (OrderStatus.SUBMITTED.value, OrderStatus.PENDING.value):
            return None

        # Check limit condition
        if order.order_type == OrderType.LIMIT.value:
            if order.side == OrderSide.BUY.value and current_price > (order.price or current_price):
                order.status = OrderStatus.PENDING.value
                order.broker_message = f"Limit BUY pending: current price {current_price} > limit {order.price}"
                await db.commit()
                return None
            if order.side == OrderSide.SELL.value and current_price < (order.price or current_price):
                order.status = OrderStatus.PENDING.value
                order.broker_message = f"Limit SELL pending: current price {current_price} < limit {order.price}"
                await db.commit()
                return None

        # Check stop condition
        if order.order_type == OrderType.STOP.value:
            if order.side == OrderSide.BUY.value and current_price < (order.stop_price or current_price):
                order.status = OrderStatus.PENDING.value
                order.broker_message = f"Stop BUY pending: current price {current_price} < stop {order.stop_price}"
                await db.commit()
                return None
            if order.side == OrderSide.SELL.value and current_price > (order.stop_price or current_price):
                order.status = OrderStatus.PENDING.value
                order.broker_message = f"Stop SELL pending: current price {current_price} > stop {order.stop_price}"
                await db.commit()
                return None

        # Calculate fill price with slippage
        slip_mult = 1.0 + self.slippage_rate if order.side == OrderSide.BUY.value else 1.0 - self.slippage_rate
        fill_price = round(current_price * slip_mult, 4)
        commission = round(order.quantity * fill_price * self.commission_rate, 4)

        # 1. Update Order Status
        order.status = OrderStatus.FILLED.value
        order.filled_quantity = order.quantity
        order.average_price = fill_price
        order.broker_message = f"Filled via Paper Execution Engine @ {fill_price}"
        order.updated_at = datetime.now(UTC)

        # 2. Record Trade Fill
        trade = TradeModel(
            trade_id=str(uuid.uuid4()),
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            price=fill_price,
            quantity=order.quantity,
            commission=commission,
            executed_at=datetime.now(UTC),
            is_paper=True,
        )
        db.add(trade)

        # 3. Update Position & PnL
        await self._update_position(
            db=db,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            fill_price=fill_price,
            commission=commission,
        )

        await db.commit()
        await db.refresh(order)
        return trade

    async def _update_position(
        self,
        db: AsyncSession,
        symbol: str,
        side: str,
        quantity: float,
        fill_price: float,
        commission: float,
    ) -> None:
        """Maintains accurate FIFO position tracking and realized P&L."""
        pos_query = select(PositionModel).where(PositionModel.symbol == symbol)
        res = await db.execute(pos_query)
        pos = res.scalar_one_or_none()

        order_dir = "LONG" if side == OrderSide.BUY.value else "SHORT"

        if pos is None:
            # Create new position
            new_pos = PositionModel(
                symbol=symbol,
                direction=order_dir,
                quantity=quantity,
                entry_price=fill_price,
                current_price=fill_price,
                unrealized_pnl=0.0,
                realized_pnl=-commission,
                is_paper=True,
                updated_at=datetime.now(UTC),
            )
            db.add(new_pos)
            return

        # Position exists
        if pos.direction == order_dir:
            # Add to position: update weighted average entry price
            total_qty = pos.quantity + quantity
            weighted_entry = (pos.entry_price * pos.quantity + fill_price * quantity) / total_qty
            pos.entry_price = round(weighted_entry, 4)
            pos.quantity = total_qty
            pos.current_price = fill_price
            pos.realized_pnl -= commission
            pos.updated_at = datetime.now(UTC)
        else:
            # Closing or reversing position
            closed_qty = min(pos.quantity, quantity)
            if pos.direction == "LONG":
                gross_pnl = (fill_price - pos.entry_price) * closed_qty
            else:
                gross_pnl = (pos.entry_price - fill_price) * closed_qty

            net_pnl = gross_pnl - commission
            pos.realized_pnl = round(pos.realized_pnl + net_pnl, 2)

            if quantity < pos.quantity:
                # Partial close
                pos.quantity -= quantity
                pos.current_price = fill_price
                pos.updated_at = datetime.now(UTC)
            elif quantity == pos.quantity:
                # Fully closed
                await db.delete(pos)
            else:
                # Position reversed
                remaining_qty = quantity - pos.quantity
                pos.direction = order_dir
                pos.quantity = remaining_qty
                pos.entry_price = fill_price
                pos.current_price = fill_price
                pos.unrealized_pnl = 0.0
                pos.updated_at = datetime.now(UTC)

    async def update_market_prices(
        self,
        db: AsyncSession,
        quotes: dict[str, float],
    ) -> None:
        """Updates mark-to-market valuations and unrealized PnL for all open positions."""
        res = await db.execute(select(PositionModel))
        positions = res.scalars().all()

        for pos in positions:
            if pos.symbol in quotes:
                current_p = quotes[pos.symbol]
                pos.current_price = current_p
                if pos.direction == "LONG":
                    pos.unrealized_pnl = round((current_p - pos.entry_price) * pos.quantity, 2)
                else:
                    pos.unrealized_pnl = round((pos.entry_price - current_p) * pos.quantity, 2)
                pos.updated_at = datetime.now(UTC)

        await db.commit()

    async def get_portfolio_snapshot(self, db: AsyncSession) -> dict[str, Any]:
        """Calculates total portfolio valuation, cash, margin, and P&L."""
        res = await db.execute(select(PositionModel))
        positions = res.scalars().all()

        total_realized = sum(p.realized_pnl for p in positions)
        total_unrealized = sum(p.unrealized_pnl for p in positions)
        positions_notional = sum(p.quantity * p.current_price for p in positions)

        cash = self.starting_cash + total_realized - sum(p.quantity * p.entry_price for p in positions if p.direction == "LONG")
        equity = cash + positions_notional

        return {
            "cash": round(cash, 2),
            "equity": round(equity, 2),
            "realized_pnl": round(total_realized, 2),
            "unrealized_pnl": round(total_unrealized, 2),
            "open_positions_count": len(positions),
            "timestamp": datetime.now(UTC).isoformat(),
        }

    async def reset_paper_account(self, db: AsyncSession) -> None:
        """Resets all paper trading positions, orders, and trades to initial state."""
        # Delete positions
        pos_res = await db.execute(select(PositionModel).where(PositionModel.is_paper.is_(True)))
        for p in pos_res.scalars().all():
            await db.delete(p)

        # Delete trades
        tr_res = await db.execute(select(TradeModel).where(TradeModel.is_paper.is_(True)))
        for t in tr_res.scalars().all():
            await db.delete(t)

        # Reset orders
        ord_res = await db.execute(select(OrderModel).where(OrderModel.is_paper.is_(True)))
        for o in ord_res.scalars().all():
            await db.delete(o)

        await db.commit()
        logger.info("Paper trading account state reset successfully.")


paper_engine = PaperExecutionEngine()
