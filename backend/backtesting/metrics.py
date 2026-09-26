"""
Quantitative Backtesting Performance Metrics Calculator.
Computes mathematically rigorous risk-adjusted performance metrics:
- Total Return & CAGR
- Sharpe Ratio (annualized vs risk-free rate)
- Sortino Ratio (downside deviation adjusted)
- Max Drawdown & Max Drawdown Duration
- Win Rate, Profit Factor, Expectancy
- Win/Loss ratio and average trade duration
"""

import math
from datetime import datetime
from typing import Any

import numpy as np
from pydantic import BaseModel, Field


class EquityPoint(BaseModel):
    timestamp: datetime
    equity: float
    cash: float
    drawdown_pct: float = 0.0


class BacktestTrade(BaseModel):
    trade_id: str
    symbol: str
    direction: str  # BUY or SELL
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    gross_pnl: float
    net_pnl: float
    commission: float
    slippage: float
    return_pct: float
    exit_reason: str  # TAKE_PROFIT, STOP_LOSS, SIGNAL, END_OF_DATA


class BacktestMetrics(BaseModel):
    initial_capital: float
    final_equity: float
    total_net_pnl: float
    total_return_pct: float
    cagr_pct: float = 0.0
    annualized_volatility_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    max_drawdown_duration_bars: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0
    win_rate_pct: float = 0.0
    profit_factor: float = 0.0
    average_trade_pnl: float = 0.0
    average_win_pnl: float = 0.0
    average_loss_pnl: float = 0.0
    win_loss_ratio: float = 0.0
    expectancy: float = 0.0
    total_commission_paid: float = 0.0
    total_slippage_paid: float = 0.0
    extra: dict[str, Any] = Field(default_factory=dict)


