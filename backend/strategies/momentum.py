"""
Momentum / Rate of Change Strategy.
Generates BUY when momentum crosses above 0 with positive acceleration.
Generates SELL when momentum crosses below 0 with negative acceleration.
"""

from typing import Any

from backend.core.models import OHLCVCandle, SignalDirection, StrategySignal
from backend.indicators.technical import compute_atr, compute_momentum
from backend.strategies.base import BaseStrategy


class MomentumStrategy(BaseStrategy):
    """Price Velocity and Acceleration Strategy."""

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        p = params or {}
        super().__init__("MOMENTUM", p)
        self.period = int(self.params.get("period", 10))
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

        mom_series = compute_momentum(closes, self.period)
        atr_series = compute_atr(highs, lows, closes, self.atr_period)

        curr_atr = atr_series[-1] or (closes[-1] * 0.01)
        curr_price = closes[-1]
        curr_candle = candles[-1]

        prev_mom = mom_series[-2]
        curr_mom = mom_series[-1]

        if prev_mom is None or curr_mom is None:
            return []

        signals: list[StrategySignal] = []

        if prev_mom <= 0 and curr_mom > 0:
            sl_distance = max(curr_atr * 1.5, curr_price * 0.005)
            signals.append(
                StrategySignal(
                    symbol=curr_candle.symbol,
                    timeframe=curr_candle.timeframe,
                    direction=SignalDirection.BUY,
                    entry=curr_price,
                    stop_loss=round(curr_price - sl_distance, 2),
                    take_profit=round(curr_price + (sl_distance * self.risk_reward_target), 2),
                    confidence=0.74,
                    strategy=self.name,
                    reasons=[f"Price momentum({self.period}) turned positive ({curr_mom:.2f})"],
                    timestamp=curr_candle.timestamp,
                    market_regime="MOMENTUM_SURGE",
                )
            )
        elif prev_mom >= 0 and curr_mom < 0:
            sl_distance = max(curr_atr * 1.5, curr_price * 0.005)
            signals.append(
                StrategySignal(
                    symbol=curr_candle.symbol,
                    timeframe=curr_candle.timeframe,
                    direction=SignalDirection.SELL,
                    entry=curr_price,
                    stop_loss=round(curr_price + sl_distance, 2),
                    take_profit=round(curr_price - (sl_distance * self.risk_reward_target), 2),
                    confidence=0.74,
                    strategy=self.name,
                    reasons=[f"Price momentum({self.period}) turned negative ({curr_mom:.2f})"],
                    timestamp=curr_candle.timestamp,
                    market_regime="MOMENTUM_DUMP",
                )
            )

        return signals
