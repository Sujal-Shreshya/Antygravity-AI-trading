import React, { useEffect, useState } from "react";
import { AlertOctagon, CheckCircle2, Shield, ShieldAlert, XCircle } from "lucide-react";
import { StatsCard } from "../components/StatsCard";
import { api } from "../services/api";
import { RiskEvent, RiskStatus } from "../types";

export const RiskPage: React.FC = () => {
  const [riskStatus, setRiskStatus] = useState<RiskStatus | null>(null);
  const [events, setEvents] = useState<RiskEvent[]>([]);
  const [loading, setLoading] = useState(true);

  // Dry-run evaluate state
  const [testSymbol, setTestSymbol] = useState("INFY");
  const [testQty, setTestQty] = useState(100);
  const [testPrice, setTestPrice] = useState(200);
  const [evalResult, setEvalResult] = useState<any>(null);

  useEffect(() => {
    loadRiskData();
    const interval = setInterval(loadRiskData, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadRiskData = async () => {
    try {
      const [status, evs] = await Promise.all([
        api.getRiskStatus(),
        api.getRiskEvents(),
      ]);
      setRiskStatus(status);
      setEvents(evs);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDryRunEvaluate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await api.evaluateOrderRisk({
        symbol: testSymbol,
        side: "BUY",
        order_type: "LIMIT",
        quantity: testQty,
        price: testPrice,
      });
      setEvalResult(res);
    } catch (err: any) {
      alert(err.message || "Failed to evaluate risk");
    }
  };

  const params = riskStatus?.parameters;
  const isKillActive = riskStatus?.kill_switch.is_active ?? false;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="border-b border-dark-700 pb-4">
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-red-400" />
          Pre-Trade Risk Management & Circuit Breakers
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          Zero-tolerance pre-trade boundary gates: Max 1% trade risk, 3% daily loss circuit breaker, 10% max portfolio drawdown, and emergency kill switch.
        </p>
      </div>

      {/* Kill Switch Status Banner */}
      <div className={`p-4 rounded-xl border flex items-center justify-between shadow-xl ${
        isKillActive
          ? "bg-red-950/60 border-red-800 text-red-200"
          : "bg-emerald-950/40 border-emerald-800/60 text-emerald-200"
      }`}>
        <div className="flex items-center space-x-3">
          {isKillActive ? (
            <AlertOctagon className="w-6 h-6 text-red-400 animate-pulse" />
          ) : (
            <CheckCircle2 className="w-6 h-6 text-emerald-400" />
          )}
          <div>
            <h3 className="font-bold text-base">
              {isKillActive ? "EMERGENCY KILL SWITCH ENGAGED" : "KILL SWITCH ARMED & OPERATIONAL"}
            </h3>
            <p className="text-xs opacity-80 mt-0.5">
              {isKillActive
                ? `Order submissions are strictly blocked. Reason: ${riskStatus?.kill_switch.reason}`
                : "All pre-trade risk controls and circuit breakers active. No order bypass is technically possible."}
            </p>
          </div>
        </div>
      </div>

      {/* Active Boundaries Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatsCard
          title="Max Risk Per Trade"
          value={`${((params?.max_risk_per_trade_pct || 0.01) * 100).toFixed(1)}%`}
          subtext="Strict Capital Loss Limit"
          icon={Shield}
          variant="default"
        />
        <StatsCard
          title="Daily Loss Limit"
          value={`${((params?.max_daily_loss_pct || 0.03) * 100).toFixed(1)}%`}
          subtext="Circuit Breaker Cut-off"
          icon={ShieldAlert}
          variant="warning"
        />
        <StatsCard
          title="Portfolio Drawdown Cap"
          value={`${((params?.max_portfolio_drawdown_pct || 0.10) * 100).toFixed(1)}%`}
          subtext="Peak-to-Trough Halt"
          icon={AlertOctagon}
          variant="danger"
        />
        <StatsCard
          title="Max Open Positions"
          value={params?.max_open_positions || 10}
          subtext="Max 15% Single Asset Cap"
          icon={Shield}
          variant="default"
        />
      </div>

      {/* Dry-Run Risk Evaluation Simulator */}
      <div className="bg-dark-800 border border-dark-700 rounded-xl p-5 shadow-xl space-y-4">
        <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
          <Shield className="w-4 h-4 text-cyan-400" />
          Pre-Trade Risk Dry-Run Simulator
        </h3>
        <p className="text-xs text-slate-400">
          Simulate whether a proposed order passes or fails all pre-trade risk and capital boundary checks.
        </p>

        <form onSubmit={handleDryRunEvaluate} className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
              Symbol
            </label>
            <input
              type="text"
              value={testSymbol}
              onChange={(e) => setTestSymbol(e.target.value)}
              className="w-full bg-dark-900 border border-dark-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
              Quantity
            </label>
            <input
              type="number"
              value={testQty}
              onChange={(e) => setTestQty(parseInt(e.target.value) || 1)}
              className="w-full bg-dark-900 border border-dark-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
              Price (₹)
            </label>
            <input
              type="number"
              value={testPrice}
              onChange={(e) => setTestPrice(parseFloat(e.target.value) || 1)}
              className="w-full bg-dark-900 border border-dark-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none"
            />
          </div>
          <div className="flex items-end">
            <button
              type="submit"
              className="w-full py-2 bg-dark-700 hover:bg-dark-600 text-cyan-400 font-bold text-xs uppercase tracking-wider rounded-lg border border-cyan-500/40 transition"
            >
              Test Pre-Trade Risk
            </button>
          </div>
        </form>

        {evalResult && (
          <div className={`p-3 rounded-lg text-xs font-mono border ${
            evalResult.is_approved
              ? "bg-emerald-950/40 border-emerald-800 text-emerald-300"
              : "bg-red-950/40 border-red-800 text-red-300"
          }`}>
            <div className="font-bold flex items-center gap-2">
              {evalResult.is_approved ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
              Decision: {evalResult.action} ({evalResult.rule_name})
            </div>
            <div className="mt-1 opacity-90">{evalResult.reason}</div>
          </div>
        )}
      </div>

      {/* Historical Risk Events Audit Trail */}
      <div className="bg-dark-800 border border-dark-700 rounded-xl overflow-hidden shadow-xl">
        <div className="p-4 border-b border-dark-700 font-bold text-sm text-white">
          Risk Rejection & Circuit Breaker Audit Trail
        </div>
        <div className="overflow-x-auto max-h-60">
          <table className="w-full text-left text-xs">
            <thead className="bg-dark-900/60 text-slate-400 uppercase font-semibold">
              <tr>
                <th className="py-2.5 px-4">Time</th>
                <th className="py-2.5 px-4">Rule Name</th>
                <th className="py-2.5 px-4">Action</th>
                <th className="py-2.5 px-4">Reason</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-700/50 font-mono">
              {events.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-6 text-center text-slate-500 italic">
                    No risk violations recorded. Risk boundaries operating within safe limits.
                  </td>
                </tr>
              ) : (
                events.map((e) => (
                  <tr key={e.id} className="hover:bg-dark-700/20">
                    <td className="py-2.5 px-4 text-slate-400">
                      {new Date(e.created_at).toLocaleTimeString()}
                    </td>
                    <td className="py-2.5 px-4 text-cyan-400 font-bold">{e.rule_name}</td>
                    <td className="py-2.5 px-4 font-bold text-red-400">{e.action}</td>
                    <td className="py-2.5 px-4 text-slate-300">{e.reason}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
