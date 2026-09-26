import React, { useState } from "react";
import {
  Award,
  BarChart2,
  Calendar,
  CheckCircle,
  Play,
  Shield,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { EquityCurveChart } from "../charts/EquityCurveChart";
import { StatsCard } from "../components/StatsCard";
import { api } from "../services/api";
import { BacktestResult } from "../types";

export const BacktestPage: React.FC = () => {
  const [strategy, setStrategy] = useState("EMA_CROSSOVER");
  const [symbol, setSymbol] = useState("RELIANCE");
  const [timeframe, setTimeframe] = useState("15m");
  const [capital, setCapital] = useState(100000);
  const [barsCount, setBarsCount] = useState(120);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRunBacktest = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await api.runBacktest({
        strategy_name: strategy,
        symbol,
        timeframe,
        initial_capital: capital,
        bars_count: barsCount,
        commission_rate: 0.0003,
        slippage_rate: 0.0005,
        risk_per_trade_pct: 0.01,
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message || "Failed to execute backtest");
    } finally {
      setLoading(false);
    }
  };

  const metrics = result?.metrics;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="border-b border-dark-700 pb-4">
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <BarChart2 className="w-5 h-5 text-cyan-400" />
          Event-Driven Backtesting Sandbox
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          Zero look-ahead bias strategy simulation with realistic transaction commissions (0.03%), slippage (0.05%), and 1% risk position sizing.
        </p>
      </div>

      {/* Configuration Form */}
      <form
        onSubmit={handleRunBacktest}
        className="bg-dark-800 border border-dark-700 rounded-xl p-5 shadow-xl space-y-4"
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
              Strategy
            </label>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="w-full bg-dark-900 border border-dark-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none"
            >
              {[
                "EMA_CROSSOVER",
                "SMA_CROSSOVER",
                "RSI",
                "MACD",
                "BOLLINGER_BANDS",
                "VWAP",
                "BREAKOUT",
                "MOMENTUM",
                "TREND_FOLLOWING",
                "MEAN_REVERSION",
              ].map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
              Symbol
            </label>
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="w-full bg-dark-900 border border-dark-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none"
            >
              {["RELIANCE", "TCS", "INFY", "BTC/USDT", "ETH/USDT", "EUR/USD"].map((sym) => (
                <option key={sym} value={sym}>{sym}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
              Timeframe
            </label>
            <select
              value={timeframe}
              onChange={(e) => setTimeframe(e.target.value)}
              className="w-full bg-dark-900 border border-dark-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none"
            >
              {["5m", "15m", "1h", "4h", "1D"].map((tf) => (
                <option key={tf} value={tf}>{tf}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
              Initial Capital (₹)
            </label>
            <input
              type="number"
              value={capital}
              onChange={(e) => setCapital(parseFloat(e.target.value) || 100000)}
              className="w-full bg-dark-900 border border-dark-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
              Bars Count
            </label>
            <input
              type="number"
              min="30"
              max="500"
              value={barsCount}
              onChange={(e) => setBarsCount(parseInt(e.target.value) || 100)}
              className="w-full bg-dark-900 border border-dark-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none"
            />
          </div>
        </div>

        {error && (
          <div className="p-2.5 rounded bg-red-950/60 border border-red-800 text-xs text-red-400">
            {error}
          </div>
        )}

        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={loading}
            className="px-6 py-2.5 bg-cyan-500 hover:bg-cyan-400 text-black font-bold text-xs uppercase tracking-wider rounded-lg shadow-lg shadow-cyan-500/20 flex items-center space-x-2 transition"
          >
            <Play className="w-4 h-4 fill-black" />
            <span>{loading ? "Simulating Execution..." : "Run Backtest Simulation"}</span>
          </button>
        </div>
      </form>

      {/* Results Section */}
      {result && metrics && (
        <div className="space-y-6">
          {/* Key Metrics Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatsCard
              title="Total Return"
              value={`${metrics.total_return_pct >= 0 ? "+" : ""}${metrics.total_return_pct}%`}
              subtext={`₹${metrics.total_net_pnl.toFixed(2)} Net P&L`}
              icon={metrics.total_return_pct >= 0 ? TrendingUp : TrendingDown}
              variant={metrics.total_return_pct >= 0 ? "success" : "danger"}
            />
            <StatsCard
              title="Win Rate"
              value={`${metrics.win_rate_pct}%`}
              subtext={`${metrics.winning_trades}W / ${metrics.losing_trades}L (${metrics.total_trades} trades)`}
              icon={Award}
              variant={metrics.win_rate_pct >= 50 ? "success" : "warning"}
            />
            <StatsCard
              title="Sharpe Ratio"
              value={metrics.sharpe_ratio.toFixed(2)}
              subtext={`Sortino: ${metrics.sortino_ratio.toFixed(2)}`}
              icon={Shield}
              variant={metrics.sharpe_ratio > 1 ? "success" : "default"}
            />
            <StatsCard
              title="Max Drawdown"
              value={`${metrics.max_drawdown_pct}%`}
              subtext={`Duration: ${metrics.max_drawdown_duration_bars} bars`}
              icon={TrendingDown}
              variant={metrics.max_drawdown_pct < 10 ? "default" : "danger"}
            />
          </div>

          {/* Equity Curve Visualizer */}
          <div className="bg-dark-800 border border-dark-700 rounded-xl p-5 shadow-xl space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                Equity Curve & Portfolio Growth (₹)
              </h3>
              <span className="text-xs font-mono text-slate-400">
                Final Equity: <strong className="text-white">₹{metrics.final_equity.toLocaleString()}</strong>
              </span>
            </div>
            <EquityCurveChart data={result.equity_curve} initialCapital={capital} />
          </div>

          {/* Trade Execution Audit Log */}
          <div className="bg-dark-800 border border-dark-700 rounded-xl overflow-hidden shadow-xl">
            <div className="p-4 border-b border-dark-700 font-bold text-sm text-white">
              Simulated Execution Trades ({result.trades.length})
            </div>
            <div className="overflow-x-auto max-h-60">
              <table className="w-full text-left text-xs">
                <thead className="bg-dark-900/60 text-slate-400 uppercase font-semibold">
                  <tr>
                    <th className="py-2.5 px-4">Direction</th>
                    <th className="py-2.5 px-4 text-right">Entry</th>
                    <th className="py-2.5 px-4 text-right">Exit</th>
                    <th className="py-2.5 px-4 text-right">Qty</th>
                    <th className="py-2.5 px-4 text-right">Net P&L</th>
                    <th className="py-2.5 px-4 text-right">Return %</th>
                    <th className="py-2.5 px-4 text-center">Exit Reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-dark-700/50 font-mono">
                  {result.trades.map((t) => (
                    <tr key={t.trade_id} className="hover:bg-dark-700/20">
                      <td className="py-2.5 px-4 font-bold">
                        <span className={t.direction === "BUY" ? "text-trade-green" : "text-trade-red"}>
                          {t.direction}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-right text-slate-300">₹{t.entry_price.toFixed(2)}</td>
                      <td className="py-2.5 px-4 text-right text-slate-300">₹{t.exit_price.toFixed(2)}</td>
                      <td className="py-2.5 px-4 text-right text-slate-300">{t.quantity}</td>
                      <td className={`py-2.5 px-4 text-right font-bold ${t.net_pnl >= 0 ? "text-trade-green" : "text-trade-red"}`}>
                        {t.net_pnl >= 0 ? "+" : ""}₹{t.net_pnl.toFixed(2)}
                      </td>
                      <td className={`py-2.5 px-4 text-right ${t.return_pct >= 0 ? "text-trade-green" : "text-trade-red"}`}>
                        {t.return_pct}%
                      </td>
                      <td className="py-2.5 px-4 text-center text-slate-400 text-[10px]">{t.exit_reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
