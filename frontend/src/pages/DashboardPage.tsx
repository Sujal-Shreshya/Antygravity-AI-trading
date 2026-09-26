import React, { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  DollarSign,
  Layers,
  LineChart,
  Shield,
  TrendingDown,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { CandleChart } from "../charts/CandleChart";
import { StatsCard } from "../components/StatsCard";
import { api } from "../services/api";
import { Candle, PortfolioBalance, RiskStatus } from "../types";

export const DashboardPage: React.FC = () => {
  const [balance, setBalance] = useState<PortfolioBalance | null>(null);
  const [riskStatus, setRiskStatus] = useState<RiskStatus | null>(null);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [symbol, setSymbol] = useState("RELIANCE");
  const [timeframe, setTimeframe] = useState("15m");
  const [consensus, setConsensus] = useState<any>(null);
  const [regime, setRegime] = useState<any>(null);

  // Quick Order State
  const [orderSide, setOrderSide] = useState<"BUY" | "SELL">("BUY");
  const [orderQty, setOrderQty] = useState(10);
  const [orderPrice, setOrderPrice] = useState(2500);
  const [submitting, setSubmitting] = useState(false);
  const [orderFeedback, setOrderFeedback] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, [symbol, timeframe]);

  const loadData = async () => {
    try {
      const [bal, risk, cData, cons, reg] = await Promise.all([
        api.getPortfolioBalance().catch(() => null),
        api.getRiskStatus().catch(() => null),
        api.getCandles(symbol, timeframe, 80).catch(() => []),
        api.getConsensusSignal(symbol, timeframe).catch(() => null),
        api.getMarketRegime(symbol, timeframe).catch(() => null),
      ]);

      if (bal) setBalance(bal);
      if (risk) setRiskStatus(risk);
      if (cData && cData.length > 0) {
        setCandles(cData);
        setOrderPrice(cData[cData.length - 1].close);
      }
      if (cons) setConsensus(cons);
      if (reg) setRegime(reg);
    } catch (err) {
      console.error("Dashboard poll error:", err);
    }
  };

  const handleQuickOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setOrderFeedback(null);
    try {
      const order = await api.submitOrder({
        symbol,
        side: orderSide,
        order_type: "MARKET",
        quantity: orderQty,
        price: orderPrice,
        live_execution: false,
      });

      // Execute in paper engine
      await api.executePaperOrder(order.order_id, orderPrice);

      setOrderFeedback({
        type: "success",
        msg: `Filled ${orderSide} ${orderQty} ${symbol} @ ₹${orderPrice.toFixed(2)}`,
      });
      loadData();
    } catch (err: any) {
      setOrderFeedback({
        type: "error",
        msg: err.message || "Order submission failed",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const equity = balance?.equity ?? 100000;
  const cash = balance?.cash ?? 100000;
  const unrealized = balance?.unrealized_pnl ?? 0;
  const realized = balance?.realized_pnl ?? 0;

  return (
    <div className="space-y-6">
      {/* Top Banner: Market Regime & AI Consensus */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Regime Indicator */}
        <div className="bg-dark-800 border border-dark-700 rounded-xl p-4 flex items-center justify-between shadow-lg">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-lg bg-cyan-950/60 border border-cyan-800/40 text-cyan-400">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Market Regime ({symbol})
              </span>
              <div className="text-lg font-bold font-mono text-cyan-300">
                {regime?.regime || "ANALYZING..."}
              </div>
            </div>
          </div>
          <div className="text-right text-xs text-slate-400">
            <div>Confidence: <strong className="text-slate-200">{((regime?.confidence || 0.8) * 100).toFixed(0)}%</strong></div>
            <div>Volatility: <strong className="text-slate-200">{regime?.details?.volatility_regime || "NORMAL"}</strong></div>
          </div>
        </div>

        {/* Multi-Strategy Consensus */}
        <div className="bg-dark-800 border border-dark-700 rounded-xl p-4 flex items-center justify-between shadow-lg">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-lg bg-purple-950/60 border border-purple-800/40 text-purple-400">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Multi-Strategy Consensus
              </span>
              <div className={`text-lg font-bold font-mono ${
                consensus?.consensus_direction === "BUY"
                  ? "text-trade-green"
                  : consensus?.consensus_direction === "SELL"
                  ? "text-trade-red"
                  : "text-amber-400"
              }`}>
                {consensus?.consensus_direction || "HOLD (NEUTRAL)"}
              </div>
            </div>
          </div>
          <div className="text-right text-xs text-slate-400">
            <div>Score: <strong className="text-slate-200">{consensus?.agreement_ratio ? `${(consensus.agreement_ratio * 100).toFixed(0)}%` : "N/A"}</strong></div>
            <div>Strategies: <strong className="text-slate-200">{consensus?.contributing_strategies?.length || 10} Evaluated</strong></div>
          </div>
        </div>
      </div>

      {/* Metric Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title="Portfolio Equity"
          value={`₹${equity.toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
          subtext="Simulated Paper Portfolio"
          icon={Wallet}
          variant="default"
        />
        <StatsCard
          title="Available Cash"
          value={`₹${cash.toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
          subtext="Unallocated Capital"
          icon={DollarSign}
          variant="default"
        />
        <StatsCard
          title="Unrealized P&L"
          value={`${unrealized >= 0 ? "+" : ""}₹${unrealized.toFixed(2)}`}
          subtext="Mark-to-Market Open Positions"
          icon={unrealized >= 0 ? TrendingUp : TrendingDown}
          variant={unrealized >= 0 ? "success" : "danger"}
        />
        <StatsCard
          title="Realized P&L"
          value={`${realized >= 0 ? "+" : ""}₹${realized.toFixed(2)}`}
          subtext="Closed Trade Profits"
          icon={LineChart}
          variant={realized >= 0 ? "success" : "danger"}
        />
      </div>

      {/* Main Grid: Chart on Left, Quick Order Form on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Candlestick Chart (2 Cols) */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center space-x-2">
            {["RELIANCE", "TCS", "INFY", "BTC/USDT", "ETH/USDT", "EUR/USD"].map((s) => (
              <button
                key={s}
                onClick={() => setSymbol(s)}
                className={`px-3 py-1.5 text-xs font-bold rounded-lg border transition ${
                  symbol === s
                    ? "bg-dark-700 text-cyan-400 border-cyan-500/50 shadow"
                    : "bg-dark-800 text-slate-400 border-dark-700 hover:text-slate-200"
                }`}
              >
                {s}
              </button>
            ))}
          </div>

          <CandleChart
            candles={candles}
            symbol={symbol}
            timeframe={timeframe}
            onTimeframeChange={setTimeframe}
          />
        </div>

        {/* Quick Order Submission Form (1 Col) */}
        <div className="bg-dark-800 border border-dark-700 rounded-xl p-5 shadow-xl space-y-5">
          <div className="flex items-center justify-between border-b border-dark-700 pb-3">
            <h3 className="font-bold text-white flex items-center gap-2">
              <Shield className="w-4 h-4 text-cyan-400" />
              Pre-Trade Guard Order Form
            </h3>
            <span className="text-[11px] font-mono text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/40">
              PAPER MODE
            </span>
          </div>

          <form onSubmit={handleQuickOrder} className="space-y-4">
            {/* Buy / Sell Tabs */}
            <div className="grid grid-cols-2 gap-2 bg-dark-900 p-1 rounded-lg border border-dark-700">
              <button
                type="button"
                onClick={() => setOrderSide("BUY")}
                className={`py-2 text-xs font-bold rounded-md transition ${
                  orderSide === "BUY"
                    ? "bg-trade-green text-black shadow-md shadow-emerald-500/20"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                BUY / LONG
              </button>
              <button
                type="button"
                onClick={() => setOrderSide("SELL")}
                className={`py-2 text-xs font-bold rounded-md transition ${
                  orderSide === "SELL"
                    ? "bg-trade-red text-white shadow-md shadow-red-500/20"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                SELL / SHORT
              </button>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Symbol</label>
              <input
                type="text"
                readOnly
                value={symbol}
                className="w-full bg-dark-900 border border-dark-700 rounded-lg px-3 py-2 text-sm text-slate-200 font-mono"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Quantity</label>
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={orderQty}
                  onChange={(e) => setOrderQty(Math.max(1, parseInt(e.target.value) || 1))}
                  className="w-full bg-dark-900 border border-dark-700 rounded-lg px-3 py-2 text-sm text-slate-200 font-mono focus:border-cyan-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Est. Price (₹)</label>
                <input
                  type="number"
                  step="0.05"
                  value={orderPrice}
                  onChange={(e) => setOrderPrice(parseFloat(e.target.value) || 0)}
                  className="w-full bg-dark-900 border border-dark-700 rounded-lg px-3 py-2 text-sm text-slate-200 font-mono focus:border-cyan-500 focus:outline-none"
                />
              </div>
            </div>

            {/* Risk Check Summary Box */}
            <div className="p-3 rounded-lg bg-dark-900/80 border border-dark-700 space-y-1.5 text-xs">
              <div className="flex justify-between text-slate-400">
                <span>Notional Value:</span>
                <strong className="text-slate-200 font-mono">₹{(orderQty * orderPrice).toLocaleString()}</strong>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Single Exposure:</span>
                <span className={`font-mono ${((orderQty * orderPrice) / equity) > 0.15 ? "text-trade-red" : "text-trade-green"}`}>
                  {(((orderQty * orderPrice) / equity) * 100).toFixed(1)}% (Max 15%)
                </span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Estimated Fee (0.03%):</span>
                <strong className="text-slate-300 font-mono">₹{((orderQty * orderPrice) * 0.0003).toFixed(2)}</strong>
              </div>
            </div>

            {orderFeedback && (
              <div
                className={`p-3 rounded-lg text-xs flex items-center space-x-2 ${
                  orderFeedback.type === "success"
                    ? "bg-emerald-950/50 border border-emerald-800 text-emerald-300"
                    : "bg-red-950/50 border border-red-800 text-red-300"
                }`}
              >
                {orderFeedback.type === "success" ? (
                  <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                ) : (
                  <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                )}
                <span>{orderFeedback.msg}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className={`w-full py-2.5 rounded-lg font-bold text-sm transition-all shadow-lg flex items-center justify-center space-x-2 ${
                orderSide === "BUY"
                  ? "bg-trade-green hover:bg-emerald-400 text-black shadow-emerald-500/20"
                  : "bg-trade-red hover:bg-red-500 text-white shadow-red-500/20"
              }`}
            >
              <span>{submitting ? "Evaluating Risk & Executing..." : `SUBMIT ${orderSide} ORDER`}</span>
              <ArrowUpRight className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
