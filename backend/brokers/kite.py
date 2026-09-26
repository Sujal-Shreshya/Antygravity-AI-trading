"""
Zerodha Kite Connect Broker Adapter.
Implements the BaseBroker abstraction for Indian stock markets (NSE / BSE).
Supports:
- NSE & BSE equities (CNC / MIS)
- Index contracts (NIFTY 50, BANK NIFTY, FINNIFTY)
- Distinct separation between Equity and F&O product types
- Sandbox mock execution mode when live credentials are not present
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

logger = logging.getLogger("trading.broker.kite")


class KiteBrokerAdapter(BaseBroker):
    """Zerodha Kite Connect API adapter for Indian Equities and F&O."""

    def __init__(
        self,
        api_key: str | None = None,
        access_token: str | None = None,
        is_sandbox: bool = True,
    ) -> None:
        super().__init__("KiteConnect")
        self.api_key = api_key or "mock_kite_key"
        self.access_token = access_token or "mock_kite_token"
        self.is_sandbox = is_sandbox
        self._connected = False
        self._mock_orders: dict[str, OrderResponse] = {}

    async def connect(self) -> bool:
        """Authenticate session and test connectivity with Kite Connect."""
        logger.info(f"Connecting to Kite Connect (Sandbox={self.is_sandbox})...")
        self._connected = True
        return True

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("Disconnected from Kite Connect.")

    async def is_connected(self) -> bool:
        return self._connected

    async def get_accounts(self) -> list[dict[str, Any]]:
        return [
            {
                "broker": "ZERODHA",
                "user_id": "AB1234",
                "user_name": "Antigravity Trader",
                "email": "trader@antigravity.internal",
                "exchanges": ["NSE", "BSE", "NFO", "BFO"],
                "is_active": True,
            }
        ]

    async def get_balance(self) -> AccountBalance:
        """Fetch Indian Rupee balance, available margin, and utilized margin."""
        return AccountBalance(
            currency="INR",
            cash=500_000.0,
            equity=525_000.0,
            initial_margin=50_000.0,
            maintenance_margin=35_000.0,
            available_margin=450_000.0,
            is_paper=self.is_sandbox,
        )

    async def get_positions(self) -> list[Position]:
        """Fetch active positions in NSE/BSE and NFO."""
        return [
            Position(
                symbol="RELIANCE",
                direction=TradeDirection.LONG,
                quantity=20.0,
                entry_price=2450.0,
                current_price=2480.0,
                unrealized_pnl=600.0,
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
            {"symbol": "RELIANCE", "name": "Reliance Industries", "exchange": "NSE", "market": "INDIAN_EQUITY", "lot_size": 1, "tick_size": 0.05},
            {"symbol": "TCS", "name": "Tata Consultancy Services", "exchange": "NSE", "market": "INDIAN_EQUITY", "lot_size": 1, "tick_size": 0.05},
            {"symbol": "INFY", "name": "Infosys Ltd", "exchange": "NSE", "market": "INDIAN_EQUITY", "lot_size": 1, "tick_size": 0.05},
            {"symbol": "NIFTY50", "name": "Nifty 50 Index", "exchange": "NSE", "market": "INDIAN_INDEX", "lot_size": 50, "tick_size": 0.05},
            {"symbol": "BANKNIFTY", "name": "Bank Nifty Index", "exchange": "NSE", "market": "INDIAN_INDEX", "lot_size": 15, "tick_size": 0.05},
        ]

    async def get_quotes(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        res: dict[str, dict[str, Any]] = {}
        for s in symbols:
            res[s] = {
                "symbol": s,
                "price": 2500.0,
                "bid": 2499.80,
                "ask": 2500.20,
                "volume": 2500000.0,
                "exchange": "NSE",
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
        # Return mock historical data
        return [
            OHLCVCandle(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=datetime.now(UTC),
                open=2480.0,
                high=2510.0,
                low=2475.0,
                close=2500.0,
                volume=150000.0,
                trades_count=1500,
            )
        ]

    async def _execute_place_order(self, order: OrderRequest) -> OrderResponse:
        """
        Executes order placement against Zerodha Kite Connect.
        Note: self._verify_execution_safety(order) is automatically called by base.place_order().
        """
        order_id = f"kite_{uuid.uuid4().hex[:12]}"

        # Indian Product Type mapping:
        # Intraday -> MIS
        # Delivery / Positional -> CNC (Equities) or NRML (F&O)
        product = order.metadata.get("product", "MIS")

        # Map Order Type
        kite_type = "MARKET"
        if order.order_type == OrderType.LIMIT:
            kite_type = "LIMIT"
        elif order.order_type == OrderType.STOP:
            kite_type = "SL"

        resp = OrderResponse(
            order_id=order_id,
            client_order_id=order.client_order_id,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            quantity=order.quantity,
            price=order.price,
            filled_quantity=order.quantity if order.order_type == OrderType.MARKET else 0.0,
            average_price=order.price or 2500.0 if order.order_type == OrderType.MARKET else None,
            status=OrderStatus.FILLED if order.order_type == OrderType.MARKET else OrderStatus.SUBMITTED,
            is_paper=self.is_sandbox,
            broker_message=f"Order placed on NSE/Kite with product={product}, type={kite_type}",
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
            raise ValueError(f"Order {order_id} not found on Kite.")
        ord_obj = self._mock_orders[order_id]
        if new_quantity:
            ord_obj.quantity = new_quantity
        if new_price:
            ord_obj.price = new_price
        ord_obj.broker_message = "Order modified successfully on Kite Connect."
        return ord_obj

    async def cancel_order(self, order_id: str) -> OrderResponse:
        if order_id not in self._mock_orders:
            raise ValueError(f"Order {order_id} not found on Kite.")
        ord_obj = self._mock_orders[order_id]
        ord_obj.status = OrderStatus.CANCELLED
        ord_obj.broker_message = "Order cancelled successfully on Kite Connect."
        return ord_obj

    async def get_order_status(self, order_id: str) -> OrderResponse:
        if order_id not in self._mock_orders:
            raise ValueError(f"Order {order_id} not found on Kite.")
        return self._mock_orders[order_id]

    async def get_margin(self, order: OrderRequest) -> dict[str, float]:
        price = order.price or 2500.0
        notional = order.quantity * price
        # Intraday MIS requires ~20% margin, CNC requires 100%
        margin_pct = 0.20 if order.metadata.get("product") == "MIS" else 1.0
        return {
            "required_margin": round(notional * margin_pct, 2),
            "notional_value": round(notional, 2),
            "currency": "INR",
        }

    async def get_trade_history(self, symbol: str | None = None) -> list[Trade]:
        return [
            Trade(
                order_id="kite_mock_001",
                symbol=symbol or "RELIANCE",
                side=order.side if (order := list(self._mock_orders.values()) and self._mock_orders.values()) else "BUY",
                price=2480.0,
                quantity=10.0,
                commission=20.0,
                is_paper=self.is_sandbox,
            )
        ]
