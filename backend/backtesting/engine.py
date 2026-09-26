"""
Event-Driven Backtesting Engine.
Executes strategies sequentially through historical OHLCV data bars with:
- Strict zero look-ahead bias
- Realistic transaction fees (commissions) and slippage modeling
- Intrabar stop-loss and take-profit fill evaluation
- 1% per-trade risk position sizing
- Comprehensive performance metric calculation
"""

import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field

from backend.backtesting.metrics import (
    BacktestMetrics,
    BacktestTrade,
    EquityPoint,
    calculate_backtest_metrics,
)
from backend.core.models import OHLCVCandle, SignalDirection
from backend.strategies.base import BaseStrategy
from backend.strategies.registry import strategy_registry

logger = logging.getLogger("trading.backtesting.engine")


class BacktestConfig(BaseModel):
    strategy_name: str
    symbol: str
    timeframe: str
    initial_capital: float = 100_000.0
    commission_rate: float = 0.0003  # 0.03% per trade
    slippage_rate: float = 0.0005  # 0.05% slippage
    risk_per_trade_pct: float = 0.01  # 1% capital risk per trade
    strategy_params: dict[str, Any] = Field(default_factory=dict)


class BacktestRunResult(BaseModel):
    backtest_id: str
    config: BacktestConfig
    metrics: BacktestMetrics
    trades: list[BacktestTrade]
    equity_curve: list[EquityPoint]


