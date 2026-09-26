"""
MACD (Moving Average Convergence Divergence) Strategy.
Generates BUY when MACD line crosses above the signal line.
Generates SELL when MACD line crosses below the signal line.
"""

from typing import Any

from backend.core.models import OHLCVCandle, SignalDirection, StrategySignal
from backend.indicators.technical import compute_atr, compute_macd
from backend.strategies.base import BaseStrategy


class MacdStrategy(BaseStrategy):
    """MACD Momentum Strategy."""

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        p = params or {}
        super().__init__("MACD", p)
        self.fast_period = int(self.params.get("fast_period", 12))
        self.slow_period = int(self.params.get("slow_period", 26))
        self.signal_period = int(self.params.get("signal_period", 9))
        self.atr_period = int(self.params.get("atr_period", 14))
        self.risk_reward_target = float(self.params.get("risk_reward_target", 2.0))

    @property
    def required_candles(self) -> int:
        return self.slow_period + self.signal_period + 5

    def generate_signals(self, candles: list[OHLCVCandle]) -> list[StrategySignal]:
        self.validate_data(candles)

        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]

        macd_line, signal_line, hist = compute_macd(
            closes, self.fast_period, self.slow_period, self.signal_period
        )
        atr_series = compute_atr(highs, lows, closes, self.atr_period)

        curr_atr = atr_series[-1] or (closes[-1] * 0.01)
        curr_price = closes[-1]
        curr_candle = candles[-1]

        prev_m, prev_s = macd_line[-2], signal_line[-2]
        curr_m, curr_s = macd_line[-1], signal_line[-1]

        if None in (prev_m, prev_s, curr_m, curr_s):
            return []

        signals: list[StrategySignal] = []

        # Bullish MACD Crossover
        if prev_m <= prev_s and curr_m > curr_s:
            sl_distance = max(curr_atr * 1.5, curr_price * 0.005)
            signals.append(
                StrategySignal(
                    symbol=curr_candle.symbol,
                    timeframe=curr_candle.timeframe,
                    direction=SignalDirection.BUY,
                    entry=curr_price,
                    stop_loss=round(curr_price - sl_distance, 2),
                    take_profit=round(curr_price + (sl_distance * self.risk_reward_target), 2),
                    confidence=0.82,
                    strategy=self.name,
                    reasons=[f"MACD line ({curr_m:.2f}) crossed above Signal ({curr_s:.2f})"],
                    timestamp=curr_candle.timestamp,
                    market_regime="MOMENTUM_ACCELERATION",
                )
            )

        # Bearish MACD Crossover
        elif prev_m >= prev_s and curr_m < curr_s:
            sl_distance = max(curr_atr * 1.5, curr_price * 0.005)
            signals.append(
                StrategySignal(
                    symbol=curr_candle.symbol,
                    timeframe=curr_candle.timeframe,
                    direction=SignalDirection.SELL,
                    entry=curr_price,
                    stop_loss=round(curr_price + sl_distance, 2),
                    take_profit=round(curr_price - (sl_distance * self.risk_reward_target), 2),
                    confidence=0.82,
                    strategy=self.name,
                    reasons=[f"MACD line ({curr_m:.2f}) crossed below Signal ({curr_s:.2f})"],
                    timestamp=curr_candle.timestamp,
                    market_regime="MOMENTUM_DECELERATION",
                )
            )

        return signals
