"""
Core trading engine exception hierarchy.
Provides domain-specific exceptions for risk limits, order validation,
live trading protection, and broker interactions.
"""

from typing import Any


class TradingEngineError(Exception):
    """Base exception for all trading engine errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class LiveTradingBlockedError(TradingEngineError):
    """Raised when an attempt is made to execute live trading while LIVE_TRADING=false."""

    def __init__(
        self,
        message: str = "Live trading order blocked: LIVE_TRADING is set to false in engine configuration.",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details)


class KillSwitchActiveError(TradingEngineError):
    """Raised when an action is blocked because the emergency kill switch is engaged."""

    def __init__(
        self,
        message: str = "Action rejected: Emergency kill switch is currently engaged.",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details)


class RiskLimitExceededError(TradingEngineError):
    """Raised when an order or trade violates pre-trade risk management constraints."""

    def __init__(
        self,
        message: str,
        rule_name: str,
        limit_value: float,
        actual_value: float,
        details: dict[str, Any] | None = None,
    ):
        det = details or {}
        det.update(
            {"rule_name": rule_name, "limit_value": limit_value, "actual_value": actual_value}
        )
        super().__init__(message, det)
        self.rule_name = rule_name
        self.limit_value = limit_value
        self.actual_value = actual_value


class OrderValidationError(TradingEngineError):
    """Raised when an order request fails syntactic or semantic validation."""

    pass


class DuplicateOrderError(TradingEngineError):
    """Raised when an idempotent order duplicate is detected within the deduplication window."""

    pass


class InsufficientFundsError(TradingEngineError):
    """Raised when account equity or margin is insufficient to support an order."""

    pass


class MarketClosedError(TradingEngineError):
    """Raised when attempting an order or trade outside active trading hours for the instrument."""

    pass


class BrokerConnectionError(TradingEngineError):
    """Raised when an external broker connection drops or fails authentication."""

    pass


class MarketDataError(TradingEngineError):
    """Raised when market data feeds are unavailable, disconnected, or corrupt."""

    pass
