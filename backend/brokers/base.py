"""
Unified Broker / Exchange Abstraction Layer.
Defines the standard asynchronous interface that every broker adapter must implement.
The core engine, strategies, and risk modules interact ONLY with this interface.
"""

from abc import ABC, abstractmethod
from typing import Any

from backend.core.config import get_settings
from backend.core.exceptions import LiveTradingBlockedError
from backend.core.kill_switch import kill_switch
from backend.core.models import (
    AccountBalance,
    OHLCVCandle,
    OrderRequest,
    OrderResponse,
    Position,
    TimeFrame,
    Trade,
)


class BaseBroker(ABC):
    """
    Abstract Base Class for Broker and Exchange Adapters.
    Encapsulates all communication with Indian brokers (Kite/Upstox),
    crypto exchanges (Binance), and Forex providers (OANDA).
    """

    def __init__(self, broker_name: str) -> None:
        self.broker_name = broker_name
        self._settings = get_settings()

    def _verify_execution_safety(self, order: OrderRequest) -> None:
        """
        Enforces global execution safety invariants:
        1. If order requests live execution while LIVE_TRADING=False -> Blocked immediately.
        2. If emergency kill switch is engaged -> Blocked immediately.
        """
        kill_switch.verify_inactive()

        if order.live_execution and not self._settings.LIVE_TRADING:
            raise LiveTradingBlockedError(
                message=f"Live order on {self.broker_name} blocked: Engine is running with LIVE_TRADING=false.",
                details={
                    "broker": self.broker_name,
                    "symbol": order.symbol,
                    "client_order_id": order.client_order_id,
                },
            )

    @abstractmethod
    async def connect(self) -> bool:
        """Establish session, authenticate credentials, and test connectivity."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully terminate connection and unsubscribe from streams."""
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        """Returns True if the connection to the broker is healthy and active."""
        pass

    @abstractmethod
    async def get_accounts(self) -> list[dict[str, Any]]:
        """Fetch list of linked trading accounts."""
        pass

    @abstractmethod
    async def get_balance(self) -> AccountBalance:
        """Retrieve current cash, equity, and margin balance."""
        pass

    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """Fetch current open positions."""
        pass

    @abstractmethod
    async def get_orders(self, symbol: str | None = None) -> list[OrderResponse]:
        """Fetch all orders or filter by symbol for the current trading day."""
        pass

    @abstractmethod
    async def get_instruments(self, market: str | None = None) -> list[dict[str, Any]]:
        """Fetch tradable instrument master contracts."""
        pass

    @abstractmethod
    async def get_quotes(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        """Fetch latest quotes, bid/ask, and volume for given symbols."""
        pass

    @abstractmethod
    async def get_historical_data(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start_time: Any,
        end_time: Any,
    ) -> list[OHLCVCandle]:
        """Fetch historical OHLCV bars without data fabrication."""
        pass

    async def place_order(self, order: OrderRequest) -> OrderResponse:
        """
        Place an order with pre-execution safety enforcement.
        Subclasses implement `_execute_place_order`.
        """
        self._verify_execution_safety(order)
        return await self._execute_place_order(order)

    @abstractmethod
    async def _execute_place_order(self, order: OrderRequest) -> OrderResponse:
        """Broker-specific order placement implementation."""
        pass

    @abstractmethod
    async def modify_order(
        self,
        order_id: str,
        new_quantity: float | None = None,
        new_price: float | None = None,
        new_stop_price: float | None = None,
    ) -> OrderResponse:
        """Modify an existing open working order."""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> OrderResponse:
        """Cancel an open working order."""
        pass

    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderResponse:
        """Retrieve latest state of an order."""
        pass

    @abstractmethod
    async def get_margin(self, order: OrderRequest) -> dict[str, float]:
        """Calculate required margin for an order prior to submission."""
        pass

    @abstractmethod
    async def get_trade_history(self, symbol: str | None = None) -> list[Trade]:
        """Fetch execution trades and fills for the current session/period."""
        pass