class BacktestingEngine:
    """Zero look-ahead bias event-driven backtesting execution engine."""

    def __init__(self, config: BacktestConfig) -> None:
        self.config = config

    def run(self, candles: list[OHLCVCandle]) -> BacktestRunResult:
        """Runs the backtest simulation across the supplied historical candle series."""
        if len(candles) < 30:
            raise ValueError(f"Insufficient candle data: minimum 30 bars required, received {len(candles)}")

        # Instantiate strategy
        strategy: BaseStrategy = strategy_registry.get_strategy(
            self.config.strategy_name,
            self.config.strategy_params,
        )

        cash = self.config.initial_capital
        equity = cash
        equity_curve: list[EquityPoint] = []
        trades: list[BacktestTrade] = []

        # Current open position tracking
        open_pos: dict[str, Any] | None = None

        # Warm-up period (need enough bars for 20/26 period indicators)
        warmup_bars = 25

        for i in range(warmup_bars, len(candles)):
            current_bar = candles[i]
            history_slice = candles[: i + 1]

            # 1. Intrabar Stop Loss / Take Profit evaluation for active position
            if open_pos is not None:
                pos_dir = open_pos["direction"]
                sl = open_pos["stop_loss"]
                tp = open_pos["take_profit"]
                exit_price = None
                exit_reason = None

                if pos_dir == "BUY":
                    # Check Stop Loss breach
                    if sl and current_bar.low <= sl:
                        exit_price = sl * (1.0 - self.config.slippage_rate)
                        exit_reason = "STOP_LOSS"
                    # Check Take Profit breach
                    elif tp and current_bar.high >= tp:
                        exit_price = tp * (1.0 - self.config.slippage_rate)
                        exit_reason = "TAKE_PROFIT"
                elif pos_dir == "SELL":
                    if sl and current_bar.high >= sl:
                        exit_price = sl * (1.0 + self.config.slippage_rate)
                        exit_reason = "STOP_LOSS"
                    elif tp and current_bar.low <= tp:
                        exit_price = tp * (1.0 + self.config.slippage_rate)
                        exit_reason = "TAKE_PROFIT"

                if exit_price is not None and exit_reason is not None:
                    # Close position
                    trade = self._close_position(
                        open_pos,
                        exit_price=exit_price,
                        exit_time=current_bar.timestamp,
                        exit_reason=exit_reason,
                    )
                    trades.append(trade)
                    cash += (open_pos["quantity"] * exit_price) - trade.commission
                    open_pos = None

            # 2. Strategy Signal Generation (no future bars referenced)
            signals = strategy.generate_signals(history_slice)
            signal = signals[-1] if signals else None

            if signal and signal.direction != SignalDirection.HOLD:
                current_price = current_bar.close

                # If existing position is contrary to signal, close it first
                if open_pos is not None:
                    if (open_pos["direction"] == "BUY" and signal.direction == SignalDirection.SELL) or (
                        open_pos["direction"] == "SELL" and signal.direction == SignalDirection.BUY
                    ):
                        slip = -self.config.slippage_rate if open_pos["direction"] == "BUY" else self.config.slippage_rate
                        exit_p = current_price * (1.0 + slip)
                        trade = self._close_position(
                            open_pos,
                            exit_price=exit_p,
                            exit_time=current_bar.timestamp,
                            exit_reason="SIGNAL_REVERSAL",
                        )
                        trades.append(trade)
                        cash += (open_pos["quantity"] * exit_p) - trade.commission
                        open_pos = None

                # Open new position if flat
                if open_pos is None:
                    # 1% per-trade risk sizing
                    equity_now = cash
                    risk_amount = equity_now * self.config.risk_per_trade_pct
                    risk_dist = abs(signal.entry - signal.stop_loss)

                    if risk_dist > 1e-4:
                        raw_qty = risk_amount / risk_dist
                    else:
                        raw_qty = (equity_now * 0.1) / current_price

                    # Cap maximum single trade exposure to 15% equity
                    max_notional = equity_now * 0.15
                    max_allowed_qty = max_notional / current_price
                    qty = min(raw_qty, max_allowed_qty)

                    # Ensure integer or micro lots within cash
                    qty = round(qty, 2)
                    if qty > 0 and (qty * current_price) <= cash:
                        slippage_mult = 1.0 + self.config.slippage_rate if signal.direction == SignalDirection.BUY else 1.0 - self.config.slippage_rate
                        entry_price = current_price * slippage_mult
                        commission = (qty * entry_price) * self.config.commission_rate
                        slippage_val = abs(entry_price - current_price) * qty

                        cash -= (qty * entry_price) + commission

                        open_pos = {
                            "trade_id": str(uuid.uuid4())[:8],
                            "direction": signal.direction.value,
                            "entry_time": current_bar.timestamp,
                            "entry_price": entry_price,
                            "quantity": qty,
                            "stop_loss": signal.stop_loss,
                            "take_profit": signal.take_profit,
                            "entry_commission": commission,
                            "entry_slippage": slippage_val,
                        }

            # 3. Mark to Market Equity calculation
            if open_pos is not None:
                if open_pos["direction"] == "BUY":
                    pos_val = open_pos["quantity"] * current_bar.close
                else:
                    pos_val = open_pos["quantity"] * (2 * open_pos["entry_price"] - current_bar.close)
                equity = cash + pos_val
            else:
                equity = cash

            equity_curve.append(
                EquityPoint(
                    timestamp=current_bar.timestamp,
                    equity=round(equity, 2),
                    cash=round(cash, 2),
                )
            )

        # 4. Final closeout if position remains open at end of data
        if open_pos is not None:
            final_bar = candles[-1]
            trade = self._close_position(
                open_pos,
                exit_price=final_bar.close,
                exit_time=final_bar.timestamp,
                exit_reason="END_OF_DATA",
            )
            trades.append(trade)
            cash += (open_pos["quantity"] * final_bar.close) - trade.commission
            equity = cash
            if equity_curve:
                equity_curve[-1].equity = round(equity, 2)
                equity_curve[-1].cash = round(cash, 2)

        # Calculate metrics
        metrics = calculate_backtest_metrics(
            initial_capital=self.config.initial_capital,
            equity_curve=equity_curve,
            trades=trades,
        )

        return BacktestRunResult(
            backtest_id=str(uuid.uuid4()),
            config=self.config,
            metrics=metrics,
            trades=trades,
            equity_curve=equity_curve,
        )

    def _close_position(
        self,
        pos: dict[str, Any],
        exit_price: float,
        exit_time: Any,
        exit_reason: str,
    ) -> BacktestTrade:
        qty = pos["quantity"]
        entry_p = pos["entry_price"]
        dir_mult = 1.0 if pos["direction"] == "BUY" else -1.0

        gross_pnl = (exit_price - entry_p) * qty * dir_mult
        exit_commission = (qty * exit_price) * self.config.commission_rate
        total_commission = pos["entry_commission"] + exit_commission
        exit_slippage = (qty * exit_price) * self.config.slippage_rate
        total_slippage = pos["entry_slippage"] + exit_slippage

        net_pnl = gross_pnl - total_commission - total_slippage
        return_pct = round((net_pnl / (entry_p * qty)) * 100, 2)

        return BacktestTrade(
            trade_id=pos["trade_id"],
            symbol=self.config.symbol,
            direction=pos["direction"],
            entry_time=pos["entry_time"],
            exit_time=exit_time,
            entry_price=round(entry_p, 4),
            exit_price=round(exit_price, 4),
            quantity=qty,
            gross_pnl=round(gross_pnl, 2),
            net_pnl=round(net_pnl, 2),
            commission=round(total_commission, 2),
            slippage=round(total_slippage, 2),
            return_pct=return_pct,
            exit_reason=exit_reason,
        )
