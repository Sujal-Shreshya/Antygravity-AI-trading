"""
RSI (Relative Strength Index) Strategy.
Generates BUY signal when RSI exits oversold territory (< 30 rising back above 30).
Generates SELL signal when RSI exits overbought territory (> 70 falling back below 70).
"""

from typing import Any

from backend.core.models import OHLCVCandle, SignalDirection, StrategySignal
from backend.indicators.technical import compute_atr, compute_rsi
from backend.strategies.base import BaseStrategy


class RsiStrategy(BaseStrategy):
    """RSI Mean-Reversion Strategy."""

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        p = params or {}
        super().__init__("RSI", p)
        self.period = int(self.params.get("period", 14))
        self.oversold = float(self.params.get("oversold", 30.0))
        self.overbought = float(self.params.get("overbought", 70.0))
        self.atr_period = int(self.params.get("atr_period", 14))
        self.risk_reward_target = float(self.params.get("risk_reward_target", 2.0))

    @property
    def required_candles(self) -> int:
        return max(self.period, self.atr_period) + 10

    def generate_signals(self, candles: list[OHLCVCandle]) -> list[StrategySignal]:
        self.validate_data(candles)

        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]

        rsi_series = compute_rsi(closes, self.period)
        atr_series = compute_atr(highs, lows, closes, self.atr_period)

        curr_atr = atr_series[-1] or (closes[-1] * 0.01)
        curr_price = closes[-1]
        curr_candle = candles[-1]

        prev_rsi = rsi_series[-2]
        curr_rsi = rsi_series[-1]

        if prev_rsi is None or curr_rsi is None:
            return []

        signals: list[StrategySignal] = []

        # RSI crossing out of oversold
        if prev_rsi <= self.oversold and curr_rsi > self.oversold:
            sl_distance = max(curr_atr * 1.5, curr_price * 0.005)
            signals.append(
                StrategySignal(
                    symbol=curr_candle.symbol,
                    timeframe=curr_candle.timeframe,
                    direction=SignalDirection.BUY,
                    entry=curr_price,
                    stop_loss=round(curr_price - sl_distance, 2),
                    take_profit=round(curr_price + (sl_distance * self.risk_reward_target), 2),
                    confidence=0.78,
                    strategy=self.name,
                    reasons=[
                        f"RSI({self.period}) rebounded above oversold ({curr_rsi:.1f} > {self.oversold})"
                    ],
                    timestamp=curr_candle.timestamp,
                    market_regime="OVERSOLD_REVERSAL",
                )
            )

        # RSI crossing out of overbought
        elif prev_rsi >= self.overbought and curr_rsi < self.overbought:
            sl_distance = max(curr_atr * 1.5, curr_price * 0.005)
            signals.append(
                StrategySignal(
                    symbol=curr_candle.symbol,
                    timeframe=curr_candle.timeframe,
                    direction=SignalDirection.SELL,
                    entry=curr_price,
                    stop_loss=round(curr_price + sl_distance, 2),
                    take_profit=round(curr_price - (sl_distance * self.risk_reward_target), 2),
                    confidence=0.78,
                    strategy=self.name,
                    reasons=[
                        f"RSI({self.period}) dropped below overbought ({curr_rsi:.1f} < {self.overbought})"
                    ],
                    timestamp=curr_candle.timestamp,
                    market_regime="OVERBOUGHT_REVERSAL",
                )
            )

        return signals
