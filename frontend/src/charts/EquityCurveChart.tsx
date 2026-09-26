import React, { useEffect, useRef } from "react";

interface EquityPoint {
  timestamp: string;
  equity: number;
  cash: number;
  drawdown_pct: number;
}

interface EquityCurveChartProps {
  data: EquityPoint[];
  initialCapital: number;
}

export const EquityCurveChart: React.FC<EquityCurveChartProps> = ({
  data,
  initialCapital,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || data.length === 0) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;

    // Background
    ctx.fillStyle = "#121721";
    ctx.fillRect(0, 0, width, height);

    const padTop = 15;
    const padBottom = 25;
    const padRight = 60;
    const chartHeight = height - padTop - padBottom;
    const chartWidth = width - padRight;

    const equities = data.map((d) => d.equity);
    const minEq = Math.min(initialCapital * 0.95, ...equities);
    const maxEq = Math.max(initialCapital * 1.05, ...equities);
    const eqRange = maxEq - minEq || 1;

    const getY = (val: number) => padTop + chartHeight * (1 - (val - minEq) / eqRange);
    const getX = (idx: number) => (idx / (data.length - 1 || 1)) * chartWidth;

    // Grid & Benchmark line (initial capital)
    const baseLineY = getY(initialCapital);
    ctx.strokeStyle = "#334155";
    ctx.setLineDash([4, 4]);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, baseLineY);
    ctx.lineTo(chartWidth, baseLineY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Y-Axis Labels
    ctx.fillStyle = "#64748b";
    ctx.font = "10px monospace";
    ctx.textAlign = "left";
    ctx.fillText(`Base ₹${initialCapital.toLocaleString()}`, chartWidth + 4, baseLineY + 3);

    const finalEq = data[data.length - 1].equity;
    const isProfitable = finalEq >= initialCapital;
    const lineColor = isProfitable ? "#0ecb81" : "#f6465d";

    // Draw Equity Line
    ctx.beginPath();
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 2;

    data.forEach((pt, i) => {
      const x = getX(i);
      const y = getY(pt.equity);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Area fill below equity line
    ctx.lineTo(chartWidth, height - padBottom);
    ctx.lineTo(0, height - padBottom);
    ctx.closePath();
    const gradient = ctx.createLinearGradient(0, padTop, 0, height - padBottom);
    gradient.addColorStop(0, isProfitable ? "rgba(14, 203, 129, 0.25)" : "rgba(246, 70, 93, 0.25)");
    gradient.addColorStop(1, "rgba(18, 23, 33, 0)");
    ctx.fillStyle = gradient;
    ctx.fill();
  }, [data, initialCapital]);

  return (
    <div className="w-full h-48 relative">
      <canvas ref={canvasRef} className="w-full h-full rounded-lg" />
    </div>
  );
};
