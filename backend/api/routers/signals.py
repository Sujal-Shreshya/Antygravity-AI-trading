"""
Signals API router.
Provides endpoints for querying historical signals, evaluating multi-strategy signals,
and classifying live market regimes.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models import OHLCVCandle, SignalDirection, StrategySignal
from backend.database.models import SignalModel
from backend.database.session import get_db
from backend.signals.aggregator import AggregatedSignal, signal_aggregator
from backend.signals.regime_classifier import MarketRegimeClassifier
from backend.strategies.registry import STRATEGY_CATALOG, strategy_registry

router = APIRouter(prefix="/signals", tags=["Signals & AI Layer"])


class EvaluateSignalsRequest(BaseModel):
    candles: list[OHLCVCandle] = Field(..., min_length=30)
    enabled_strategies: list[str] | None = None


@router.get("", summary="List recent generated signals")
async def list_signals(
    symbol: str | None = None,
    direction: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Returns audit trail of past strategy signals stored in database."""
    query = select(SignalModel).order_by(desc(SignalModel.created_at)).limit(limit)
    if symbol:
        query = query.where(SignalModel.symbol == symbol)
    if direction:
        query = query.where(SignalModel.direction == direction)

    result = await db.execute(query)
    signals = result.scalars().all()
    return [
        {
            "id": s.id,
            "symbol": s.symbol,
            "timeframe": s.timeframe,
            "direction": s.direction,
            "entry": s.entry,
            "stop_loss": s.stop_loss,
            "take_profit": s.take_profit,
            "confidence": s.confidence,
            "strategy_id": s.strategy_id,
            "reasons": s.reasons,
            "market_regime": s.market_regime,
            "created_at": s.created_at.isoformat(),
        }
        for s in signals
    ]


@router.post("/regime", summary="Classify market regime from candles")
async def get_market_regime(candles: list[OHLCVCandle]) -> dict[str, Any]:
    """Extracts features and predicts the current market regime without forward bias."""
    if len(candles) < 30:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Regime classification requires at least 30 historical candles.",
        )
    regime, confidence = MarketRegimeClassifier.classify_regime(candles)
    features = MarketRegimeClassifier.extract_features(candles)
    return {
        "symbol": candles[-1].symbol,
        "regime": regime.value,
        "confidence": round(confidence, 2),
        "features": features.model_dump() if features else None,
        "as_of": candles[-1].timestamp.isoformat(),
    }


@router.post(
    "/evaluate", response_model=AggregatedSignal, summary="Evaluate multi-strategy consensus"
)
async def evaluate_signals(
    payload: EvaluateSignalsRequest,
    db: AsyncSession = Depends(get_db),
) -> AggregatedSignal:
    """
    Evaluates enabled strategies on supplied candles, detects market regime,
    performs multi-strategy consensus, persists raw signals, and returns an actionable decision.
    """
    candles = payload.candles
    strat_keys = payload.enabled_strategies or list(STRATEGY_CATALOG.keys())

    # 1. Classify regime
    regime, _ = MarketRegimeClassifier.classify_regime(candles)

    # 2. Run all enabled strategies
    candidate_signals: list[StrategySignal] = []
    for key in strat_keys:
        try:
            strat = strategy_registry.get_strategy(key)
            if len(candles) >= strat.required_candles:
                sigs = strat.generate_signals(candles)
                candidate_signals.extend(sigs)
        except Exception:
            continue

    # 3. Aggregate into consensus
    aggregated = signal_aggregator.aggregate(candidate_signals, regime)
    if not aggregated:
        # Fallback neutral HOLD
        last_candle = candles[-1]
        aggregated = AggregatedSignal(
            symbol=last_candle.symbol,
            timeframe=last_candle.timeframe,
            direction=SignalDirection.HOLD,
            entry=last_candle.close,
            stop_loss=round(last_candle.close * 0.98, 2),
            take_profit=round(last_candle.close * 1.04, 2),
            confidence=0.50,
            risk_reward_ratio=2.0,
            market_regime=regime,
            participating_strategies=[],
            reasons=["No strategy generated a high-confidence signal."],
            is_actionable=False,
        )

    # 4. Persist raw strategy signals to DB for audit
    for s in candidate_signals:
        sig_model = SignalModel(
            symbol=s.symbol,
            timeframe=s.timeframe.value,
            direction=s.direction.value,
            entry=s.entry,
            stop_loss=s.stop_loss,
            take_profit=s.take_profit,
            confidence=s.confidence,
            strategy_id=s.strategy,
            reasons=s.reasons,
            market_regime=regime.value,
        )
        db.add(sig_model)

    await db.commit()
    return aggregated


@router.get("/consensus", summary="Get live multi-strategy consensus signal")
async def get_live_consensus(
    symbol: str = "RELIANCE",
    timeframe: str = "15m",
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Computes real-time multi-strategy consensus for a given symbol and timeframe."""
    from backend.data.mock_provider import MockDataProvider

    provider = MockDataProvider()
    candles = await provider.fetch_historical_candles(symbol, timeframe, limit=60)

    payload = EvaluateSignalsRequest(candles=candles)
    aggregated = await evaluate_signals(payload, db)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "consensus_direction": aggregated.direction.value,
        "entry": aggregated.entry,
        "stop_loss": aggregated.stop_loss,
        "take_profit": aggregated.take_profit,
        "overall_confidence": aggregated.confidence,
        "risk_reward_ratio": aggregated.risk_reward_ratio,
        "market_regime": aggregated.market_regime.value if aggregated.market_regime else None,
        "participating_strategies": aggregated.participating_strategies,
        "reasons": aggregated.reasons,
        "is_actionable": aggregated.is_actionable,
    }


@router.get("/regime", summary="Get current market regime for a symbol")
async def get_live_market_regime(
    symbol: str = "RELIANCE",
    timeframe: str = "15m",
) -> dict[str, Any]:
    """Classifies current market regime for a symbol without forward lookahead bias."""
    from backend.data.mock_provider import MockDataProvider

    provider = MockDataProvider()
    candles = await provider.fetch_historical_candles(symbol, timeframe, limit=60)
    return await get_market_regime(candles)

