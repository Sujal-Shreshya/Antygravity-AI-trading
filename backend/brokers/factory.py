"""
Broker Factory & Catalog Registry.
Enables pluggable broker selection across Indian Equities, Crypto, and Forex.
Strategy and risk engines remain fully agnostic of broker-specific APIs.
"""

from typing import Any

from backend.brokers.base import BaseBroker
from backend.brokers.binance import BinanceBrokerAdapter
from backend.brokers.kite import KiteBrokerAdapter
from backend.brokers.oanda import OandaBrokerAdapter


class BrokerFactory:
    """Factory for instantiating multi-market broker adapters."""

    _instances: dict[str, BaseBroker] = {}

    @classmethod
    def get_broker(
        cls,
        name: str,
        is_sandbox: bool = True,
        **kwargs: Any,
    ) -> BaseBroker:
        """Returns or creates a singleton broker instance for the specified provider."""
        key = f"{name.upper()}_{is_sandbox}"
        if key in cls._instances:
            return cls._instances[key]

        normalized = name.upper()
        adapter: BaseBroker

        if normalized in ("KITE", "ZERODHA"):
            adapter = KiteBrokerAdapter(is_sandbox=is_sandbox, **kwargs)
        elif normalized in ("BINANCE", "BINANCE_SPOT"):
            adapter = BinanceBrokerAdapter(is_futures=False, is_sandbox=is_sandbox, **kwargs)
        elif normalized in ("BINANCE_FUTURES",):
            adapter = BinanceBrokerAdapter(is_futures=True, is_sandbox=is_sandbox, **kwargs)
        elif normalized in ("OANDA", "FOREX"):
            adapter = OandaBrokerAdapter(is_sandbox=is_sandbox, **kwargs)
        else:
            raise ValueError(
                f"Unsupported broker: '{name}'. Supported: KITE, BINANCE, BINANCE_FUTURES, OANDA."
            )

        cls._instances[key] = adapter
        return adapter


broker_factory = BrokerFactory()
