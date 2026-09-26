"""
Core domain models and schemas for AI Trading Engine.
Defines normalized market data, signals, orders, trades, positions, and risk contracts.
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ==============================================================================
# Enumerations
# ==============================================================================


class MarketType(StrEnum):
    INDIAN_EQUITY = "INDIAN_EQUITY"
    INDIAN_FNO = "INDIAN_FNO"
    CRYPTO_SPOT = "CRYPTO_SPOT"
    CRYPTO_FUTURES = "CRYPTO_FUTURES"
    FOREX = "FOREX"


class TimeFrame(StrEnum):
    M1 = "1m"
    M3 = "3m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1D"
    W1 = "1W"


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class TradeDirection(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"


class SignalDirection(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class RiskAction(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    MODIFY = "MODIFY"


# ==============================================================================
# Domain Data Models
# ==============================================================================


class OHLCVCandle(BaseModel):
    """Normalized OHLCV Bar representing historical or streaming candle."""

    model_config = ConfigDict(frozen=True)

    symbol: str = Field(..., min_length=1, description="Asset ticker e.g. 'RELIANCE', 'BTC/USDT'")
    timeframe: TimeFrame
    timestamp: datetime = Field(description="Bar opening timestamp (UTC normalized)")
    open: float = Field(..., gt=0)
    high: float = Field(..., gt=0)
    low: float = Field(..., gt=0)
    close: float = Field(..., gt=0)
    volume: float = Field(..., ge=0)
    trades_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_price_bounds(self) -> "OHLCVCandle":
        """Validate logical relationship between High, Low, Open, and Close."""
        if self.high < max(self.open, self.close):
            raise ValueError(
                f"High ({self.high}) cannot be less than Open ({self.open}) or Close ({self.close})"
            )
        if self.low > min(self.open, self.close):
            raise ValueError(
                f"Low ({self.low}) cannot be greater than Open ({self.open}) or Close ({self.close})"
            )
        if self.low > self.high:
            raise ValueError(f"Low ({self.low}) cannot exceed High ({self.high})")
        return self


class StrategySignal(BaseModel):
    """Standardized trading signal emitted by strategy modules."""

    model_config = ConfigDict(frozen=True)

    symbol: str = Field(..., min_length=1)
    timeframe: TimeFrame
    direction: SignalDirection
    entry: float = Field(..., gt=0)
    stop_loss: float = Field(..., gt=0)
    take_profit: float = Field(..., gt=0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    strategy: str = Field(..., min_length=1)
    reasons: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    market_regime: str | None = None
    extra_indicators: dict[str, float] = Field(default_factory=dict)

    @property
    def risk_reward_ratio(self) -> float:
        """Calculates risk-to-reward ratio for the signal."""
        risk_dist = abs(self.entry - self.stop_loss)
        if risk_dist <= 1e-9:
            return 0.0
        reward_dist = abs(self.take_profit - self.entry)
        return round(reward_dist / risk_dist, 4)

    @model_validator(mode="after")
    def validate_signal_levels(self) -> "StrategySignal":
        """Verify SL and TP are on the correct sides of entry based on direction."""
        if self.direction == SignalDirection.BUY:
            if self.stop_loss >= self.entry:
                raise ValueError(
                    f"BUY signal stop loss ({self.stop_loss}) must be below entry ({self.entry})"
                )
            if self.take_profit <= self.entry:
                raise ValueError(
                    f"BUY signal take profit ({self.take_profit}) must be above entry ({self.entry})"
                )
        elif self.direction == SignalDirection.SELL:
            if self.stop_loss <= self.entry:
                raise ValueError(
                    f"SELL signal stop loss ({self.stop_loss}) must be above entry ({self.entry})"
                )
            if self.take_profit >= self.entry:
                raise ValueError(
                    f"SELL signal take profit ({self.take_profit}) must be below entry ({self.entry})"
                )
        return self


class OrderRequest(BaseModel):
    """Client intent to create an order."""

    client_order_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = Field(..., min_length=1)
    side: OrderSide
    order_type: OrderType
    quantity: float = Field(..., gt=0)
    price: float | None = Field(default=None, gt=0)
    stop_price: float | None = Field(default=None, gt=0)
    time_in_force: str = Field(default="GTC")
    # Live execution MUST default to False
    live_execution: bool = Field(default=False)
    strategy_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_order_type_prices(self) -> "OrderRequest":
        """Validate that limit/stop orders have their required prices."""
        if self.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT) and self.price is None:
            raise ValueError(f"Price is required for order type {self.order_type}")
        if self.order_type in (OrderType.STOP, OrderType.STOP_LIMIT) and self.stop_price is None:
            raise ValueError(f"Stop price is required for order type {self.order_type}")
        return self


class OrderResponse(BaseModel):
    """Standardized response from execution engine or broker."""

    order_id: str
    client_order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: float | None = None
    filled_quantity: float = 0.0
    average_price: float | None = None
    status: OrderStatus
    is_paper: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    broker_message: str | None = None


class Trade(BaseModel):
    """Execution fill event."""

    trade_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str
    symbol: str
    side: OrderSide
    price: float = Field(..., gt=0)
    quantity: float = Field(..., gt=0)
    commission: float = Field(default=0.0, ge=0)
    executed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_paper: bool = True


class Position(BaseModel):
    """Open position in a portfolio."""

    symbol: str
    direction: TradeDirection
    quantity: float = Field(..., gt=0)
    entry_price: float = Field(..., gt=0)
    current_price: float = Field(..., gt=0)
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    stop_loss: float | None = None
    take_profit: float | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AccountBalance(BaseModel):
    """Account balance and margin status."""

    currency: str = "INR"
    cash: float = Field(..., ge=0)
    equity: float = Field(..., ge=0)
    initial_margin: float = Field(default=0.0, ge=0)
    maintenance_margin: float = Field(default=0.0, ge=0)
    available_margin: float = Field(..., ge=0)
    is_paper: bool = True
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
