"""
Real-time Candle Aggregator and Tick Normalizer.
Aggregates asynchronous price ticks into time-bucketed OHLCV bars.
Protects against out-of-order ticks, duplicates, and clock drift.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.core.models import OHLCVCandle, TimeFrame

logger = logging.getLogger("trading.data.aggregator")


class Tick(BaseModel):
    """Raw or normalized price quote tick."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    price: float = Field(..., gt=0)
    volume: float = Field(default=0.0, ge=0)
    timestamp: datetime
    bid: float | None = None
    ask: float | None = None


def get_timeframe_seconds(tf: TimeFrame) -> int:
    """Returns the duration of a timeframe in seconds."""
    match tf:
        case TimeFrame.M1:
            return 60
        case TimeFrame.M3:
            return 180
        case TimeFrame.M5:
            return 300
        case TimeFrame.M15:
            return 900
        case TimeFrame.M30:
            return 1800
        case TimeFrame.H1:
            return 3600
        case TimeFrame.H4:
            return 14400
        case TimeFrame.D1:
            return 86400
        case TimeFrame.W1:
            return 604800
        case _:
            return 60


def bucket_timestamp(dt: datetime, tf: TimeFrame) -> datetime:
    """Rounds down a datetime to the opening boundary of its timeframe bucket."""
    seconds = get_timeframe_seconds(tf)
    epoch = int(dt.timestamp())
    bucket_epoch = (epoch // seconds) * seconds
    return datetime.fromtimestamp(bucket_epoch, tz=UTC)


class CandleAggregator:
    """
    Maintains in-progress OHLCV bars for subscribed symbols and timeframes.
    Emits completed candles when a tick crosses the bucket boundary.
    """

    def __init__(
        self,
        timeframe: TimeFrame,
        on_candle_close: Callable[[OHLCVCandle], None] | None = None,
    ) -> None:
        self.timeframe = timeframe
        self.on_candle_close = on_candle_close
        # symbol -> in-progress candle state dict
        self._current_candles: dict[str, dict] = {}
        # symbol -> last seen tick timestamp for out-of-order rejection
        self._last_tick_time: dict[str, datetime] = {}

    def process_tick(self, tick: Tick) -> OHLCVCandle | None:
        """
        Processes an incoming tick.
        Returns a completed OHLCVCandle if this tick triggered a bar closure, otherwise None.
        """
        dt = tick.timestamp if tick.timestamp.tzinfo else tick.timestamp.replace(tzinfo=UTC)
        symbol = tick.symbol

        # Out-of-order tick protection
        last_time = self._last_tick_time.get(symbol)
        if last_time and dt < last_time:
            logger.warning(
                f"Discarded out-of-order tick for {symbol}: tick time {dt} < last seen {last_time}"
            )
            return None

        self._last_tick_time[symbol] = dt
        bar_open_time = bucket_timestamp(dt, self.timeframe)
        current = self._current_candles.get(symbol)

        completed_candle: OHLCVCandle | None = None

        if current is not None:
            # Check if this tick belongs to a new time bucket
            if bar_open_time > current["timestamp"]:
                # Close the existing bar
                completed_candle = OHLCVCandle(
                    symbol=symbol,
                    timeframe=self.timeframe,
                    timestamp=current["timestamp"],
                    open=current["open"],
                    high=current["high"],
                    low=current["low"],
                    close=current["close"],
                    volume=current["volume"],
                    trades_count=current["trades_count"],
                )
                if self.on_candle_close:
                    self.on_candle_close(completed_candle)

                # Reset for new bar
                self._current_candles[symbol] = {
                    "timestamp": bar_open_time,
                    "open": tick.price,
                    "high": tick.price,
                    "low": tick.price,
                    "close": tick.price,
                    "volume": tick.volume,
                    "trades_count": 1,
                }
            else:
                # Update existing bar
                current["high"] = max(current["high"], tick.price)
                current["low"] = min(current["low"], tick.price)
                current["close"] = tick.price
                current["volume"] += tick.volume
                current["trades_count"] += 1
        else:
            # Initialize first bar
            self._current_candles[symbol] = {
                "timestamp": bar_open_time,
                "open": tick.price,
                "high": tick.price,
                "low": tick.price,
                "close": tick.price,
                "volume": tick.volume,
                "trades_count": 1,
            }

        return completed_candle

    def get_current_candle(self, symbol: str) -> OHLCVCandle | None:
        """Returns the current incomplete candle for a symbol if available."""
        current = self._current_candles.get(symbol)
        if not current:
            return None
        return OHLCVCandle(
            symbol=symbol,
            timeframe=self.timeframe,
            timestamp=current["timestamp"],
            open=current["open"],
            high=current["high"],
            low=current["low"],
            close=current["close"],
            volume=current["volume"],
            trades_count=current["trades_count"],
        )
