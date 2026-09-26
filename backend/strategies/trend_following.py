"""
Trend Following Multi-Indicator Strategy.
Combines EMA alignment (20 > 50 > 200) with MACD confirmation and RSI trend filter.
"""

from typing import Any

from backend.core.models import OHLCVCandle, SignalDirection, StrategySignal
from backend.indicators.technical import compute_atr, compute_ema, compute_macd, compute_rsi
from backend.strategies.base import BaseStrategy


class TrendFollowingStrategy(BaseStrategy):
    """Multi-Indicator Trend Following Strategy."""

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        p = params or {}
        super().__init__("TREND_FOLLOWING", p)
        self.fast_ema_p = int(self.params.get("fast_ema", 20))
        self.slow_ema_p = int(self.params.get("slow_ema", 50))
        self.atr_period = int(self.params.get("atr_period", 14))
        self.risk_reward_target = float(self.params.get("risk_reward_target", 2.5))

    @property
    def required_candles(self) -> int:
        return self.slow_ema_p + 15

    def generate_signals(self, candles: list[OHLCVCandle]) -> list[StrategySignal]:
        self.validate_data(candles)

        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]

        fast_ema = compute_ema(closes, self.fast_ema_p)
        slow_ema = compute_ema(closes, self.slow_ema_p)
        rsi_series = compute_rsi(closes, 14)
        macd_l, signal_l, _ = compute_macd(closes, 12, 26, 9)
        atr_series = compute_atr(highs, lows, closes, self.atr_period)

        curr_atr = atr_series[-1] or (closes[-1] * 0.01)
        curr_price = closes[-1]
        curr_candle = candles[-1]

        f_ema, s_ema = fast_ema[-1], slow_ema[-1]
        rsi = rsi_series[-1]
        m, sig = macd_l[-1], signal_l[-1]

        if None in (f_ema, s_ema, rsi, m, sig):
            return []

        signals: list[StrategySignal] = []

        # Strong Bullish Trend Alignment: Fast EMA > Slow EMA, RSI between 50 and 70, MACD > Signal
        if f_ema > s_ema and 50.0 <= rsi <= 70.0 and m > sig:
            sl_distance = max(curr_atr * 2.0, curr_price * 0.008)
            signals.append(
                StrategySignal(
                    symbol=curr_candle.symbol,
                    timeframe=curr_candle.timeframe,
                    direction=SignalDirection.BUY,
                    entry=curr_price,
                    stop_loss=round(curr_price - sl_distance, 2),
                    take_profit=round(curr_price + (sl_distance * self.risk_reward_target), 2),
                    confidence=0.88,
                    strategy=self.name,
                    reasons=[
                        f"Fast EMA({self.fast_ema_p}) > Slow EMA({self.slow_ema_p})",
                        f"RSI in bullish zone ({rsi:.1f})",
                        "MACD above signal line",
                    ],
                    timestamp=curr_candle.timestamp,
                    market_regime="STRONG_UPTREND",
                )
            )

        # Strong Bearish Trend Alignment: Fast EMA < Slow EMA, RSI between 30 and 50, MACD < Signal
        elif f_ema < s_ema and 30.0 <= rsi <= 50.0 and m < sig:
            sl_distance = max(curr_atr * 2.0, curr_price * 0.008)
            signals.append(
                StrategySignal(
                    symbol=curr_candle.symbol,
                    timeframe=curr_candle.timeframe,
                    direction=SignalDirection.SELL,
                    entry=curr_price,
                    stop_loss=round(curr_price + sl_distance, 2),
                    take_profit=round(curr_price - (sl_distance * self.risk_reward_target), 2),
                    confidence=0.88,
                    strategy=self.name,
                    reasons=[
                        f"Fast EMA({self.fast_ema_p}) < Slow EMA({self.slow_ema_p})",
                        f"RSI in bearish zone ({rsi:.1f})",
                        "MACD below signal line",
                    ],
                    timestamp=curr_candle.timestamp,
                    market_regime="STRONG_DOWNTREND",
                )
            )

        return signals
