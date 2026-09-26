import React from "react";
import { LucideIcon } from "lucide-react";

interface StatsCardProps {
  title: string;
  value: string | number;
  subtext?: string;
  icon: LucideIcon;
  variant?: "default" | "success" | "danger" | "warning";
}

export const StatsCard: React.FC<StatsCardProps> = ({
  title,
  value,
  subtext,
  icon: Icon,
  variant = "default",
}) => {
  const variantStyles = {
    default: "text-slate-100 border-dark-700 bg-dark-800",
    success: "text-emerald-400 border-emerald-900/40 bg-emerald-950/20",
    danger: "text-red-400 border-red-900/40 bg-red-950/20",
    warning: "text-amber-400 border-amber-900/40 bg-amber-950/20",
  };

  const iconStyles = {
    default: "text-cyan-400 bg-cyan-950/50 border border-cyan-800/40",
    success: "text-emerald-400 bg-emerald-950/50 border border-emerald-800/40",
    danger: "text-red-400 bg-red-950/50 border border-red-800/40",
    warning: "text-amber-400 bg-amber-950/50 border border-amber-800/40",
  };

  return (
    <div className={`p-4 rounded-xl border transition-all ${variantStyles[variant]}`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
          {title}
        </span>
        <div className={`p-2 rounded-lg ${iconStyles[variant]}`}>
          <Icon className="w-4 h-4" />
        </div>
      </div>
      <div className="mt-3">
        <div className="text-2xl font-bold font-mono tracking-tight">{value}</div>
        {subtext && <div className="mt-1 text-xs text-slate-400">{subtext}</div>}
      </div>
    </div>
  );
};
