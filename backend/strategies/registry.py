"""
Strategy Registry.
Maintains catalog of algorithmic trading strategy plugins.
Supports dynamic discovery, parameter introspection, and instantiation.
"""

from typing import Any

from backend.strategies.base import BaseStrategy
from backend.strategies.bollinger_bands import BollingerBandsStrategy
from backend.strategies.breakout import BreakoutStrategy
from backend.strategies.ema_crossover import EmaCrossoverStrategy
from backend.strategies.macd import MacdStrategy
from backend.strategies.mean_reversion import MeanReversionStrategy
from backend.strategies.momentum import MomentumStrategy
from backend.strategies.rsi import RsiStrategy
from backend.strategies.sma_crossover import SmaCrossoverStrategy
from backend.strategies.trend_following import TrendFollowingStrategy
from backend.strategies.vwap import VwapStrategy

STRATEGY_CATALOG: dict[str, type[BaseStrategy]] = {
    "EMA_CROSSOVER": EmaCrossoverStrategy,
    "SMA_CROSSOVER": SmaCrossoverStrategy,
    "RSI": RsiStrategy,
    "MACD": MacdStrategy,
    "BOLLINGER_BANDS": BollingerBandsStrategy,
    "VWAP": VwapStrategy,
    "BREAKOUT": BreakoutStrategy,
    "MOMENTUM": MomentumStrategy,
    "TREND_FOLLOWING": TrendFollowingStrategy,
    "MEAN_REVERSION": MeanReversionStrategy,
}


class StrategyRegistry:
    """Registry and factory for algorithmic strategy plugins."""

    @classmethod
    def list_strategies(cls) -> list[dict[str, Any]]:
        """Returns catalog metadata for all registered strategies."""
        results: list[dict[str, Any]] = []
        for strat_id, strat_cls in STRATEGY_CATALOG.items():
            instance = strat_cls()
            results.append(
                {
                    "id": strat_id,
                    "name": instance.name,
                    "required_candles": instance.required_candles,
                    "default_parameters": instance.params,
                    "description": strat_cls.__doc__.strip().split("\n")[0]
                    if strat_cls.__doc__
                    else "",
                }
            )
        return results

    @classmethod
    def get_strategy(cls, strategy_id: str, params: dict[str, Any] | None = None) -> BaseStrategy:
        """Instantiates a strategy by identifier with optional custom parameters."""
        strat_cls = STRATEGY_CATALOG.get(strategy_id.upper())
        if not strat_cls:
            raise ValueError(
                f"Unknown strategy '{strategy_id}'. Available: {list(STRATEGY_CATALOG.keys())}"
            )
        return strat_cls(params)


strategy_registry = StrategyRegistry()
