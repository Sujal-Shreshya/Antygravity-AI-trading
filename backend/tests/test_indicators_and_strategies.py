"""
Unit and integration tests for Technical Indicators and Algorithmic Strategy Engine.
Verifies all 10 baseline strategies, mathematical indicators, and strategy API endpoints.
"""

from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.models import SignalDirection, StrategySignal, TimeFrame
from backend.data.mock_provider import MockDataProvider
from backend.indicators.technical import (
    compute_bollinger_bands,
    compute_ema,
    compute_rsi,
    compute_sma,
)
from backend.main import app
from backend.strategies.registry import STRATEGY_CATALOG, strategy_registry


def test_indicators_mathematical_properties():
    """Verify indicator mathematical validity and boundary constraints."""
    prices = [
        10.0,
        11.0,
        12.0,
        11.0,
        10.0,
        9.0,
        10.0,
        11.0,
        12.0,
        13.0,
        14.0,
        15.0,
        14.0,
        13.0,
        12.0,
    ]

    # SMA
    sma = compute_sma(prices, 5)
    assert len(sma) == len(prices)
    assert sma[4] == 10.8  # (10+11+12+11+10)/5 = 54/5 = 10.8

    # EMA
    ema = compute_ema(prices, 5)
    assert len(ema) == len(prices)
    assert ema[4] == 10.8

    # RSI
    rsi_prices = [
        44.0,
        44.25,
        44.5,
        43.75,
        44.0,
        44.5,
        44.25,
        44.75,
        45.0,
        45.5,
        45.25,
        46.0,
        46.5,
        46.25,
        46.75,
        47.0,
    ]
    rsi = compute_rsi(rsi_prices, 14)
    assert len(rsi) == len(rsi_prices)
    for val in rsi:
        if val is not None:
            assert 0.0 <= val <= 100.0

    # Bollinger Bands
    upper, mid, lower = compute_bollinger_bands(prices, period=5, num_std_dev=2.0)
    for u, m, lower_val in zip(upper, mid, lower, strict=True):
        if None not in (u, m, lower_val):
            assert u >= m
            assert m >= lower_val


@pytest.mark.asyncio
async def test_all_10_strategies_execution():
    """Verify all 10 baseline strategies execute cleanly and emit valid StrategySignals."""
    provider = MockDataProvider(base_price=1000.0)
    start = datetime(2026, 9, 29, 9, 15, tzinfo=UTC)
    end = datetime(2026, 9, 29, 15, 30, tzinfo=UTC)

    candles = await provider.get_historical_candles("NIFTY", TimeFrame.M5, start, end)
    assert len(candles) >= 70

    # Ensure all 10 strategies exist in catalog
    assert len(STRATEGY_CATALOG) == 10
    strategy_keys = [
        "EMA_CROSSOVER",
        "SMA_CROSSOVER",
        "RSI",
        "MACD",
        "BOLLINGER_BANDS",
        "VWAP",
        "BREAKOUT",
        "MOMENTUM",
        "TREND_FOLLOWING",
        "MEAN_REVERSION",
    ]

    for key in strategy_keys:
        strat = strategy_registry.get_strategy(key)
        assert strat.name == key
        assert strat.required_candles > 0

        # Run signal generation
        signals = strat.generate_signals(candles)
        assert isinstance(signals, list)

        # Validate any emitted signals against trading invariants
        for sig in signals:
            assert isinstance(sig, StrategySignal)
            assert sig.symbol == "NIFTY"
            assert sig.confidence >= 0.0
            assert sig.risk_reward_ratio >= 1.5

            if sig.direction == SignalDirection.BUY:
                assert sig.stop_loss < sig.entry < sig.take_profit
            elif sig.direction == SignalDirection.SELL:
                assert sig.take_profit < sig.entry < sig.stop_loss


@pytest.mark.asyncio
async def test_strategies_api_endpoints():
    """Verify strategy catalog and evaluation API routes."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. List strategies
        list_resp = await client.get("/api/v1/strategies")
        assert list_resp.status_code == 200
        catalog = list_resp.json()
        assert len(catalog) == 10
        strategy_ids = [s["id"] for s in catalog]
        assert "EMA_CROSSOVER" in strategy_ids
        assert "TREND_FOLLOWING" in strategy_ids

        # 2. Get single strategy
        item_resp = await client.get("/api/v1/strategies/EMA_CROSSOVER")
        assert item_resp.status_code == 200
        assert item_resp.json()["id"] == "EMA_CROSSOVER"

        # 3. Evaluate strategy via API
        provider = MockDataProvider(base_price=500.0)
        start = datetime(2026, 9, 29, 9, 15, tzinfo=UTC)
        end = datetime(2026, 9, 29, 13, 15, tzinfo=UTC)
        candles = await provider.get_historical_candles("SBIN", TimeFrame.M5, start, end)

        eval_payload = {
            "candles": [c.model_dump(mode="json") for c in candles],
            "parameters": {"fast_period": 5, "slow_period": 15},
        }
        eval_resp = await client.post(
            "/api/v1/strategies/EMA_CROSSOVER/evaluate", json=eval_payload
        )
        assert eval_resp.status_code == 200
        signals = eval_resp.json()
        assert isinstance(signals, list)