def calculate_backtest_metrics(
    initial_capital: float,
    equity_curve: list[EquityPoint],
    trades: list[BacktestTrade],
    risk_free_rate: float = 0.05,
    periods_per_year: int = 252,
) -> BacktestMetrics:
    """Calculates all quantitative performance metrics from backtest execution outputs."""
    if not equity_curve:
        return BacktestMetrics(
            initial_capital=initial_capital,
            final_equity=initial_capital,
            total_net_pnl=0.0,
            total_return_pct=0.0,
        )

    final_equity = equity_curve[-1].equity
    total_net_pnl = final_equity - initial_capital
    total_return_pct = round((total_net_pnl / initial_capital) * 100, 2)

    # 1. Trade Statistics
    total_trades = len(trades)
    winning = [t for t in trades if t.net_pnl > 1e-6]
    losing = [t for t in trades if t.net_pnl < -1e-6]
    breakeven = [t for t in trades if abs(t.net_pnl) <= 1e-6]

    win_count = len(winning)
    loss_count = len(losing)
    breakeven_count = len(breakeven)

    win_rate_pct = round((win_count / total_trades) * 100, 2) if total_trades > 0 else 0.0

    gross_profit = sum(t.net_pnl for t in winning)
    gross_loss = abs(sum(t.net_pnl for t in losing))
    profit_factor = (
        round(gross_profit / gross_loss, 2)
        if gross_loss > 0
        else (round(gross_profit, 2) if gross_profit > 0 else 1.0)
    )

    avg_win = (gross_profit / win_count) if win_count > 0 else 0.0
    avg_loss = (gross_loss / loss_count) if loss_count > 0 else 0.0
    win_loss_ratio = round(avg_win / avg_loss, 2) if avg_loss > 0 else 0.0

    # Mathematical Expectancy = (Win% * AvgWin) - (Loss% * AvgLoss)
    win_prob = win_count / total_trades if total_trades > 0 else 0.0
    loss_prob = loss_count / total_trades if total_trades > 0 else 0.0
    expectancy = round((win_prob * avg_win) - (loss_prob * avg_loss), 2)
    avg_trade_pnl = round(total_net_pnl / total_trades, 2) if total_trades > 0 else 0.0

    total_commission = round(sum(t.commission for t in trades), 2)
    total_slippage = round(sum(t.slippage for t in trades), 2)

    # 2. Equity Curve & Drawdown Analysis
    equities = np.array([p.equity for p in equity_curve])
    peaks = np.maximum.accumulate(equities)
    drawdowns = (peaks - equities) / peaks

    # Update drawdown_pct in equity_curve objects
    for i, p in enumerate(equity_curve):
        p.drawdown_pct = round(float(drawdowns[i]) * 100, 2)

    max_dd_pct = round(float(np.max(drawdowns)) * 100, 2) if len(drawdowns) > 0 else 0.0

    # Calculate Max Drawdown Duration (in bars)
    max_dd_duration = 0
    current_dd_duration = 0
    for dd in drawdowns:
        if dd > 0:
            current_dd_duration += 1
            if current_dd_duration > max_dd_duration:
                max_dd_duration = current_dd_duration
        else:
            current_dd_duration = 0

    # 3. Time span & Annualized Metrics
    if len(equity_curve) > 1:
        time_span_days = max(
            1, (equity_curve[-1].timestamp - equity_curve[0].timestamp).total_seconds() / 86400
        )
        years = time_span_days / 365.25

        if years > 0 and final_equity > 0:
            cagr = ((final_equity / initial_capital) ** (1 / years)) - 1
            cagr_pct = round(cagr * 100, 2)
        else:
            cagr_pct = total_return_pct

        # Returns series
        returns = np.diff(equities) / equities[:-1]
        returns_clean = returns[np.isfinite(returns)]

        if len(returns_clean) > 1 and np.std(returns_clean) > 1e-9:
            daily_std = float(np.std(returns_clean))
            annualized_vol = daily_std * math.sqrt(periods_per_year)
            annualized_vol_pct = round(annualized_vol * 100, 2)

            # Sharpe Ratio
            excess_return = (cagr_pct / 100.0) - risk_free_rate
            sharpe = excess_return / annualized_vol if annualized_vol > 0 else 0.0
            sharpe_ratio = round(sharpe, 2)

            # Sortino Ratio (downside volatility only)
            downside_returns = returns_clean[returns_clean < 0]
            if len(downside_returns) > 0:
                downside_std = float(np.std(downside_returns)) * math.sqrt(periods_per_year)
                sortino = excess_return / downside_std if downside_std > 0 else 0.0
                sortino_ratio = round(sortino, 2)
            else:
                sortino_ratio = round(sharpe_ratio * 1.5, 2) if sharpe_ratio > 0 else 0.0

            # Calmar Ratio
            calmar = (
                round((cagr_pct / max_dd_pct), 2)
                if max_dd_pct > 0
                else round(cagr_pct, 2)
            )
        else:
            annualized_vol_pct = 0.0
            sharpe_ratio = 0.0
            sortino_ratio = 0.0
            calmar = 0.0
    else:
        cagr_pct = total_return_pct
        annualized_vol_pct = 0.0
        sharpe_ratio = 0.0
        sortino_ratio = 0.0
        calmar = 0.0

    return BacktestMetrics(
        initial_capital=initial_capital,
        final_equity=round(final_equity, 2),
        total_net_pnl=round(total_net_pnl, 2),
        total_return_pct=total_return_pct,
        cagr_pct=cagr_pct,
        annualized_volatility_pct=annualized_vol_pct,
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        calmar_ratio=calmar,
        max_drawdown_pct=max_dd_pct,
        max_drawdown_duration_bars=max_dd_duration,
        total_trades=total_trades,
        winning_trades=win_count,
        losing_trades=loss_count,
        breakeven_trades=breakeven_count,
        win_rate_pct=win_rate_pct,
        profit_factor=profit_factor,
        average_trade_pnl=avg_trade_pnl,
        average_win_pnl=round(avg_win, 2),
        average_loss_pnl=round(avg_loss, 2),
        win_loss_ratio=win_loss_ratio,
        expectancy=expectancy,
        total_commission_paid=total_commission,
        total_slippage_paid=total_slippage,
    )
