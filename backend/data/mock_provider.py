"""
Mock Data Provider for testing and local development.
Provides deterministic, synthetic market data for offline validation.
Explicitly labeled as MOCK data — never confused with real production feeds.
"""

import math
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.core.models import OHLCVCandle, TimeFrame
from backend.data.base import BaseDataProvider


class MockDataProvider(BaseDataProvider):
    """
    Deterministic Sandbox Data Provider.
    Used for unit testing, backtesting pipelines, and UI prototyping without API keys.
    """

    def __init__(self, base_price: float = 1000.0) -> None:
        super().__init__("mock_provider")
        self.base_price = base_price
        self._connected = False
        self.is_mock = True

    async def connect(self) -> bool:
        self._connected = True
        return True

    async def disconnect(self) -> None:
        self._connected = False

    async def is_connected(self) -> bool:
        return self._connected

    async def get_historical_candles(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start_time: datetime,
        end_time: datetime,
    ) -> list[OHLCVCandle]:
        """
        Generates deterministic, continuous synthetic bars using a sinusoidal pattern.
        Ensures valid candle bounds (High >= Open/Close >= Low).
        """
        candles: list[OHLCVCandle] = []
        current = start_time.replace(tzinfo=UTC) if not start_time.tzinfo else start_time
        target_end = end_time.replace(tzinfo=UTC) if not end_time.tzinfo else end_time

        # Approximate delta based on timeframe
        step = timedelta(minutes=1)
        if timeframe == TimeFrame.M5:
            step = timedelta(minutes=5)
        elif timeframe == TimeFrame.M15:
            step = timedelta(minutes=15)
        elif timeframe == TimeFrame.H1:
            step = timedelta(hours=1)
        elif timeframe == TimeFrame.D1:
            step = timedelta(days=1)

        price = self.base_price
        idx = 0

        while current < target_end and len(candles) < 2000:
            # Deterministic variation
            change = math.sin(idx * 0.1) * (self.base_price * 0.005)
            open_p = round(price, 2)
            close_p = round(max(1.0, open_p + change), 2)
            high_p = round(max(open_p, close_p) + abs(change) * 0.5 + 0.5, 2)
            low_p = round(max(0.5, min(open_p, close_p) - abs(change) * 0.5 - 0.5), 2)
            volume = round(1000.0 + abs(math.cos(idx * 0.1)) * 500.0, 2)

            candle = OHLCVCandle(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=current,
                open=open_p,
                high=high_p,
                low=low_p,
                close=close_p,
                volume=volume,
                trades_count=int(volume // 10),
            )
            candles.append(candle)

            price = close_p
            current += step
            idx += 1

        return candles

    async def fetch_historical_candles(
        self,
        symbol: str,
        timeframe: str | TimeFrame = TimeFrame.M15,
        limit: int = 100,
    ) -> list[OHLCVCandle]:
        """Convenience method to generate the latest N candles for a symbol and timeframe."""
        tf = TimeFrame(timeframe) if isinstance(timeframe, str) else timeframe
        step = timedelta(minutes=15)
        if tf == TimeFrame.M1:
            step = timedelta(minutes=1)
        elif tf == TimeFrame.M3:
            step = timedelta(minutes=3)
        elif tf == TimeFrame.M5:
            step = timedelta(minutes=5)
        elif tf == TimeFrame.M30:
            step = timedelta(minutes=30)
        elif tf == TimeFrame.H1:
            step = timedelta(hours=1)
        elif tf == TimeFrame.H4:
            step = timedelta(hours=4)
        elif tf == TimeFrame.D1:
            step = timedelta(days=1)
        elif tf == TimeFrame.W1:
            step = timedelta(weeks=1)

        end_time = datetime.now(UTC)
        start_time = end_time - (step * (limit + 5))
        candles = await self.get_historical_candles(symbol, tf, start_time, end_time)
        return candles[-limit:] if len(candles) >= limit else candles


    async def subscribe(
        self,
        symbols: list[str],
        timeframe: TimeFrame,
        callback: Callable[[OHLCVCandle], Any],
    ) -> None:
        for s in symbols:
            self._subscribers.setdefault(s, []).append(callback)

    async def unsubscribe(self, symbols: list[str], timeframe: TimeFrame) -> None:
        for s in symbols:
            self._subscribers.pop(s, None)

    async def get_latest_quote(self, symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "price": self.base_price,
            "bid": self.base_price - 0.05,
            "ask": self.base_price + 0.05,
            "volume": 10000.0,
            "timestamp": datetime.now(UTC).isoformat(),
            "provider": "MOCK_SANDBOX",
        }
