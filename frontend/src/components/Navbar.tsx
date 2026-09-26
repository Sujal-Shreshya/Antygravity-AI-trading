import React from "react";
import {
  Activity,
  AlertOctagon,
  BarChart2,
  Layers,
  LineChart,
  Lock,
  Radio,
  ShieldAlert,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import { KillSwitchStatus } from "../types";

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  killSwitch: KillSwitchStatus | null;
  onOpenKillSwitchModal: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  killSwitch,
  onOpenKillSwitchModal,
}) => {
  const isKillActive = killSwitch?.is_active ?? false;

  const navItems = [
    { id: "dashboard", label: "Dashboard", icon: Activity },
    { id: "markets", label: "Markets", icon: Radio },
    { id: "strategies", label: "Strategies & Signals", icon: Layers },
    { id: "orders", label: "Orders & Execution", icon: TrendingUp },
    { id: "positions", label: "Positions", icon: LineChart },
    { id: "backtesting", label: "Backtesting", icon: BarChart2 },
    { id: "risk", label: "Risk Management", icon: ShieldAlert },
  ];

  return (
    <header className="border-b border-dark-700 bg-dark-800/90 backdrop-blur sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Title */}
          <div className="flex items-center space-x-3">
            <div className="bg-gradient-to-tr from-cyan-600 to-blue-500 p-2 rounded-lg text-white shadow-lg shadow-cyan-500/20">
              <TrendingUp className="w-6 h-6" />
            </div>
            <div>
              <span className="font-bold text-lg tracking-wider text-white flex items-center gap-2">
                AI TRADING ENGINE
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800">
                  PROD v0.1
                </span>
              </span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="hidden md:flex space-x-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium transition-all ${
                    isActive
                      ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/30"
                      : "text-slate-400 hover:text-slate-200 hover:bg-dark-700/50"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>

          {/* Safety Badges & Emergency Kill Switch */}
          <div className="flex items-center space-x-3">
            {/* Live Trading Guard Badge */}
            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-mono bg-emerald-950/60 text-emerald-400 border border-emerald-800/50">
              <Lock className="w-3.5 h-3.5 text-emerald-400" />
              <span>LIVE_TRADING=false</span>
            </div>

            {/* Kill Switch Toggle Button */}
            <button
              onClick={onOpenKillSwitchModal}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all shadow-md ${
                isKillActive
                  ? "bg-red-600 hover:bg-red-500 text-white animate-pulse shadow-red-600/30"
                  : "bg-dark-700 hover:bg-dark-600 text-slate-300 border border-dark-600"
              }`}
            >
              {isKillActive ? (
                <>
                  <AlertOctagon className="w-4 h-4 text-white" />
                  <span>KILL SWITCH ENGAGED</span>
                </>
              ) : (
                <>
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  <span>KILL SWITCH ARMED</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
