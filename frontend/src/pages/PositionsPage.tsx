import React, { useEffect, useState } from "react";
import { ArrowDownRight, ArrowUpRight, LineChart, RefreshCw, XCircle } from "lucide-react";
import { api } from "../services/api";
import { Position } from "../types";

export const PositionsPage: React.FC = () => {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadPositions();
    const interval = setInterval(loadPositions, 4000);
    return () => clearInterval(interval);
  }, []);

  const loadPositions = async () => {
    try {
      const data = await api.getPositions();
      setPositions(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleClosePosition = async (pos: Position) => {
    try {
      const closeSide = pos.direction === "LONG" ? "SELL" : "BUY";
      const order = await api.submitOrder({
        symbol: pos.symbol,
        side: closeSide,
        order_type: "MARKET",
        quantity: pos.quantity,
        price: pos.current_price,
        live_execution: false,
      });
      await api.executePaperOrder(order.order_id, pos.current_price);
      loadPositions();
    } catch (err: any) {
      alert(err.message || "Failed to close position");
    }
  };

  const totalUnrealized = positions.reduce((acc, p) => acc + p.unrealized_pnl, 0);
  const totalRealized = positions.reduce((acc, p) => acc + p.realized_pnl, 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-dark-700 pb-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <LineChart className="w-5 h-5 text-cyan-400" />
            Open Portfolio Positions
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Real-time FIFO mark-to-market positions, average entry prices, and P&L tracking.
          </p>
        </div>

        <div className="flex items-center space-x-4 bg-dark-800 px-4 py-2 rounded-xl border border-dark-700">
          <div>
            <span className="text-[10px] text-slate-400 uppercase font-semibold">Total Unrealized</span>
            <div className={`text-base font-bold font-mono ${totalUnrealized >= 0 ? "text-trade-green" : "text-trade-red"}`}>
              {totalUnrealized >= 0 ? "+" : ""}₹{totalUnrealized.toFixed(2)}
            </div>
          </div>
          <div className="h-8 w-px bg-dark-700" />
          <div>
            <span className="text-[10px] text-slate-400 uppercase font-semibold">Total Realized</span>
            <div className={`text-base font-bold font-mono ${totalRealized >= 0 ? "text-trade-green" : "text-trade-red"}`}>
              {totalRealized >= 0 ? "+" : ""}₹{totalRealized.toFixed(2)}
            </div>
          </div>
        </div>
      </div>

      <div className="bg-dark-800 border border-dark-700 rounded-xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-dark-900/60 text-slate-400 text-xs uppercase tracking-wider font-semibold border-b border-dark-700">
              <tr>
                <th className="py-3 px-4">Symbol</th>
                <th className="py-3 px-4">Side</th>
                <th className="py-3 px-4 text-right">Quantity</th>
                <th className="py-3 px-4 text-right">Entry Price</th>
                <th className="py-3 px-4 text-right">Current Price</th>
                <th className="py-3 px-4 text-right">Unrealized P&L</th>
                <th className="py-3 px-4 text-right">Realized P&L</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-700/50">
              {positions.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-500 italic">
                    No open positions. Portfolio is 100% in cash.
                  </td>
                </tr>
              ) : (
                positions.map((p) => {
                  const isLong = p.direction === "LONG";
                  const isPnlPositive = p.unrealized_pnl >= 0;

                  return (
                    <tr key={p.id} className="hover:bg-dark-700/30 transition">
                      <td className="py-3 px-4 font-bold font-mono text-white">{p.symbol}</td>
                      <td className="py-3 px-4">
                        <span
                          className={`font-mono font-bold text-xs px-2 py-0.5 rounded ${
                            isLong
                              ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                              : "bg-red-950 text-red-400 border border-red-800"
                          }`}
                        >
                          {p.direction}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-white font-bold">{p.quantity}</td>
                      <td className="py-3 px-4 text-right font-mono text-slate-300">
                        ₹{p.entry_price.toFixed(2)}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-slate-200">
                        ₹{p.current_price.toFixed(2)}
                      </td>
                      <td
                        className={`py-3 px-4 text-right font-mono font-bold ${
                          isPnlPositive ? "text-trade-green" : "text-trade-red"
                        }`}
                      >
                        {isPnlPositive ? "+" : ""}₹{p.unrealized_pnl.toFixed(2)}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-slate-400">
                        ₹{p.realized_pnl.toFixed(2)}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => handleClosePosition(p)}
                          className="px-2.5 py-1 bg-red-950 hover:bg-red-900 text-red-300 border border-red-800 rounded text-xs font-semibold transition"
                        >
                          Close Position
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
