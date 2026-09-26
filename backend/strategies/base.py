"""
Strategy Base Architecture.
Defines the standard plugin interface for technical and quantitative trading strategies.
Every strategy must process historical or streaming candles and emit standardized StrategySignals.
"""

from abc import ABC, abstractmethod
from typing import Any

from backend.core.models import OHLCVCandle, StrategySignal


class BaseStrategy(ABC):
    """
    Abstract Base Class for all Strategy Plugins.
    Strategies are pure logic blocks: they accept market data and return candidate signals.
    Strategies have ZERO knowledge of real/paper broker routing or risk boundaries.
    """

    def __init__(self, name: str, params: dict[str, Any] | None = None) -> None:
        self.name = name
        self.params = params or {}

    @property
    @abstractmethod
    def required_candles(self) -> int:
        """Minimum number of OHLCV bars needed to compute strategy indicators."""
        pass

    def validate_data(self, candles: list[OHLCVCandle]) -> None:
        """Validate input candle sequence before calculation."""
        if not candles:
            raise ValueError(f"Strategy {self.name} received empty candle sequence.")
        if len(candles) < self.required_candles:
            raise ValueError(
                f"Strategy {self.name} requires at least {self.required_candles} candles, got {len(candles)}."
            )

    @abstractmethod
    def generate_signals(self, candles: list[OHLCVCandle]) -> list[StrategySignal]:
        """
        Evaluate candle sequence and emit trading signals.
        Must return an empty list if no clear edge is identified.
        """
        pass
