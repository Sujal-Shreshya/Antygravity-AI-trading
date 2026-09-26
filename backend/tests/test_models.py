"""
Unit tests for domain models, data validation, and invariant enforcement.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.core.models import (
    AccountBalance,
    OHLCVCandle,
    OrderRequest,
    OrderSide,
    OrderType,
    Position,
    SignalDirection,
    StrategySignal,
    TimeFrame,
    TradeDirection,
)


def test_valid_ohlcv_candle():
    """Verify standard valid OHLCV candle creates successfully."""
    candle = OHLCVCandle(
        symbol="NIFTY",
        timeframe=TimeFrame.M5,
        timestamp=datetime.now(UTC),
        open=22000.0,
        high=22050.0,
        low=21980.0,
        close=22020.0,
        volume=150000.0,
    )
    assert candle.symbol == "NIFTY"
    assert candle.high >= candle.open
    assert candle.low <= candle.close


def test_invalid_ohlcv_bounds():
    """Verify invalid candle price bounds raise ValidationError."""
    # High is less than Open
    with pytest.raises(ValidationError):
        OHLCVCandle(
            symbol="NIFTY",
            timeframe=TimeFrame.M5,
            timestamp=datetime.now(UTC),
            open=22000.0,
            high=21950.0,  # invalid: high < open
            low=21900.0,
            close=21920.0,
            volume=100.0,
        )

    # Low is greater than Close
    with pytest.raises(ValidationError):
        OHLCVCandle(
            symbol="NIFTY",
            timeframe=TimeFrame.M5,
            timestamp=datetime.now(UTC),
            open=22000.0,
            high=22100.0,
            low=22050.0,  # invalid: low > open & close
            close=22020.0,
            volume=100.0,
        )


def test_strategy_signal_buy_validation():
    """Verify BUY signal validation and risk/reward calculation."""
    # Valid BUY signal: SL < Entry < TP
    signal = StrategySignal(
        symbol="BTC/USDT",
        timeframe=TimeFrame.M15,
        direction=SignalDirection.BUY,
        entry=65000.0,
        stop_loss=64000.0,  # 1000 risk
        take_profit=67500.0,  # 2500 reward
        confidence=0.85,
        strategy="EMA_CROSSOVER",
        reasons=["Golden cross on 15m", "RSI divergence"],
    )
    assert signal.risk_reward_ratio == 2.5

    # Invalid BUY signal: SL >= Entry
    with pytest.raises(ValidationError):
        StrategySignal(
            symbol="BTC/USDT",
            timeframe=TimeFrame.M15,
            direction=SignalDirection.BUY,
            entry=65000.0,
            stop_loss=65500.0,  # invalid: SL > entry
            take_profit=68000.0,
            confidence=0.9,
            strategy="EMA_CROSSOVER",
        )


def test_strategy_signal_sell_validation():
    """Verify SELL signal validation."""
    # Valid SELL signal: TP < Entry < SL
    signal = StrategySignal(
        symbol="EUR/USD",
        timeframe=TimeFrame.H1,
        direction=SignalDirection.SELL,
        entry=1.0850,
        stop_loss=1.0900,  # 50 pips risk
        take_profit=1.0750,  # 100 pips reward
        confidence=0.75,
        strategy="MACD",
        reasons=["Bearish crossover"],
    )
    assert signal.risk_reward_ratio == 2.0

    # Invalid SELL signal: TP >= Entry
    with pytest.raises(ValidationError):
        StrategySignal(
            symbol="EUR/USD",
            timeframe=TimeFrame.H1,
            direction=SignalDirection.SELL,
            entry=1.0850,
            stop_loss=1.0900,
            take_profit=1.0860,  # invalid: TP > entry for SELL
            confidence=0.75,
            strategy="MACD",
        )


def test_order_request_validation():
    """Verify order type pricing requirements."""
    # Market order without price is valid
    market_order = OrderRequest(
        symbol="TATASTEEL",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=50,
    )
    assert market_order.price is None
    assert market_order.live_execution is False

    # Limit order without price raises ValidationError
    with pytest.raises(ValidationError):
        OrderRequest(
            symbol="TATASTEEL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=50,
            price=None,  # limit order requires price
        )

    # Stop order without stop price raises ValidationError
    with pytest.raises(ValidationError):
        OrderRequest(
            symbol="TATASTEEL",
            side=OrderSide.SELL,
            order_type=OrderType.STOP,
            quantity=50,
            stop_price=None,  # stop order requires stop_price
        )


def test_position_and_balance_models():
    """Verify Position and AccountBalance instantiation."""
    pos = Position(
        symbol="RELIANCE",
        direction=TradeDirection.LONG,
        quantity=25,
        entry_price=2900.0,
        current_price=2950.0,
        unrealized_pnl=1250.0,
        realized_pnl=0.0,
        updated_at=datetime.now(UTC),
    )
    assert pos.unrealized_pnl == 1250.0

    balance = AccountBalance(
        currency="INR",
        cash=500000.0,
        equity=512500.0,
        available_margin=427500.0,
        is_paper=True,
        updated_at=datetime.now(UTC),
    )
    assert balance.equity == 512500.0
    assert balance.is_paper is True
