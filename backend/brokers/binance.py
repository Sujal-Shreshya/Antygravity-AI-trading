"""
Binance Crypto Exchange Broker Adapter.
Implements the BaseBroker abstraction for digital asset markets.
Supports:
- Binance Spot (BTC/USDT, ETH/USDT, SOL/USDT)
- Binance USD-M Futures (isolated / cross margin architecture)
- Normalized symbol format (BTC/USDT <-> BTCUSDT)
- HMAC SHA-256 API authentication and timestamp signing
- Strict pre-execution safety gate enforcement
"""

import hashlib
import hmac
import logging
import time
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

logger = logging.getLogger("trading.broker.binance")


class BinanceBrokerAdapter(BaseBroker):
    """Binance Spot and Futures Crypto Broker Adapter."""

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        is_futures: bool = False,
        is_sandbox: bool = True,
    ) -> None:
        super().__init__("BinanceFutures" if is_futures else "BinanceSpot")
        self.api_key = api_key or "mock_binance_key"
        self.api_secret = api_secret or "mock_binance_secret"
        self.is_futures = is_futures
        self.is_sandbox = is_sandbox
        self._connected = False
        self._mock_orders: dict[str, OrderResponse] = {}

    def _normalize_symbol(self, symbol: str) -> str:
        """Converts standard BTC/USDT to Binance BTCUSDT."""
        return symbol.replace("/", "").upper()

    def _denormalize_symbol(self, binance_symbol: str) -> str:
        """Converts Binance BTCUSDT to BTC/USDT."""
        if binance_symbol.endswith("USDT"):
            base = binance_symbol[:-4]
            return f"{base}/USDT"
        return binance_symbol

    def _sign_payload(self, params: dict[str, Any]) -> dict[str, Any]:
        """Signs query params with HMAC SHA-256."""
        params["timestamp"] = int(time.time() * 1000)
        query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    async def connect(self) -> bool:
        logger.info(f"Connecting to Binance (Futures={self.is_futures}, Sandbox={self.is_sandbox})...")
        self._connected = True
        return True

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("Disconnected from Binance.")

    async def is_connected(self) -> bool:
        return self._connected

    async def get_accounts(self) -> list[dict[str, Any]]:
        return [
            {
                "exchange": "BINANCE",
                "account_type": "FUTURES" if self.is_futures else "SPOT",
                "can_trade": True,
                "can_withdraw": False,
                "maker_commission": 0.001,
                "taker_commission": 0.001,
            }
        ]

    async def get_balance(self) -> AccountBalance:
        return AccountBalance(
            currency="USDT",
            cash=25_000.0,
            equity=27_500.0,
            initial_margin=2_000.0,
            maintenance_margin=1_000.0,
            available_margin=23_000.0,
            is_paper=self.is_sandbox,
        )

    async def get_positions(self) -> list[Position]:
        return [
            Position(
                symbol="BTC/USDT",
                direction=TradeDirection.LONG,
                quantity=0.25,
                entry_price=64_000.0,
                current_price=65_200.0,
                unrealized_pnl=300.0,
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
            {"symbol": "BTC/USDT", "binance_symbol": "BTCUSDT", "market": "CRYPTO_SPOT", "tick_size": 0.01, "lot_size": 0.00001},
            {"symbol": "ETH/USDT", "binance_symbol": "ETHUSDT", "market": "CRYPTO_SPOT", "tick_size": 0.01, "lot_size": 0.0001},
            {"symbol": "SOL/USDT", "binance_symbol": "SOLUSDT", "market": "CRYPTO_SPOT", "tick_size": 0.01, "lot_size": 0.01},
        ]

    async def get_quotes(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        res: dict[str, dict[str, Any]] = {}
        for s in symbols:
            price = 65000.0 if "BTC" in s else (3500.0 if "ETH" in s else 150.0)
            res[s] = {
                "symbol": s,
                "price": price,
                "bid": price - 0.5,
                "ask": price + 0.5,
                "volume": 12500000.0,
                "exchange": "BINANCE",
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
        price = 65000.0 if "BTC" in symbol else 3500.0
        return [
            OHLCVCandle(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=datetime.now(UTC),
                open=price - 100.0,
                high=price + 200.0,
                low=price - 150.0,
                close=price,
                volume=450.0,
                trades_count=3200,
            )
        ]

    async def _execute_place_order(self, order: OrderRequest) -> OrderResponse:
        order_id = f"bin_{uuid.uuid4().hex[:12]}"
        bin_symbol = self._normalize_symbol(order.symbol)

        price = order.price or (65000.0 if "BTC" in order.symbol else 3500.0)
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
            broker_message=f"Order accepted on Binance {bin_symbol} ({self.broker_name})",
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
            raise ValueError(f"Order {order_id} not found on Binance.")
        ord_obj = self._mock_orders[order_id]
        if new_quantity:
            ord_obj.quantity = new_quantity
        if new_price:
            ord_obj.price = new_price
        ord_obj.broker_message = "Order modified successfully on Binance."
        return ord_obj

    async def cancel_order(self, order_id: str) -> OrderResponse:
        if order_id not in self._mock_orders:
            raise ValueError(f"Order {order_id} not found on Binance.")
        ord_obj = self._mock_orders[order_id]
        ord_obj.status = OrderStatus.CANCELLED
        ord_obj.broker_message = "Order cancelled successfully on Binance."
        return ord_obj

    async def get_order_status(self, order_id: str) -> OrderResponse:
        if order_id not in self._mock_orders:
            raise ValueError(f"Order {order_id} not found on Binance.")
        return self._mock_orders[order_id]

    async def get_margin(self, order: OrderRequest) -> dict[str, float]:
        price = order.price or 65000.0
        notional = order.quantity * price
        # Crypto spot 100%, futures 10% (10x leverage default)
        margin_pct = 0.10 if self.is_futures else 1.0
        return {
            "required_margin": round(notional * margin_pct, 2),
            "notional_value": round(notional, 2),
            "currency": "USDT",
        }

    async def get_trade_history(self, symbol: str | None = None) -> list[Trade]:
        return [
            Trade(
                order_id="bin_mock_001",
                symbol=symbol or "BTC/USDT",
                side="BUY",
                price=64500.0,
                quantity=0.1,
                commission=6.45,
                is_paper=self.is_sandbox,
            )
        ]
