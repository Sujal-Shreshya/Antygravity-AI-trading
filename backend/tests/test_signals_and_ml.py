"""
Unit and integration tests for Signals Aggregation and Market Regime Classification.
Verifies multi-strategy consensus voting, conflict resolution, regime feature extraction,
and signals API endpoints.
"""

from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.models import SignalDirection, StrategySignal, TimeFrame
from backend.data.mock_provider import MockDataProvider
from backend.main import app
from backend.signals.aggregator import SignalAggregator
from backend.signals.regime_classifier import MarketRegime, MarketRegimeClassifier


def test_market_regime_classification_properties():
    """Verify feature extraction and regime prediction without look-ahead bias."""
    provider = MockDataProvider(base_price=2000.0)
    start = datetime(2026, 9, 29, 9, 15, tzinfo=UTC)
    end = datetime(2026, 9, 29, 14, 0, tzinfo=UTC)

    # Generate synthetic bars
    import asyncio

    candles = asyncio.run(provider.get_historical_candles("TCS", TimeFrame.M5, start, end))
    assert len(candles) >= 50

    features = MarketRegimeClassifier.extract_features(candles)
    assert features is not None
    assert features.rsi >= 0.0 and features.rsi <= 100.0
    assert features.atr_pct > 0.0
    assert features.bb_bandwidth > 0.0
    assert features.volume_ratio >= 0.0

    regime, confidence = MarketRegimeClassifier.classify_regime(candles)
    assert regime in MarketRegime
    assert 0.0 <= confidence <= 1.0


def test_signal_aggregator_consensus_and_conflict():
    """Verify multi-strategy voting and conflict resolution into HOLD."""
    aggregator = SignalAggregator(min_confidence=0.70)
    t = datetime.now(UTC)

    # 1. Consensus BUY (Both EMA and MACD bullish)
    sig1 = StrategySignal(
        symbol="RELIANCE",
        timeframe=TimeFrame.M15,
        direction=SignalDirection.BUY,
        entry=2800.0,
        stop_loss=2780.0,
        take_profit=2850.0,
        confidence=0.85,
        strategy="EMA_CROSSOVER",
        reasons=["EMA golden cross"],
        timestamp=t,
    )
    sig2 = StrategySignal(
        symbol="RELIANCE",
        timeframe=TimeFrame.M15,
        direction=SignalDirection.BUY,
        entry=2800.0,
        stop_loss=2775.0,
        take_profit=2860.0,
        confidence=0.80,
        strategy="MACD",
        reasons=["MACD bullish crossover"],
        timestamp=t,
    )

    agg = aggregator.aggregate([sig1, sig2], regime=MarketRegime.BULLISH_TREND)
    assert agg is not None
    assert agg.direction == SignalDirection.BUY
    assert agg.is_actionable is True
    assert agg.confidence >= 0.80
    assert agg.stop_loss == 2780.0  # Most conservative SL
    assert "EMA_CROSSOVER" in agg.participating_strategies
    assert "MACD" in agg.participating_strategies

    # 2. Conflicting Signals: One strong BUY, one strong SELL
    sig_bear = StrategySignal(
        symbol="RELIANCE",
        timeframe=TimeFrame.M15,
        direction=SignalDirection.SELL,
        entry=2800.0,
        stop_loss=2820.0,
        take_profit=2750.0,
        confidence=0.85,
        strategy="RSI",
        reasons=["RSI overbought exhaustion"],
        timestamp=t,
    )

    conflict_agg = aggregator.aggregate([sig1, sig_bear], regime=MarketRegime.RANGE_BOUND)
    assert conflict_agg is not None
    assert conflict_agg.direction == SignalDirection.HOLD
    assert conflict_agg.is_actionable is False
    assert any("Conflicting" in r for r in conflict_agg.reasons)


@pytest.mark.asyncio
async def test_signals_api_workflow():
    """Verify signals evaluation, regime detection, and retrieval endpoints."""
    provider = MockDataProvider(base_price=3000.0)
    start = datetime(2026, 9, 29, 9, 15, tzinfo=UTC)
    end = datetime(2026, 9, 29, 14, 15, tzinfo=UTC)
    candles = await provider.get_historical_candles("INFY", TimeFrame.M5, start, end)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Regime endpoint
        regime_resp = await client.post(
            "/api/v1/signals/regime",
            json=[c.model_dump(mode="json") for c in candles],
        )
        assert regime_resp.status_code == 200
        reg_data = regime_resp.json()
        assert "regime" in reg_data
        assert "confidence" in reg_data

        # 2. Multi-strategy consensus evaluate endpoint
        eval_payload = {
            "candles": [c.model_dump(mode="json") for c in candles],
            "enabled_strategies": ["EMA_CROSSOVER", "MACD", "RSI", "TREND_FOLLOWING"],
        }
        eval_resp = await client.post("/api/v1/signals/evaluate", json=eval_payload)
        assert eval_resp.status_code == 200
        sig_data = eval_resp.json()
        assert sig_data["symbol"] == "INFY"
        assert sig_data["direction"] in ("BUY", "SELL", "HOLD")

        # 3. Query persisted signals from database
        list_resp = await client.get("/api/v1/signals?symbol=INFY")
        assert list_resp.status_code == 200
        persisted = list_resp.json()
        assert isinstance(persisted, list)
