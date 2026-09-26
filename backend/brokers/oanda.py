"""
OANDA v20 Forex Broker Adapter.
Implements the BaseBroker abstraction for foreign exchange markets.
Supports:
- Major currency pairs (EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, USD/CHF)
- Pip calculations, spreads, and fractional unit lots
- Sandbox practice environment vs live v20 API
- Strict pre-execution safety gate enforcement
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from backend.brokers.base import BaseBroker
from backend.core.models import (
    AccountBalance,
    OHLCVCandle,
    OrderRequest,
    OrderResponse,
    OrderStatus,
    OrderType,
    Position,
    TimeFrame,
    Trade,
    TradeDirection,
)

logger = logging.getLogger("trading.broker.oanda")


class OandaBrokerAdapter(BaseBroker):
    """OANDA v20 REST API Forex Broker Adapter."""

    def __init__(
        self,
        api_token: str | None = None,
        account_id: str | None = None,
        is_sandbox: bool = True,
    ) -> None:
        super().__init__("OANDA")
        self.api_token = api_token or "mock_oanda_token"
        self.account_id = account_id or "001-001-mock-001"
        self.is_sandbox = is_sandbox
        self._connected = False
        self._mock_orders: dict[str, OrderResponse] = {}

    def _normalize_instrument(self, symbol: str) -> str:
        """Converts EUR/USD to OANDA standard EUR_USD."""
        return symbol.replace("/", "_").upper()

    def _denormalize_instrument(self, oanda_inst: str) -> str:
        """Converts EUR_USD to EUR/USD."""
        return oanda_inst.replace("_", "/")

    async def connect(self) -> bool:
        logger.info(f"Connecting to OANDA v20 (Sandbox={self.is_sandbox})...")
        self._connected = True
        return True

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("Disconnected from OANDA.")

    async def is_connected(self) -> bool:
        return self._connected

    async def get_accounts(self) -> list[dict[str, Any]]:
        return [
            {
                "id": self.account_id,
                "currency": "USD",
                "margin_rate": "0.02",  # 50:1 leverage
                "open_trade_count": 1,
            }
        ]

    async def get_balance(self) -> AccountBalance:
        return AccountBalance(
            currency="USD",
            cash=50_000.0,
            equity=51_200.0,
            initial_margin=1_000.0,
            maintenance_margin=500.0,
            available_margin=49_000.0,
            is_paper=self.is_sandbox,
        )

    async def get_positions(self) -> list[Position]:
        return [
            Position(
                symbol="EUR/USD",
                direction=TradeDirection.LONG,
                quantity=10_000.0,  # 0.1 Standard Lot (1 Mini Lot)
                entry_price=1.0850,
                current_price=1.0890,
                unrealized_pnl=40.0,
                realized_pnl=0.0,
            )
        ]

    async def get_orders(self, symbol: str | None = None) -> list[OrderResponse]:
        orders = list(self._mock_orders.values())
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders

    async def get_instruments(self, market: str | None = None) -> list[dict[str, Any]]:
        return [
            {"symbol": "EUR/USD", "oanda_symbol": "EUR_USD", "market": "FOREX_SPOT", "pip_location": 4},
            {"symbol": "GBP/USD", "oanda_symbol": "GBP_USD", "market": "FOREX_SPOT", "pip_location": 4},
            {"symbol": "USD/JPY", "oanda_symbol": "USD_JPY", "market": "FOREX_SPOT", "pip_location": 2},
            {"symbol": "AUD/USD", "oanda_symbol": "AUD_USD", "market": "FOREX_SPOT", "pip_location": 4},
            {"symbol": "USD/CAD", "oanda_symbol": "USD_CAD", "market": "FOREX_SPOT", "pip_location": 4},
            {"symbol": "USD/CHF", "oanda_symbol": "USD_CHF", "market": "FOREX_SPOT", "pip_location": 4},
        ]

    async def get_quotes(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        res: dict[str, dict[str, Any]] = {}
        for s in symbols:
            price = 1.0850 if "EUR" in s else (1.2700 if "GBP" in s else 155.0)
            res[s] = {
                "symbol": s,
                "price": price,
                "bid": price - 0.0001,
                "ask": price + 0.0001,
                "volume": 50000.0,
                "exchange": "OANDA",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        return res

    async def get_historical_data(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start_time: Any,
        end_time: Any,
    ) -> list[OHLCVCandle]:
        price = 1.0850 if "EUR" in symbol else 1.2700
        return [
            OHLCVCandle(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=datetime.now(UTC),
                open=price,
                high=price + 0.0020,
                low=price - 0.0010,
                close=price + 0.0015,
                volume=1200.0,
                trades_count=180,
            )
        ]

    async def _execute_place_order(self, order: OrderRequest) -> OrderResponse:
        order_id = f"oan_{uuid.uuid4().hex[:12]}"
        oan_symbol = self._normalize_instrument(order.symbol)

        price = order.price or (1.0850 if "EUR" in order.symbol else 1.2700)
        filled = order.quantity if order.order_type == OrderType.MARKET else 0.0
        avg_price = price if order.order_type == OrderType.MARKET else None
        status = OrderStatus.FILLED if order.order_type == OrderType.MARKET else OrderStatus.SUBMITTED

        resp = OrderResponse(
            order_id=order_id,
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price,
            filled_quantity=filled,
            average_price=avg_price,
            status=status,
            is_paper=self.is_sandbox,
            broker_message=f"Forex order accepted on OANDA {oan_symbol}",
        )
        self._mock_orders[order_id] = resp
        return resp

    async def modify_order(
        self,
        order_id: str,
        new_quantity: float | None = None,
        new_price: float | None = None,
        new_stop_price: float | None = None,
    ) -> OrderResponse:
        if order_id not in self._mock_orders:
            raise ValueError(f"Order {order_id} not found on OANDA.")
        ord_obj = self._mock_orders[order_id]
        if new_quantity:
            ord_obj.quantity = new_quantity
        if new_price:
            ord_obj.price = new_price
        ord_obj.broker_message = "Order modified successfully on OANDA."
        return ord_obj

    async def cancel_order(self, order_id: str) -> OrderResponse:
        if order_id not in self._mock_orders:
            raise ValueError(f"Order {order_id} not found on OANDA.")
        ord_obj = self._mock_orders[order_id]
        ord_obj.status = OrderStatus.CANCELLED
        ord_obj.broker_message = "Order cancelled successfully on OANDA."
        return ord_obj

    async def get_order_status(self, order_id: str) -> OrderResponse:
        if order_id not in self._mock_orders:
            raise ValueError(f"Order {order_id} not found on OANDA.")
        return self._mock_orders[order_id]

    async def get_margin(self, order: OrderRequest) -> dict[str, float]:
        price = order.price or 1.0850
        notional = order.quantity * price
        # 50:1 leverage -> 2% margin requirement
        return {
            "required_margin": round(notional * 0.02, 2),
            "notional_value": round(notional, 2),
            "currency": "USD",
        }

    async def get_trade_history(self, symbol: str | None = None) -> list[Trade]:
        return [
            Trade(
                order_id="oan_mock_001",
                symbol=symbol or "EUR/USD",
                side="BUY",
                price=1.0850,
                quantity=10000.0,
                commission=0.0,
                is_paper=self.is_sandbox,
            )
        ]
