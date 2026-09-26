"""
Bollinger Bands Mean-Reversion Strategy.
Generates BUY when price pierces below lower band and bounces back.
Generates SELL when price pierces above upper band and falls back.
"""

from typing import Any

from backend.core.models import OHLCVCandle, SignalDirection, StrategySignal
from backend.indicators.technical import compute_atr, compute_bollinger_bands
from backend.strategies.base import BaseStrategy


class BollingerBandsStrategy(BaseStrategy):
    """Bollinger Bands Strategy."""

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        p = params or {}
        super().__init__("BOLLINGER_BANDS", p)
        self.period = int(self.params.get("period", 20))
        self.num_std_dev = float(self.params.get("num_std_dev", 2.0))
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

        upper, mid, lower = compute_bollinger_bands(closes, self.period, self.num_std_dev)
        atr_series = compute_atr(highs, lows, closes, self.atr_period)

        curr_atr = atr_series[-1] or (closes[-1] * 0.01)
        curr_price = closes[-1]
        curr_candle = candles[-1]

        prev_close = closes[-2]
        prev_lower = lower[-2]
        prev_upper = upper[-2]
        curr_lower = lower[-1]
        curr_upper = upper[-1]

        if None in (prev_lower, prev_upper, curr_lower, curr_upper):
            return []

        signals: list[StrategySignal] = []

        # Pierced below lower band, now closed above lower band (Mean reversion bounce)
        if prev_close <= prev_lower and curr_price > curr_lower:
            sl_distance = max(curr_atr * 1.5, curr_price * 0.005)
            signals.append(
                StrategySignal(
                    symbol=curr_candle.symbol,
                    timeframe=curr_candle.timeframe,
                    direction=SignalDirection.BUY,
                    entry=curr_price,
                    stop_loss=round(curr_price - sl_distance, 2),
                    take_profit=round(curr_price + (sl_distance * self.risk_reward_target), 2),
                    confidence=0.76,
                    strategy=self.name,
                    reasons=[f"Price bounced off lower Bollinger Band ({curr_lower:.2f})"],
                    timestamp=curr_candle.timestamp,
                    market_regime="MEAN_REVERSION",
                )
            )

        # Pierced above upper band, now closed below upper band (Mean reversion pullback)
        elif prev_close >= prev_upper and curr_price < curr_upper:
            sl_distance = max(curr_atr * 1.5, curr_price * 0.005)
            signals.append(
                StrategySignal(
                    symbol=curr_candle.symbol,
                    timeframe=curr_candle.timeframe,
                    direction=SignalDirection.SELL,
                    entry=curr_price,
                    stop_loss=round(curr_price + sl_distance, 2),
                    take_profit=round(curr_price - (sl_distance * self.risk_reward_target), 2),
                    confidence=0.76,
                    strategy=self.name,
                    reasons=[f"Price rejected from upper Bollinger Band ({curr_upper:.2f})"],
                    timestamp=curr_candle.timestamp,
                    market_regime="MEAN_REVERSION",
                )
            )

        return signals
