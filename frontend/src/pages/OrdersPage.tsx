import React, { useEffect, useState } from "react";
import { CheckCircle2, Clock, Trash2, TrendingUp, XCircle } from "lucide-react";
import { api } from "../services/api";
import { Order } from "../types";

export const OrdersPage: React.FC = () => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadOrders();
    const interval = setInterval(loadOrders, 4000);
    return () => clearInterval(interval);
  }, []);

  const loadOrders = async () => {
    try {
      const data = await api.getOrders();
      setOrders(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async (orderId: string) => {
    try {
      await api.cancelOrder(orderId);
      loadOrders();
    } catch (err: any) {
      alert(err.message || "Failed to cancel order");
    }
  };

  const handleFillPaper = async (orderId: string, price: number) => {
    try {
      await api.executePaperOrder(orderId, price || 100.0);
      loadOrders();
    } catch (err: any) {
      alert(err.message || "Failed to fill paper order");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between border-b border-dark-700 pb-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-cyan-400" />
            Order Execution & Audit Log
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Complete lifecycle tracking of all submitted, working, filled, and cancelled orders.
          </p>
        </div>
      </div>

      <div className="bg-dark-800 border border-dark-700 rounded-xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-dark-900/60 text-slate-400 text-xs uppercase tracking-wider font-semibold border-b border-dark-700">
              <tr>
                <th className="py-3 px-4">Time</th>
                <th className="py-3 px-4">Order ID</th>
                <th className="py-3 px-4">Symbol</th>
                <th className="py-3 px-4">Side</th>
                <th className="py-3 px-4">Type</th>
                <th className="py-3 px-4 text-right">Qty</th>
                <th className="py-3 px-4 text-right">Price</th>
                <th className="py-3 px-4 text-center">Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-700/50">
              {orders.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-8 text-center text-slate-500 italic">
                    No orders submitted yet. Place an order via the Dashboard or Strategy automation.
                  </td>
                </tr>
              ) : (
                orders.map((o) => {
                  const isBuy = o.side === "BUY";
                  const isWorking = o.status === "SUBMITTED" || o.status === "PENDING";

                  return (
                    <tr key={o.order_id} className="hover:bg-dark-700/30 transition">
                      <td className="py-3 px-4 text-xs font-mono text-slate-400">
                        {new Date(o.created_at).toLocaleTimeString()}
                      </td>
                      <td className="py-3 px-4 text-xs font-mono text-slate-400" title={o.order_id}>
                        {o.order_id.slice(0, 8)}...
                      </td>
                      <td className="py-3 px-4 font-bold font-mono text-white">{o.symbol}</td>
                      <td className="py-3 px-4">
                        <span
                          className={`font-mono font-bold text-xs px-2 py-0.5 rounded ${
                            isBuy
                              ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                              : "bg-red-950 text-red-400 border border-red-800"
                          }`}
                        >
                          {o.side}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-xs font-mono text-slate-300">{o.order_type}</td>
                      <td className="py-3 px-4 text-right font-mono text-white font-bold">{o.quantity}</td>
                      <td className="py-3 px-4 text-right font-mono text-slate-200">
                        ₹{o.price?.toFixed(2) || (o.average_price?.toFixed(2) ?? "MKT")}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span
                          className={`inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold ${
                            o.status === "FILLED"
                              ? "bg-emerald-950/60 text-emerald-400 border border-emerald-800/40"
                              : o.status === "CANCELLED"
                              ? "bg-dark-900 text-slate-500 border border-dark-700"
                              : o.status === "REJECTED"
                              ? "bg-red-950/60 text-red-400 border border-red-800/40"
                              : "bg-cyan-950/60 text-cyan-400 border border-cyan-800/40 animate-pulse"
                          }`}
                        >
                          {o.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right space-x-2">
                        {isWorking && (
                          <>
                            <button
                              onClick={() => handleFillPaper(o.order_id, o.price || 100.0)}
                              className="px-2 py-1 bg-cyan-600 hover:bg-cyan-500 text-black text-xs font-bold rounded shadow transition"
                            >
                              Simulate Fill
                            </button>
                            <button
                              onClick={() => handleCancel(o.order_id)}
                              className="px-2 py-1 bg-red-900/60 hover:bg-red-800 text-red-200 text-xs font-semibold rounded transition"
                            >
                              Cancel
                            </button>
                          </>
                        )}
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
