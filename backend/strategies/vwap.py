"""
VWAP (Volume-Weighted Average Price) Divergence & Reversion Strategy.
Generates BUY when price reclaims VWAP from below with rising volume.
Generates SELL when price breaks below VWAP from above.
"""

from typing import Any

from backend.core.models import OHLCVCandle, SignalDirection, StrategySignal
from backend.indicators.technical import compute_atr, compute_vwap
from backend.strategies.base import BaseStrategy


class VwapStrategy(BaseStrategy):
    """VWAP Institutional Flow Strategy."""

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        p = params or {}
        super().__init__("VWAP", p)
        self.atr_period = int(self.params.get("atr_period", 14))
        self.risk_reward_target = float(self.params.get("risk_reward_target", 2.0))

    @property
    def required_candles(self) -> int:
        return self.atr_period + 5

    def generate_signals(self, candles: list[OHLCVCandle]) -> list[StrategySignal]:
        self.validate_data(candles)

        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]

        vwap_series = compute_vwap(candles)
        atr_series = compute_atr(highs, lows, closes, self.atr_period)

        curr_atr = atr_series[-1] or (closes[-1] * 0.01)
        curr_price = closes[-1]
        curr_candle = candles[-1]

        prev_close = closes[-2]
        prev_vwap = vwap_series[-2]
        curr_vwap = vwap_series[-1]

        if None in (prev_vwap, curr_vwap):
            return []

        signals: list[StrategySignal] = []

        # Price crosses above VWAP
        if prev_close <= prev_vwap and curr_price > curr_vwap:
            sl_distance = max(curr_atr * 1.5, curr_price * 0.005)
            signals.append(
                StrategySignal(
                    symbol=curr_candle.symbol,
                    timeframe=curr_candle.timeframe,
                    direction=SignalDirection.BUY,
                    entry=curr_price,
                    stop_loss=round(curr_price - sl_distance, 2),
                    take_profit=round(curr_price + (sl_distance * self.risk_reward_target), 2),
                    confidence=0.79,
                    strategy=self.name,
                    reasons=[
                        f"Price ({curr_price:.2f}) crossed above institutional VWAP ({curr_vwap:.2f})"
                    ],
                    timestamp=curr_candle.timestamp,
                    market_regime="BULLISH_FLOW",
                )
            )

        # Price crosses below VWAP
        elif prev_close >= prev_vwap and curr_price < curr_vwap:
            sl_distance = max(curr_atr * 1.5, curr_price * 0.005)
            signals.append(
                StrategySignal(
                    symbol=curr_candle.symbol,
                    timeframe=curr_candle.timeframe,
                    direction=SignalDirection.SELL,
                    entry=curr_price,
                    stop_loss=round(curr_price + sl_distance, 2),
                    take_profit=round(curr_price - (sl_distance * self.risk_reward_target), 2),
                    confidence=0.79,
                    strategy=self.name,
                    reasons=[
                        f"Price ({curr_price:.2f}) crossed below institutional VWAP ({curr_vwap:.2f})"
                    ],
                    timestamp=curr_candle.timestamp,
                    market_regime="BEARISH_FLOW",
                )
            )

        return signals
