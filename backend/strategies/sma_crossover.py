"""
SMA Crossover (Golden / Death Cross) Strategy.
Generates BUY signal when Fast SMA crosses above Slow SMA.
Generates SELL signal when Fast SMA crosses below Slow SMA.
"""

from typing import Any

from backend.core.models import OHLCVCandle, SignalDirection, StrategySignal
from backend.indicators.technical import compute_atr, compute_sma
from backend.strategies.base import BaseStrategy


class SmaCrossoverStrategy(BaseStrategy):
    """Simple Moving Average Crossover Strategy."""

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        p = params or {}
        super().__init__("SMA_CROSSOVER", p)
        self.fast_period = int(self.params.get("fast_period", 20))
        self.slow_period = int(self.params.get("slow_period", 50))
        self.atr_period = int(self.params.get("atr_period", 14))
        self.risk_reward_target = float(self.params.get("risk_reward_target", 2.0))

    @property
    def required_candles(self) -> int:
        return max(self.slow_period, self.atr_period) + 5

    def generate_signals(self, candles: list[OHLCVCandle]) -> list[StrategySignal]:
        self.validate_data(candles)

        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]

        fast_sma = compute_sma(closes, self.fast_period)
        slow_sma = compute_sma(closes, self.slow_period)
        atr_series = compute_atr(highs, lows, closes, self.atr_period)

        curr_atr = atr_series[-1] or (closes[-1] * 0.01)
        curr_price = closes[-1]
        curr_candle = candles[-1]

        prev_fast = fast_sma[-2]
        prev_slow = slow_sma[-2]
        curr_fast = fast_sma[-1]
        curr_slow = slow_sma[-1]

        if None in (prev_fast, prev_slow, curr_fast, curr_slow):
            return []

        signals: list[StrategySignal] = []

        if prev_fast <= prev_slow and curr_fast > curr_slow:
            sl_distance = max(curr_atr * 1.5, curr_price * 0.005)
            signals.append(
                StrategySignal(
                    symbol=curr_candle.symbol,
                    timeframe=curr_candle.timeframe,
                    direction=SignalDirection.BUY,
                    entry=curr_price,
                    stop_loss=round(curr_price - sl_distance, 2),
                    take_profit=round(curr_price + (sl_distance * self.risk_reward_target), 2),
                    confidence=0.75,
                    strategy=self.name,
                    reasons=[f"SMA({self.fast_period}) Golden Cross over SMA({self.slow_period})"],
                    timestamp=curr_candle.timestamp,
                    market_regime="BULLISH_TREND",
                )
            )
        elif prev_fast >= prev_slow and curr_fast < curr_slow:
            sl_distance = max(curr_atr * 1.5, curr_price * 0.005)
            signals.append(
                StrategySignal(
                    symbol=curr_candle.symbol,
                    timeframe=curr_candle.timeframe,
                    direction=SignalDirection.SELL,
                    entry=curr_price,
                    stop_loss=round(curr_price + sl_distance, 2),
                    take_profit=round(curr_price - (sl_distance * self.risk_reward_target), 2),
                    confidence=0.75,
                    strategy=self.name,
                    reasons=[f"SMA({self.fast_period}) Death Cross under SMA({self.slow_period})"],
                    timestamp=curr_candle.timestamp,
                    market_regime="BEARISH_TREND",
                )
            )

        return signals
