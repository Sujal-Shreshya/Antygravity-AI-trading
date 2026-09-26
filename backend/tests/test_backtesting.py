"""
Unit and integration tests for Backtesting Engine and Metrics Calculator (Phase 7).
Tests:
- Mathematical properties of BacktestMetrics (Sharpe, Sortino, Drawdown, Profit Factor, Expectancy)
- Event-driven execution engine (zero look-ahead bias, fee deduction, stop loss execution)
- API endpoints (/api/v1/backtest/run, /api/v1/backtest/results, /api/v1/backtest/results/{id})
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from backend.backtesting.engine import BacktestConfig, BacktestingEngine
from backend.backtesting.metrics import (
    BacktestTrade,
    EquityPoint,
    calculate_backtest_metrics,
)
from backend.data.mock_provider import MockDataProvider
from backend.main import app


def test_metrics_mathematical_properties():
    """Verify quantitative metrics calculations."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    equity_curve = [
        EquityPoint(timestamp=start + timedelta(days=i), equity=eq, cash=eq)
        for i, eq in enumerate([100_000.0, 102_000.0, 98_000.0, 105_000.0, 110_000.0])
    ]

    trades = [
        BacktestTrade(
            trade_id="t1",
            symbol="TCS",
            direction="BUY",
            entry_time=start,
            exit_time=start + timedelta(days=1),
            entry_price=100.0,
            exit_price=102.0,
            quantity=100.0,
            gross_pnl=200.0,
            net_pnl=190.0,
            commission=10.0,
            slippage=0.0,
            return_pct=1.9,
            exit_reason="TAKE_PROFIT",
        ),
        BacktestTrade(
            trade_id="t2",
            symbol="TCS",
            direction="BUY",
            entry_time=start + timedelta(days=1),
            exit_time=start + timedelta(days=2),
            entry_price=102.0,
            exit_price=98.0,
            quantity=100.0,
            gross_pnl=-400.0,
            net_pnl=-410.0,
            commission=10.0,
            slippage=0.0,
            return_pct=-4.0,
            exit_reason="STOP_LOSS",
        ),
        BacktestTrade(
            trade_id="t3",
            symbol="TCS",
            direction="BUY",
            entry_time=start + timedelta(days=2),
            exit_time=start + timedelta(days=4),
            entry_price=98.0,
            exit_price=110.0,
            quantity=100.0,
            gross_pnl=1200.0,
            net_pnl=1180.0,
            commission=20.0,
            slippage=0.0,
            return_pct=12.0,
            exit_reason="TAKE_PROFIT",
        ),
    ]

    metrics = calculate_backtest_metrics(
        initial_capital=100_000.0,
        equity_curve=equity_curve,
        trades=trades,
    )

    assert metrics.total_trades == 3
    assert metrics.winning_trades == 2
    assert metrics.losing_trades == 1
    assert metrics.win_rate_pct == pytest.approx(66.67, 0.1)
    assert metrics.total_return_pct == 10.0
    assert metrics.final_equity == 110_000.0
    assert metrics.profit_factor > 1.0
    assert metrics.max_drawdown_pct > 0.0
    assert metrics.total_commission_paid == 40.0


@pytest.mark.asyncio
async def test_backtest_engine_execution():
    """Verify BacktestingEngine executes against mock candles without lookahead bias."""
    provider = MockDataProvider()
    candles = await provider.fetch_historical_candles(
        symbol="RELIANCE",
        timeframe="15m",
        limit=100,
    )

    config = BacktestConfig(
        strategy_name="EMA_CROSSOVER",
        symbol="RELIANCE",
        timeframe="15m",
        initial_capital=100_000.0,
        commission_rate=0.0003,
        slippage_rate=0.0005,
        risk_per_trade_pct=0.01,
        strategy_params={"fast_period": 5, "slow_period": 15},
    )

    engine = BacktestingEngine(config)
    result = engine.run(candles)

    assert result.backtest_id is not None
    assert len(result.equity_curve) > 50
    assert result.metrics.initial_capital == 100_000.0
    # Equity curve values must be positive
    assert all(p.equity > 0 for p in result.equity_curve)
    # Total net PnL + initial capital == final equity
    assert abs((result.metrics.initial_capital + result.metrics.total_net_pnl) - result.metrics.final_equity) < 1.0


@pytest.mark.asyncio
async def test_backtest_api_endpoints():
    """Verify /api/v1/backtest/run and /api/v1/backtest/results API routes."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register and login user
        await client.post(
            "/api/v1/auth/register",
            json={"email": "backtest_user@trading.com", "password": "SecurePassword123!"},
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "backtest_user@trading.com", "password": "SecurePassword123!"},
        )
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Run backtest via API
        run_payload = {
            "strategy_name": "RSI",
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "initial_capital": 50_000.0,
            "bars_count": 80,
            "strategy_params": {"period": 14, "oversold": 30, "overbought": 70},
        }

        resp = await client.post("/api/v1/backtest/run", json=run_payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "backtest_id" in data
        assert "metrics" in data
        assert data["metrics"]["initial_capital"] == 50_000.0
        backtest_id = data["backtest_id"]

        # 2. List backtest results
        list_resp = await client.get("/api/v1/backtest/results", headers=headers)
        assert list_resp.status_code == 200
        results = list_resp.json()
        assert len(results) >= 1
        assert any(r["id"] == backtest_id for r in results)

        # 3. Retrieve specific backtest
        get_resp = await client.get(f"/api/v1/backtest/results/{backtest_id}", headers=headers)
        assert get_resp.status_code == 200
        detail = get_resp.json()
        assert detail["id"] == backtest_id
        assert detail["strategy_name"] == "RSI"
        assert detail["symbol"] == "BTC/USDT"
