"""
Statistical Mean Reversion Strategy.
Computes price rolling Z-score relative to N-day moving average.
Generates BUY when Z-score < -2.0 (extreme statistical undervaluation).
Generates SELL when Z-score > +2.0 (extreme statistical overvaluation).
"""

import math
from typing import Any

from backend.core.models import OHLCVCandle, SignalDirection, StrategySignal
from backend.indicators.technical import compute_atr, compute_sma
from backend.strategies.base import BaseStrategy


class MeanReversionStrategy(BaseStrategy):
    """Statistical Z-Score Mean Reversion Strategy."""

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        p = params or {}
        super().__init__("MEAN_REVERSION", p)
        self.period = int(self.params.get("period", 20))
        self.z_threshold = float(self.params.get("z_threshold", 2.0))
        self.atr_period = int(self.params.get("atr_period", 14))
        self.risk_reward_target = float(self.params.get("risk_reward_target", 2.0))

    @property
    def required_candles(self) -> int:
        return max(self.period, self.atr_period) + 5

    def generate_signals(self, candles: list[OHLCVCandle]) -> list[StrategySignal]:
        self.validate_data(candles)

        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]

        sma_series = compute_sma(closes, self.period)
        atr_series = compute_atr(highs, lows, closes, self.atr_period)

        curr_atr = atr_series[-1] or (closes[-1] * 0.01)
        curr_price = closes[-1]
        curr_candle = candles[-1]
        curr_sma = sma_series[-1]

        if curr_sma is None:
            return []

        # Calculate standard deviation over the window
        window = closes[-self.period :]
        variance = sum((p - curr_sma) ** 2 for p in window) / self.period
        std_dev = math.sqrt(variance)

        if std_dev <= 1e-9:
            return []

        z_score = (curr_price - curr_sma) / std_dev
        signals: list[StrategySignal] = []

        # Extreme oversold: Z-score < -2.0
        if z_score < -self.z_threshold:
            sl_distance = max(curr_atr * 1.5, curr_price * 0.005)
            signals.append(
                StrategySignal(
                    symbol=curr_candle.symbol,
                    timeframe=curr_candle.timeframe,
                    direction=SignalDirection.BUY,
                    entry=curr_price,
                    stop_loss=round(curr_price - sl_distance, 2),
                    take_profit=round(curr_price + (sl_distance * self.risk_reward_target), 2),
                    confidence=0.81,
                    strategy=self.name,
                    reasons=[
                        f"Z-score ({z_score:.2f}) < -{self.z_threshold} standard deviations from mean"
                    ],
                    timestamp=curr_candle.timestamp,
                    market_regime="STATISTICAL_DISLOCATION",
                )
            )

        # Extreme overbought: Z-score > +2.0
        elif z_score > self.z_threshold:
            sl_distance = max(curr_atr * 1.5, curr_price * 0.005)
            signals.append(
                StrategySignal(
                    symbol=curr_candle.symbol,
                    timeframe=curr_candle.timeframe,
                    direction=SignalDirection.SELL,
                    entry=curr_price,
                    stop_loss=round(curr_price + sl_distance, 2),
                    take_profit=round(curr_price - (sl_distance * self.risk_reward_target), 2),
                    confidence=0.81,
                    strategy=self.name,
                    reasons=[
                        f"Z-score ({z_score:.2f}) > +{self.z_threshold} standard deviations from mean"
                    ],
                    timestamp=curr_candle.timestamp,
                    market_regime="STATISTICAL_DISLOCATION",
                )
            )

        return signals
