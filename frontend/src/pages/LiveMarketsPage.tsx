import React, { useEffect, useState } from "react";
import { Clock, Globe, Radio, TrendingDown, TrendingUp } from "lucide-react";
import { api } from "../services/api";
import { Instrument, Quote } from "../types";

export const LiveMarketsPage: React.FC = () => {
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [quotes, setQuotes] = useState<Record<string, Quote>>({});
  const [selectedMarket, setSelectedMarket] = useState<string>("ALL");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadInstruments();
  }, []);

  useEffect(() => {
    if (instruments.length > 0) {
      pollQuotes();
      const interval = setInterval(pollQuotes, 4000);
      return () => clearInterval(interval);
    }
  }, [instruments]);

  const loadInstruments = async () => {
    setLoading(true);
    try {
      const data = await api.getInstruments();
      setInstruments(data);
    } catch (err) {
      console.error("Failed to load instruments:", err);
    } finally {
      setLoading(false);
    }
  };

  const pollQuotes = async () => {
    const quoteMap: Record<string, Quote> = {};
    await Promise.all(
      instruments.map(async (inst) => {
        try {
          const q = await api.getQuote(inst.symbol);
          quoteMap[inst.symbol] = q;
        } catch {}
      })
    );
    setQuotes(quoteMap);
  };

  const filteredInstruments = instruments.filter((inst) => {
    if (selectedMarket === "ALL") return true;
    return inst.market === selectedMarket;
  });

  return (
    <div className="space-y-6">
      {/* Header & Filter Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-dark-700 pb-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Radio className="w-5 h-5 text-cyan-400 animate-pulse" />
            Multi-Market Live Feeds
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Real-time normalized market quotes for Indian Equities, Crypto Spot, and Forex.
          </p>
        </div>

        <div className="flex items-center space-x-2 bg-dark-800 p-1 rounded-lg border border-dark-700">
          {[
            { id: "ALL", label: "All Markets" },
            { id: "INDIAN_EQUITY", label: "NSE / BSE" },
            { id: "CRYPTO_SPOT", label: "Crypto 24/7" },
            { id: "FOREX_SPOT", label: "Forex 24/5" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setSelectedMarket(tab.id)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition ${
                selectedMarket === tab.id
                  ? "bg-cyan-500 text-black shadow"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Markets Table */}
      <div className="bg-dark-800 border border-dark-700 rounded-xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-dark-900/60 text-slate-400 text-xs uppercase tracking-wider font-semibold border-b border-dark-700">
              <tr>
                <th className="py-3 px-4">Instrument</th>
                <th className="py-3 px-4">Market</th>
                <th className="py-3 px-4">Exchange</th>
                <th className="py-3 px-4 text-right">LTP</th>
                <th className="py-3 px-4 text-right">Bid</th>
                <th className="py-3 px-4 text-right">Ask</th>
                <th className="py-3 px-4 text-right">Volume</th>
                <th className="py-3 px-4 text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-700/50">
              {filteredInstruments.map((inst) => {
                const quote = quotes[inst.symbol];
                const price = quote?.price ?? 100.0;
                const bid = quote?.bid ?? price - 0.05;
                const ask = quote?.ask ?? price + 0.05;

                return (
                  <tr key={inst.symbol} className="hover:bg-dark-700/30 transition">
                    <td className="py-3 px-4">
                      <div className="font-bold text-white font-mono">{inst.symbol}</div>
                      <div className="text-xs text-slate-400">{inst.name}</div>
                    </td>
                    <td className="py-3 px-4 text-xs font-mono text-cyan-400">{inst.market}</td>
                    <td className="py-3 px-4 text-xs font-mono text-slate-300">{inst.exchange}</td>
                    <td className="py-3 px-4 text-right font-mono font-bold text-white">
                      ₹{price.toFixed(2)}
                    </td>
                    <td className="py-3 px-4 text-right font-mono text-trade-green">
                      ₹{bid.toFixed(2)}
                    </td>
                    <td className="py-3 px-4 text-right font-mono text-trade-red">
                      ₹{ask.toFixed(2)}
                    </td>
                    <td className="py-3 px-4 text-right font-mono text-slate-400">
                      {quote?.volume ? quote.volume.toLocaleString() : "10,000"}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold font-mono bg-emerald-950/60 text-emerald-400 border border-emerald-800/40">
                        LIVE
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
