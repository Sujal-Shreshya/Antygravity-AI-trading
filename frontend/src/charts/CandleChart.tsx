import React, { useEffect, useRef, useState } from "react";
import { Candle } from "../types";

interface CandleChartProps {
  candles: Candle[];
  symbol: string;
  timeframe: string;
  onTimeframeChange: (tf: string) => void;
}

export const CandleChart: React.FC<CandleChartProps> = ({
  candles,
  symbol,
  timeframe,
  onTimeframeChange,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [hoveredCandle, setHoveredCandle] = useState<Candle | null>(null);

  const timeframes = ["1m", "5m", "15m", "1h", "1D"];

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || candles.length === 0) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Handle high DPI displays
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;

    // Clear canvas
    ctx.fillStyle = "#121721"; // dark-800
    ctx.fillRect(0, 0, width, height);

    // Padding
    const padTop = 20;
    const padBottom = 40;
    const padRight = 60;
    const chartHeight = height - padTop - padBottom;
    const chartWidth = width - padRight;

    // Find min and max price across candles
    const highs = candles.map((c) => c.high);
    const lows = candles.map((c) => c.low);
    const minPrice = Math.min(...lows) * 0.998;
    const maxPrice = Math.max(...highs) * 1.002;
    const priceRange = maxPrice - minPrice || 1;

    // Price to Y coordinate
    const getY = (price: number) => padTop + chartHeight * (1 - (price - minPrice) / priceRange);

    // Draw Price Grid lines
    ctx.strokeStyle = "#1a2233"; // dark-700
    ctx.lineWidth = 1;
    ctx.fillStyle = "#64748b"; // slate-500
    ctx.font = "10px monospace";
    ctx.textAlign = "left";

    const gridSteps = 5;
    for (let i = 0; i <= gridSteps; i++) {
      const price = minPrice + (priceRange * i) / gridSteps;
      const y = getY(price);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(chartWidth, y);
      ctx.stroke();
      ctx.fillText(price.toFixed(2), chartWidth + 6, y + 3);
    }

    // Candle rendering dimensions
    const candleCount = candles.length;
    const candleWidth = Math.max(2, (chartWidth / candleCount) * 0.7);
    const step = chartWidth / candleCount;

    // Draw Candles
    candles.forEach((c, idx) => {
      const x = idx * step + step / 2;
      const openY = getY(c.open);
      const closeY = getY(c.close);
      const highY = getY(c.high);
      const lowY = getY(c.low);

      const isBullish = c.close >= c.open;
      const color = isBullish ? "#0ecb81" : "#f6465d";

      // Draw Wick (High to Low)
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(x, highY);
      ctx.lineTo(x, lowY);
      ctx.stroke();

      // Draw Candle Body
      ctx.fillStyle = color;
      const bodyTop = Math.min(openY, closeY);
      const bodyHeight = Math.max(2, Math.abs(closeY - openY));
      ctx.fillRect(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight);
    });
  }, [candles]);

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || candles.length === 0) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const padRight = 60;
    const chartWidth = rect.width - padRight;
    const step = chartWidth / candles.length;

    const index = Math.floor(x / step);
    if (index >= 0 && index < candles.length) {
      setHoveredCandle(candles[index]);
    } else {
      setHoveredCandle(null);
    }
  };

  const latest = candles[candles.length - 1];
  const isUp = latest ? latest.close >= latest.open : true;

  return (
    <div className="bg-dark-800 border border-dark-700 rounded-xl overflow-hidden p-4 shadow-xl">
      {/* Chart Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-dark-700/60">
        <div className="flex items-center space-x-3">
          <span className="text-lg font-bold text-white tracking-wide">{symbol}</span>
          {latest && (
            <span
              className={`text-lg font-mono font-bold ${isUp ? "text-trade-green" : "text-trade-red"}`}
            >
              ₹{latest.close.toFixed(2)}
            </span>
          )}
        </div>

        {/* Timeframe Switcher */}
        <div className="flex items-center space-x-1 bg-dark-900 p-1 rounded-lg border border-dark-700">
          {timeframes.map((tf) => (
            <button
              key={tf}
              onClick={() => onTimeframeChange(tf)}
              className={`px-2.5 py-1 text-xs font-mono font-semibold rounded ${
                timeframe === tf
                  ? "bg-cyan-500 text-black shadow"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* Inspect OHLCV Tooltip Banner */}
      <div className="h-6 mt-2 flex items-center space-x-4 text-xs font-mono text-slate-400">
        {hoveredCandle ? (
          <>
            <span>O: <strong className="text-slate-200">{hoveredCandle.open}</strong></span>
            <span>H: <strong className="text-slate-200">{hoveredCandle.high}</strong></span>
            <span>L: <strong className="text-slate-200">{hoveredCandle.low}</strong></span>
            <span>C: <strong className={hoveredCandle.close >= hoveredCandle.open ? "text-trade-green" : "text-trade-red"}>{hoveredCandle.close}</strong></span>
            <span>Vol: <strong className="text-slate-200">{hoveredCandle.volume}</strong></span>
            <span>Time: {new Date(hoveredCandle.timestamp).toLocaleTimeString()}</span>
          </>
        ) : (
          <span className="text-slate-500 italic">Hover over candles to inspect OHLCV values</span>
        )}
      </div>

      {/* Chart Canvas */}
      <div className="relative w-full h-80 mt-1">
        <canvas
          ref={canvasRef}
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoveredCandle(null)}
          className="w-full h-full cursor-crosshair rounded-lg"
        />
      </div>
    </div>
  );
};
