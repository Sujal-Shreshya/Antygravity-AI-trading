import React, { useEffect, useState } from "react";
import { CheckCircle2, ChevronRight, Cpu, Layers, Sparkles, TrendingUp } from "lucide-react";
import { api } from "../services/api";

export const StrategiesPage: React.FC = () => {
  const [strategies, setStrategies] = useState<any[]>([]);
  const [symbol, setSymbol] = useState("RELIANCE");
  const [timeframe, setTimeframe] = useState("15m");
  const [consensus, setConsensus] = useState<any>(null);
  const [regime, setRegime] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadCatalog();
    loadSignals();
  }, [symbol, timeframe]);

  const loadCatalog = async () => {
    try {
      const list = await api.getStrategies();
      setStrategies(list);
    } catch (err) {
      console.error(err);
    }
  };

  const loadSignals = async () => {
    setLoading(true);
    try {
      const [cons, reg] = await Promise.all([
        api.getConsensusSignal(symbol, timeframe),
        api.getMarketRegime(symbol, timeframe),
      ]);
      setConsensus(cons);
      setRegime(reg);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-dark-700 pb-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Cpu className="w-5 h-5 text-purple-400" />
            Algorithmic Strategies & AI Signal Aggregator
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            10 Quantitative strategy engines, zero look-ahead market regime classification, and weighted consensus voting.
          </p>
        </div>

        {/* Symbol & Timeframe selectors */}
        <div className="flex items-center space-x-2">
          <select
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="bg-dark-800 border border-dark-700 rounded-lg px-3 py-1.5 text-xs font-mono text-slate-200 focus:outline-none"
          >
            {["RELIANCE", "TCS", "INFY", "BTC/USDT", "ETH/USDT", "EUR/USD"].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <select
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value)}
            className="bg-dark-800 border border-dark-700 rounded-lg px-3 py-1.5 text-xs font-mono text-slate-200 focus:outline-none"
          >
            {["5m", "15m", "1h", "4h", "1D"].map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Consensus & Regime Snapshot Box */}
      <div className="bg-gradient-to-r from-purple-950/40 via-dark-800 to-cyan-950/40 border border-purple-900/50 rounded-xl p-5 shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2 text-purple-400 text-xs font-bold uppercase tracking-wider">
              <Sparkles className="w-4 h-4" />
              <span>Multi-Strategy Consensus Signal ({symbol} • {timeframe})</span>
            </div>
            <div className="mt-2 flex items-baseline space-x-3">
              <span className={`text-3xl font-bold font-mono ${
                consensus?.consensus_direction === "BUY"
                  ? "text-trade-green"
                  : consensus?.consensus_direction === "SELL"
                  ? "text-trade-red"
                  : "text-amber-400"
              }`}>
                {consensus?.consensus_direction || "HOLD"}
              </span>
              <span className="text-xs text-slate-400">
                Confidence: <strong className="text-slate-200 font-mono">{((consensus?.overall_confidence || 0.8) * 100).toFixed(0)}%</strong>
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 text-xs font-mono bg-dark-900/60 p-3 rounded-lg border border-dark-700">
            <div>
              <span className="text-slate-500">Market Regime:</span>
              <div className="text-cyan-300 font-bold">{regime?.regime || "TREND"}</div>
            </div>
            <div>
              <span className="text-slate-500">Entry / SL / TP:</span>
              <div className="text-slate-200 font-bold">
                ₹{consensus?.entry?.toFixed(2) || "2500"} / ₹{consensus?.stop_loss?.toFixed(2) || "2450"}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 10 Strategies Catalog Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {strategies.map((strat) => (
          <div
            key={strat.id}
            className="bg-dark-800 border border-dark-700 rounded-xl p-4 shadow-lg hover:border-dark-600 transition flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-dark-700 text-cyan-400 border border-dark-600">
                  {strat.id}
                </span>
                <span className="text-[10px] text-slate-400 font-mono">
                  {strat.required_candles} bars warm-up
                </span>
              </div>
              <h4 className="font-bold text-slate-100 text-base">{strat.name}</h4>
              <p className="text-xs text-slate-400 mt-1.5 leading-relaxed line-clamp-2">
                {strat.description || "Quantitative technical momentum and volatility strategy."}
              </p>
            </div>

            <div className="mt-4 pt-3 border-t border-dark-700/60">
              <span className="text-[10px] uppercase font-semibold text-slate-500 tracking-wider">
                Default Parameters
              </span>
              <div className="mt-1 flex flex-wrap gap-1">
                {Object.entries(strat.default_parameters || {}).map(([k, v]) => (
                  <span
                    key={k}
                    className="text-[10px] font-mono bg-dark-900 px-1.5 py-0.5 rounded text-slate-300 border border-dark-700"
                  >
                    {k}: {String(v)}
                  </span>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
