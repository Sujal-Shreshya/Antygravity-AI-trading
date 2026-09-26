"""
Market Data API router.
Provides endpoints for querying historical candles, current quotes, and trading session hours.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import TimeFrame
from backend.data.aggregator import Tick
from backend.data.calendar import MarketCalendar
from backend.data.feed_manager import market_data_manager
from backend.database.models import CandleModel
from backend.database.session import get_db

router = APIRouter(prefix="/market-data", tags=["Market Data"])


@router.get("/market-hours", summary="Get market trading session status")
async def get_market_hours() -> dict[str, Any]:
    """Returns the open/closed status across Indian Equities/FNO, Crypto, and Forex."""
    now = datetime.now(UTC)
    status_map = MarketCalendar.get_market_status(now)
    return {
        "timestamp": now.isoformat(),
        "markets": status_map,
    }


@router.get("/quote/{symbol:path}", summary="Get latest quote for a symbol")
async def get_quote(symbol: str) -> dict[str, Any]:
    """Returns latest tick quote and freshness telemetry."""
    quote = market_data_manager.get_latest_quote(symbol)
    if not quote:
        from backend.data.mock_provider import MockDataProvider

        provider = MockDataProvider()
        return await provider.get_latest_quote(symbol)
    return quote


@router.get("/candles", response_model=list[dict[str, Any]], summary="Get OHLCV candles")
async def get_candles(
    symbol: str = Query(..., min_length=1),
    timeframe: TimeFrame = Query(default=TimeFrame.M15),
    limit: int = Query(default=100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """
    Retrieves historical OHLCV bars.
    Queries in-memory cache first, falling back to persistent database records.
    Never fabricates missing prices.
    """
    # Check in-memory ring buffer
    cached = market_data_manager.get_candles(symbol, timeframe, limit=limit)
    if cached:
        return [c.model_dump() for c in cached]

    # Query persistent database
    query = (
        select(CandleModel)
        .where(CandleModel.symbol == symbol, CandleModel.timeframe == timeframe.value)
        .order_by(desc(CandleModel.timestamp))
        .limit(limit)
    )
    result = await db.execute(query)
    rows = result.scalars().all()

    if not rows:
        return []

    # Sort chronologically for client charts
    candles = sorted(
        [
            {
                "symbol": r.symbol,
                "timeframe": r.timeframe,
                "timestamp": r.timestamp.isoformat(),
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
                "trades_count": r.trades_count,
            }
            for r in rows
        ],
        key=lambda x: x["timestamp"],
    )
    return candles


@router.post("/ticks", status_code=status.HTTP_202_ACCEPTED, summary="Ingest real-time tick")
async def ingest_tick(tick: Tick) -> dict[str, str]:
    """Ingests a real-time price tick into the aggregator and feeds."""
    market_data_manager.on_tick(tick)
    return {"status": "accepted", "symbol": tick.symbol}
