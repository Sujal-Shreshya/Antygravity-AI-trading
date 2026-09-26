"""
Unit and integration tests for Broker / Exchange Adapters (Phase 10).
Tests:
- Zerodha Kite Connect adapter (Indian equities & F&O)
- Binance adapter (Crypto Spot & Futures)
- OANDA adapter (Forex v20)
- Broker factory dynamic resolution
- Strict safety enforcement across all adapters (live trading block, kill switch block)
"""

import pytest

from backend.brokers.binance import BinanceBrokerAdapter
from backend.brokers.factory import BrokerFactory
from backend.brokers.kite import KiteBrokerAdapter
from backend.brokers.oanda import OandaBrokerAdapter
from backend.core.exceptions import KillSwitchActiveError, LiveTradingBlockedError
from backend.core.kill_switch import kill_switch
from backend.core.models import OrderRequest, OrderSide, OrderType


@pytest.fixture(autouse=True)
def reset_ks():
    kill_switch.deactivate()
    yield
    kill_switch.deactivate()


@pytest.mark.asyncio
async def test_kite_broker_adapter_lifecycle():
    adapter = KiteBrokerAdapter(is_sandbox=True)
    assert await adapter.connect() is True
    assert await adapter.is_connected() is True

    balance = await adapter.get_balance()
    assert balance.currency == "INR"
    assert balance.equity > 0

    instruments = await adapter.get_instruments()
    assert len(instruments) >= 3
    assert any(i["symbol"] == "RELIANCE" for i in instruments)

    # Valid paper order placement
    order = OrderRequest(
        symbol="RELIANCE",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=10,
        live_execution=False,
    )
    resp = await adapter.place_order(order)
    assert resp.symbol == "RELIANCE"
    assert resp.status.value in ("FILLED", "SUBMITTED")

    # Safety: Live order blocked when LIVE_TRADING=False
    live_order = OrderRequest(
        symbol="RELIANCE",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=10,
        live_execution=True,
    )
    with pytest.raises(LiveTradingBlockedError):
        await adapter.place_order(live_order)

    # Safety: Kill switch blocks orders
    kill_switch.activate(reason="Risk circuit")
    with pytest.raises(KillSwitchActiveError):
        await adapter.place_order(order)


@pytest.mark.asyncio
async def test_binance_adapter_spot_and_futures():
    spot_adapter = BinanceBrokerAdapter(is_futures=False, is_sandbox=True)
    fut_adapter = BinanceBrokerAdapter(is_futures=True, is_sandbox=True)

    assert spot_adapter._normalize_symbol("BTC/USDT") == "BTCUSDT"
    assert spot_adapter._denormalize_symbol("BTCUSDT") == "BTC/USDT"

    # Margin comparison: Futures has lower margin requirement than Spot
    order = OrderRequest(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1.0,
        price=60_000.0,
    )
    spot_margin = await spot_adapter.get_margin(order)
    fut_margin = await fut_adapter.get_margin(order)

    assert spot_margin["required_margin"] == 60_000.0  # 100% notional
    assert fut_margin["required_margin"] == 6_000.0    # 10% notional (10x leverage)


@pytest.mark.asyncio
async def test_oanda_forex_adapter():
    adapter = OandaBrokerAdapter(is_sandbox=True)
    assert adapter._normalize_instrument("EUR/USD") == "EUR_USD"
    assert adapter._denormalize_instrument("EUR_USD") == "EUR/USD"

    quotes = await adapter.get_quotes(["EUR/USD"])
    assert "EUR/USD" in quotes
    assert quotes["EUR/USD"]["bid"] < quotes["EUR/USD"]["ask"]

    # Safety: Live order blocked
    live_order = OrderRequest(
        symbol="EUR/USD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=10_000,
        live_execution=True,
    )
    with pytest.raises(LiveTradingBlockedError):
        await adapter.place_order(live_order)


def test_broker_factory():
    kite = BrokerFactory.get_broker("KITE")
    assert isinstance(kite, KiteBrokerAdapter)

    binance = BrokerFactory.get_broker("BINANCE")
    assert isinstance(binance, BinanceBrokerAdapter)
    assert binance.is_futures is False

    binance_fut = BrokerFactory.get_broker("BINANCE_FUTURES")
    assert isinstance(binance_fut, BinanceBrokerAdapter)
    assert binance_fut.is_futures is True

    oanda = BrokerFactory.get_broker("OANDA")
    assert isinstance(oanda, OandaBrokerAdapter)

    with pytest.raises(ValueError):
        BrokerFactory.get_broker("UNSUPPORTED_BROKER")
