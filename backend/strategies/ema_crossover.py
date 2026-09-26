"""
EMA Crossover Strategy.
Generates BUY signal when Fast EMA crosses above Slow EMA.
Generates SELL signal when Fast EMA crosses below Slow EMA.
Dynamic Stop Loss and Take Profit calculated using Average True Range (ATR).
"""

from typing import Any

from backend.core.models import OHLCVCandle, SignalDirection, StrategySignal
from backend.indicators.technical import compute_atr, compute_ema
from backend.strategies.base import BaseStrategy


class EmaCrossoverStrategy(BaseStrategy):
    """Exponential Moving Average Crossover Strategy."""

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        p = params or {}
        super().__init__("EMA_CROSSOVER", p)
        self.fast_period = int(self.params.get("fast_period", 9))
        self.slow_period = int(self.params.get("slow_period", 21))
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

        fast_ema = compute_ema(closes, self.fast_period)
        slow_ema = compute_ema(closes, self.slow_period)
        atr_series = compute_atr(highs, lows, closes, self.atr_period)

        curr_atr = atr_series[-1] or (closes[-1] * 0.01)
        curr_price = closes[-1]
        curr_candle = candles[-1]

        prev_fast = fast_ema[-2]
        prev_slow = slow_ema[-2]
        curr_fast = fast_ema[-1]
        curr_slow = slow_ema[-1]

        if None in (prev_fast, prev_slow, curr_fast, curr_slow):
            return []

        signals: list[StrategySignal] = []

        # Bullish Crossover (Fast crosses above Slow)
        if prev_fast <= prev_slow and curr_fast > curr_slow:
            sl_distance = max(curr_atr * 1.5, curr_price * 0.005)
            stop_loss = round(curr_price - sl_distance, 2)
            take_profit = round(curr_price + (sl_distance * self.risk_reward_target), 2)

            signals.append(
                StrategySignal(
                    symbol=curr_candle.symbol,
                    timeframe=curr_candle.timeframe,
                    direction=SignalDirection.BUY,
                    entry=curr_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    confidence=0.80,
                    strategy=self.name,
                    reasons=[
                        f"Fast EMA({self.fast_period}) crossed above Slow EMA({self.slow_period})",
                        f"ATR volatility: {curr_atr:.2f}",
                    ],
                    timestamp=curr_candle.timestamp,
                    market_regime="BULLISH_TREND",
                )
            )

        # Bearish Crossover (Fast crosses below Slow)
        elif prev_fast >= prev_slow and curr_fast < curr_slow:
            sl_distance = max(curr_atr * 1.5, curr_price * 0.005)
            stop_loss = round(curr_price + sl_distance, 2)
            take_profit = round(curr_price - (sl_distance * self.risk_reward_target), 2)

            signals.append(
                StrategySignal(
                    symbol=curr_candle.symbol,
                    timeframe=curr_candle.timeframe,
                    direction=SignalDirection.SELL,
                    entry=curr_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    confidence=0.80,
                    strategy=self.name,
                    reasons=[
                        f"Fast EMA({self.fast_period}) crossed below Slow EMA({self.slow_period})",
                        f"ATR volatility: {curr_atr:.2f}",
                    ],
                    timestamp=curr_candle.timestamp,
                    market_regime="BEARISH_TREND",
                )
            )

        return signals
