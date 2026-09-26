"""
Market Data Feed Manager.
Coordinates data providers, manages real-time candle aggregation,
maintains an in-memory cache of recent bars, and detects stale feeds.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from backend.core.models import OHLCVCandle, TimeFrame
from backend.data.aggregator import CandleAggregator, Tick

logger = logging.getLogger("trading.data.feed_manager")


class MarketDataManager:
    """Singleton coordinator for market data consumption, caching, and distribution."""

    _instance: "MarketDataManager | None" = None

    def __new__(cls) -> "MarketDataManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        # (symbol, timeframe) -> CandleAggregator
        self._aggregators: dict[tuple[str, TimeFrame], CandleAggregator] = {}
        # (symbol, timeframe) -> list[OHLCVCandle] (ring buffer up to 1000 bars)
        self._candle_cache: dict[tuple[str, TimeFrame], list[OHLCVCandle]] = {}
        # symbol -> latest Tick
        self._latest_ticks: dict[str, Tick] = {}
        # symbol -> last update timestamp
        self._last_heartbeat: dict[str, datetime] = {}
        # Callbacks registered for new closed candles
        self._candle_subscribers: list[Callable[[OHLCVCandle], Any]] = []

        self._max_cached_bars: int = 1000
        self._stale_threshold_seconds: int = 60
        self._initialized = True

    def register_candle_subscriber(self, callback: Callable[[OHLCVCandle], Any]) -> None:
        """Subscribes an asynchronous or synchronous callback to finalized candle events."""
        if callback not in self._candle_subscribers:
            self._candle_subscribers.append(callback)

    def on_tick(self, tick: Tick) -> None:
        """Entry point for incoming ticks from WebSocket or REST pollers."""
        symbol = tick.symbol
        now = datetime.now(UTC)
        self._latest_ticks[symbol] = tick
        self._last_heartbeat[symbol] = now

        # Update aggregators across all active timeframes for this symbol
        for tf in (TimeFrame.M1, TimeFrame.M5, TimeFrame.M15, TimeFrame.H1, TimeFrame.D1):
            key = (symbol, tf)
            if key not in self._aggregators:
                self._aggregators[key] = CandleAggregator(
                    timeframe=tf,
                    on_candle_close=self._handle_closed_candle,
                )

            closed_candle = self._aggregators[key].process_tick(tick)
            if closed_candle:
                self._handle_closed_candle(closed_candle)

    def _handle_closed_candle(self, candle: OHLCVCandle) -> None:
        """Appends closed candle to memory cache and notifies subscribers."""
        key = (candle.symbol, candle.timeframe)
        if key not in self._candle_cache:
            self._candle_cache[key] = []

        bars = self._candle_cache[key]
        bars.append(candle)
        if len(bars) > self._max_cached_bars:
            self._candle_cache[key] = bars[-self._max_cached_bars :]

        # Notify downstream subscribers (e.g. strategy engine)
        for sub in self._candle_subscribers:
            try:
                sub(candle)
            except Exception as e:
                logger.error(f"Error in candle subscriber: {e}", exc_info=True)

    def get_latest_quote(self, symbol: str) -> dict[str, Any] | None:
        """Returns the most recent tick quote and freshness state."""
        tick = self._latest_ticks.get(symbol)
        if not tick:
            return None

        last_seen = self._last_heartbeat.get(symbol, tick.timestamp)
        is_stale = (datetime.now(UTC) - last_seen).total_seconds() > self._stale_threshold_seconds

        return {
            "symbol": tick.symbol,
            "price": tick.price,
            "volume": tick.volume,
            "bid": tick.bid,
            "ask": tick.ask,
            "timestamp": tick.timestamp.isoformat(),
            "is_stale": is_stale,
        }

    def get_candles(
        self,
        symbol: str,
        timeframe: TimeFrame,
        limit: int = 100,
    ) -> list[OHLCVCandle]:
        """Returns recent completed candles from in-memory cache."""
        key = (symbol, timeframe)
        bars = self._candle_cache.get(key, [])
        return bars[-limit:]

    def load_historical_candles(
        self,
        symbol: str,
        timeframe: TimeFrame,
        candles: list[OHLCVCandle],
    ) -> None:
        """Pre-populates the cache with historical candles (e.g. on engine startup)."""
        key = (symbol, timeframe)
        self._candle_cache[key] = sorted(candles, key=lambda c: c.timestamp)


# Global singleton instance
market_data_manager = MarketDataManager()
