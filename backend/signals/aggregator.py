"""
Multi-Strategy Signal Aggregator and Consensus Engine.
Combines signals from individual strategies, resolves directional conflicts,
applies regime weighting, and emits consolidated actionable trade proposals.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from backend.core.models import SignalDirection, StrategySignal, TimeFrame
from backend.signals.regime_classifier import MarketRegime


class AggregatedSignal(BaseModel):
    """Consolidated actionable signal after multi-strategy voting and regime calibration."""

    symbol: str
    timeframe: TimeFrame
    direction: SignalDirection
    entry: float
    stop_loss: float
    take_profit: float
    confidence: float = Field(..., ge=0.0, le=1.0)
    risk_reward_ratio: float
    market_regime: MarketRegime
    participating_strategies: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_actionable: bool = False


# Strategy compatibility bonus per market regime
REGIME_STRATEGY_WEIGHTS: dict[MarketRegime, dict[str, float]] = {
    MarketRegime.BULLISH_TREND: {
        "EMA_CROSSOVER": 1.4,
        "SMA_CROSSOVER": 1.4,
        "TREND_FOLLOWING": 1.6,
        "MOMENTUM": 1.3,
        "BREAKOUT": 1.2,
        "RSI": 0.8,
        "MEAN_REVERSION": 0.7,
    },
    MarketRegime.BEARISH_TREND: {
        "EMA_CROSSOVER": 1.4,
        "SMA_CROSSOVER": 1.4,
        "TREND_FOLLOWING": 1.6,
        "MOMENTUM": 1.3,
        "BREAKOUT": 1.2,
        "RSI": 0.8,
        "MEAN_REVERSION": 0.7,
    },
    MarketRegime.RANGE_BOUND: {
        "MEAN_REVERSION": 1.6,
        "BOLLINGER_BANDS": 1.5,
        "RSI": 1.4,
        "VWAP": 1.3,
        "TREND_FOLLOWING": 0.6,
        "BREAKOUT": 0.6,
    },
    MarketRegime.HIGH_VOLATILITY: {
        "BREAKOUT": 1.5,
        "MOMENTUM": 1.4,
        "TREND_FOLLOWING": 1.2,
        "MEAN_REVERSION": 0.5,
    },
    MarketRegime.COMPRESSION: {
        "BREAKOUT": 1.6,
        "BOLLINGER_BANDS": 1.4,
        "TREND_FOLLOWING": 0.7,
    },
}


class SignalAggregator:
    """Consolidates strategy outputs into an actionable, calibrated signal."""

    def __init__(self, min_confidence: float = 0.70) -> None:
        self.min_confidence = min_confidence

    def aggregate(
        self,
        signals: list[StrategySignal],
        regime: MarketRegime = MarketRegime.RANGE_BOUND,
    ) -> AggregatedSignal | None:
        """
        Consolidates candidate strategy signals for a single symbol and timeframe.
        Returns AggregatedSignal or None if no input signals provided.
        """
        if not signals:
            return None

        symbol = signals[0].symbol
        timeframe = signals[0].timeframe
        entry = signals[-1].entry  # Latest price

        weights_map = REGIME_STRATEGY_WEIGHTS.get(regime, {})

        buy_weight = 0.0
        sell_weight = 0.0
        buy_strategies: list[str] = []
        sell_strategies: list[str] = []
        all_reasons: list[str] = []

        buy_sl_candidates: list[float] = []
        buy_tp_candidates: list[float] = []
        sell_sl_candidates: list[float] = []
        sell_tp_candidates: list[float] = []

        for sig in signals:
            multiplier = weights_map.get(sig.strategy, 1.0)
            weighted_conf = sig.confidence * multiplier
            all_reasons.extend(sig.reasons)

            if sig.direction == SignalDirection.BUY:
                buy_weight += weighted_conf
                buy_strategies.append(sig.strategy)
                buy_sl_candidates.append(sig.stop_loss)
                buy_tp_candidates.append(sig.take_profit)
            elif sig.direction == SignalDirection.SELL:
                sell_weight += weighted_conf
                sell_strategies.append(sig.strategy)
                sell_sl_candidates.append(sig.stop_loss)
                sell_tp_candidates.append(sig.take_profit)

        # Directional Consensus Evaluation
        direction = SignalDirection.HOLD
        confidence = 0.5
        stop_loss = round(entry * 0.98, 2)
        take_profit = round(entry * 1.04, 2)
        participating: list[str] = []

        # Conflict resolution: if both BUY and SELL have significant support
        if (
            buy_weight > 0
            and sell_weight > 0
            and min(buy_weight, sell_weight) / max(buy_weight, sell_weight) > 0.4
        ):
            direction = SignalDirection.HOLD
            confidence = 0.40
            all_reasons.append(
                f"Conflicting signals detected (BUY weight: {buy_weight:.2f}, SELL weight: {sell_weight:.2f}). Resolving to HOLD."
            )
            participating = buy_strategies + sell_strategies

        elif buy_weight > sell_weight and buy_weight >= 0.7:
            direction = SignalDirection.BUY
            confidence = min(0.95, buy_weight / (len(buy_strategies) + 0.5))
            # Most conservative stop loss (closest to entry but below entry)
            stop_loss = max(buy_sl_candidates)
            take_profit = sum(buy_tp_candidates) / len(buy_tp_candidates)
            participating = buy_strategies

        elif sell_weight > buy_weight and sell_weight >= 0.7:
            direction = SignalDirection.SELL
            confidence = min(0.95, sell_weight / (len(sell_strategies) + 0.5))
            # Most conservative stop loss (closest to entry but above entry)
            stop_loss = min(sell_sl_candidates)
            take_profit = sum(sell_tp_candidates) / len(sell_tp_candidates)
            participating = sell_strategies

        # Calculate RR ratio
        risk = abs(entry - stop_loss)
        reward = abs(take_profit - entry)
        rr_ratio = round(reward / risk, 2) if risk > 1e-9 else 0.0

        is_actionable = (
            direction in (SignalDirection.BUY, SignalDirection.SELL)
            and confidence >= self.min_confidence
            and rr_ratio >= 1.5
        )

        return AggregatedSignal(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            entry=entry,
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            confidence=round(confidence, 2),
            risk_reward_ratio=rr_ratio,
            market_regime=regime,
            participating_strategies=participating,
            reasons=all_reasons[:5],  # top 5 reasons
            is_actionable=is_actionable,
        )


signal_aggregator = SignalAggregator()
