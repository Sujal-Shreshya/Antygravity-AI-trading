"""
Market Data Provider Abstraction Layer.
Defines interfaces for consuming streaming ticks/bars and querying historical candles.
Ensures standardized schema normalization across NSE, Crypto, and Forex feeds.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
from typing import Any

from backend.core.models import OHLCVCandle, TimeFrame


class BaseDataProvider(ABC):
    """Abstract interface for all streaming and REST market data providers."""

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name
        self._subscribers: dict[str, list[Callable[[OHLCVCandle], Any]]] = {}

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to WebSocket stream or initiate REST session."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect active streaming feeds cleanly."""
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if market data stream is alive and receiving heartbeats."""
        pass

    @abstractmethod
    async def get_historical_candles(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start_time: datetime,
        end_time: datetime,
    ) -> list[OHLCVCandle]:
        """Fetch historical bars without synthesizing or fabricating missing records."""
        pass

    @abstractmethod
    async def subscribe(
        self,
        symbols: list[str],
        timeframe: TimeFrame,
        callback: Callable[[OHLCVCandle], Any],
    ) -> None:
        """Subscribe to real-time candle or tick updates."""
        pass

    @abstractmethod
    async def unsubscribe(self, symbols: list[str], timeframe: TimeFrame) -> None:
        """Unsubscribe from real-time feeds."""
        pass

    @abstractmethod
    async def get_latest_quote(self, symbol: str) -> dict[str, Any]:
        """Fetch top-of-book bid, ask, last price, and volume."""
        pass
