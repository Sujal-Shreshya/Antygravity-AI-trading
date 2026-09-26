"""
Breakout Strategy.
Generates BUY when current price breaks above the N-bar highest high (Donchian channel).
Generates SELL when current price breaks below the N-bar lowest low.
"""

from typing import Any

from backend.core.models import OHLCVCandle, SignalDirection, StrategySignal
from backend.indicators.technical import compute_atr, compute_donchian_breakout
from backend.strategies.base import BaseStrategy


class BreakoutStrategy(BaseStrategy):
    """Donchian Range Breakout Strategy."""

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        p = params or {}
        super().__init__("BREAKOUT", p)
        self.period = int(self.params.get("period", 20))
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

        upper, lower = compute_donchian_breakout(highs, lows, self.period)
        atr_series = compute_atr(highs, lows, closes, self.atr_period)

        curr_atr = atr_series[-1] or (closes[-1] * 0.01)
        curr_price = closes[-1]
        curr_candle = candles[-1]

        prev_upper = upper[-1]  # Highest high of lookback period excluding current
        prev_lower = lower[-1]

        if None in (prev_upper, prev_lower):
            return []

        signals: list[StrategySignal] = []

        # Bullish Breakout above recent channel
        if curr_price > prev_upper:
            sl_distance = max(curr_atr * 1.5, curr_price * 0.005)
            signals.append(
                StrategySignal(
                    symbol=curr_candle.symbol,
                    timeframe=curr_candle.timeframe,
                    direction=SignalDirection.BUY,
                    entry=curr_price,
                    stop_loss=round(curr_price - sl_distance, 2),
                    take_profit=round(curr_price + (sl_distance * self.risk_reward_target), 2),
                    confidence=0.84,
                    strategy=self.name,
                    reasons=[
                        f"Price ({curr_price:.2f}) broke above {self.period}-bar high ({prev_upper:.2f})"
                    ],
                    timestamp=curr_candle.timestamp,
                    market_regime="VOLATILITY_EXPANSION",
                )
            )

        # Bearish Breakdown below recent channel
        elif curr_price < prev_lower:
            sl_distance = max(curr_atr * 1.5, curr_price * 0.005)
            signals.append(
                StrategySignal(
                    symbol=curr_candle.symbol,
                    timeframe=curr_candle.timeframe,
                    direction=SignalDirection.SELL,
                    entry=curr_price,
                    stop_loss=round(curr_price + sl_distance, 2),
                    take_profit=round(curr_price - (sl_distance * self.risk_reward_target), 2),
                    confidence=0.84,
                    strategy=self.name,
                    reasons=[
                        f"Price ({curr_price:.2f}) broke below {self.period}-bar low ({prev_lower:.2f})"
                    ],
                    timestamp=curr_candle.timestamp,
                    market_regime="VOLATILITY_EXPANSION",
                )
            )

        return signals
