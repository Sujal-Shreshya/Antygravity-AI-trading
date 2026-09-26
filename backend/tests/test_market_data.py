"""
Unit and integration tests for Market Data Subsystem.
Tests market calendar hours, real-time tick-to-candle aggregation, out-of-order rejection,
and market data API endpoints.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.models import MarketType, TimeFrame
from backend.data.aggregator import CandleAggregator, Tick
from backend.data.calendar import MarketCalendar
from backend.data.mock_provider import MockDataProvider
from backend.main import app

IST = ZoneInfo("Asia/Kolkata")


def test_market_calendar_crypto():
    """Verify Crypto markets are open 24/7."""
    assert MarketCalendar.is_market_open(MarketType.CRYPTO_SPOT) is True
    assert MarketCalendar.is_market_open(MarketType.CRYPTO_FUTURES) is True


def test_market_calendar_indian_market_hours():
    """Verify Indian market hours (09:15 to 15:30 IST Mon-Fri)."""
    # Tuesday 11:30 AM IST -> Open
    open_time_ist = datetime(2026, 9, 29, 11, 30, tzinfo=IST)
    open_time_utc = open_time_ist.astimezone(UTC)
    assert MarketCalendar.is_market_open(MarketType.INDIAN_EQUITY, open_time_utc) is True

    # Tuesday 08:30 AM IST -> Closed (pre-market)
    pre_time_ist = datetime(2026, 9, 29, 8, 30, tzinfo=IST)
    assert (
        MarketCalendar.is_market_open(MarketType.INDIAN_EQUITY, pre_time_ist.astimezone(UTC))
        is False
    )

    # Tuesday 16:00 PM IST -> Closed (post-market)
    post_time_ist = datetime(2026, 9, 29, 16, 0, tzinfo=IST)
    assert (
        MarketCalendar.is_market_open(MarketType.INDIAN_EQUITY, post_time_ist.astimezone(UTC))
        is False
    )

    # Sunday 12:00 PM IST -> Closed (weekend)
    weekend_ist = datetime(2026, 9, 27, 12, 0, tzinfo=IST)
    assert (
        MarketCalendar.is_market_open(MarketType.INDIAN_EQUITY, weekend_ist.astimezone(UTC))
        is False
    )


def test_candle_aggregator_tick_flow():
    """Verify ticks correctly update High/Low/Close and trigger candle completion."""
    closed_bars = []

    def on_close(candle):
        closed_bars.append(candle)

    agg = CandleAggregator(timeframe=TimeFrame.M1, on_candle_close=on_close)

    base_time = datetime(2026, 9, 29, 10, 0, 5, tzinfo=UTC)

    # Tick 1: 10:00:05 @ 100.0
    agg.process_tick(Tick(symbol="RELIANCE", price=100.0, volume=10.0, timestamp=base_time))

    # Tick 2: 10:00:20 @ 105.0 (High)
    agg.process_tick(
        Tick(
            symbol="RELIANCE", price=105.0, volume=15.0, timestamp=base_time + timedelta(seconds=15)
        )
    )

    # Tick 3: 10:00:45 @ 98.0 (Low)
    agg.process_tick(
        Tick(
            symbol="RELIANCE", price=98.0, volume=20.0, timestamp=base_time + timedelta(seconds=40)
        )
    )

    # Check incomplete candle
    in_prog = agg.get_current_candle("RELIANCE")
    assert in_prog is not None
    assert in_prog.open == 100.0
    assert in_prog.high == 105.0
    assert in_prog.low == 98.0
    assert in_prog.close == 98.0
    assert in_prog.volume == 45.0
    assert len(closed_bars) == 0

    # Tick 4: 10:01:05 (Next 1-minute bucket) -> triggers closure of 10:00 bucket
    next_bucket_time = base_time + timedelta(seconds=60)
    closed = agg.process_tick(
        Tick(symbol="RELIANCE", price=99.0, volume=5.0, timestamp=next_bucket_time)
    )

    assert closed is not None
    assert len(closed_bars) == 1
    closed_candle = closed_bars[0]
    assert closed_candle.open == 100.0
    assert closed_candle.high == 105.0
    assert closed_candle.low == 98.0
    assert closed_candle.close == 98.0
    assert closed_candle.volume == 45.0


def test_candle_aggregator_out_of_order_protection():
    """Verify that late/out-of-order ticks are rejected safely."""
    agg = CandleAggregator(timeframe=TimeFrame.M1)
    t1 = datetime(2026, 9, 29, 10, 0, 30, tzinfo=UTC)
    t_late = datetime(2026, 9, 29, 10, 0, 10, tzinfo=UTC)

    agg.process_tick(Tick(symbol="INFY", price=1500.0, volume=10.0, timestamp=t1))

    # Stale tick arriving after t1
    result = agg.process_tick(Tick(symbol="INFY", price=1505.0, volume=10.0, timestamp=t_late))
    assert result is None

    # Current bar close remains 1500.0
    current = agg.get_current_candle("INFY")
    assert current is not None
    assert current.close == 1500.0


@pytest.mark.asyncio
async def test_mock_data_provider():
    """Verify mock provider generates valid contiguous OHLCV bars without gap violations."""
    provider = MockDataProvider(base_price=2500.0)
    start = datetime(2026, 9, 29, 9, 15, tzinfo=UTC)
    end = datetime(2026, 9, 29, 11, 15, tzinfo=UTC)

    candles = await provider.get_historical_candles("HDFCBANK", TimeFrame.M5, start, end)
    assert len(candles) > 0
    for c in candles:
        assert c.symbol == "HDFCBANK"
        assert c.high >= c.open
        assert c.high >= c.close
        assert c.low <= c.open
        assert c.low <= c.close
        assert c.volume > 0


@pytest.mark.asyncio
async def test_market_data_api_endpoints():
    """Verify market data API routes."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Market hours status
        hrs_resp = await client.get("/api/v1/market-data/market-hours")
        assert hrs_resp.status_code == 200
        data = hrs_resp.json()
        assert "markets" in data
        assert "CRYPTO_SPOT" in data["markets"]
        assert data["markets"]["CRYPTO_SPOT"] is True

        # 2. Ingest tick
        tick_payload = {
            "symbol": "BTC/USDT",
            "price": 64250.0,
            "volume": 1.25,
            "timestamp": datetime.now(UTC).isoformat(),
            "bid": 64248.0,
            "ask": 64252.0,
        }
        tick_resp = await client.post("/api/v1/market-data/ticks", json=tick_payload)
        assert tick_resp.status_code == 202

        # 3. Query quote for ingested symbol
        quote_resp = await client.get("/api/v1/market-data/quote/BTC/USDT")
        assert quote_resp.status_code == 200
        q = quote_resp.json()
        assert q["symbol"] == "BTC/USDT"
        assert q["price"] == 64250.0
        assert q["is_stale"] is False
