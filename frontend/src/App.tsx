import React, { useEffect, useState } from "react";
import { KillSwitchModal } from "./components/KillSwitchModal";
import { Navbar } from "./components/Navbar";
import { BacktestPage } from "./pages/BacktestPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LiveMarketsPage } from "./pages/LiveMarketsPage";
import { OrdersPage } from "./pages/OrdersPage";
import { PositionsPage } from "./pages/PositionsPage";
import { RiskPage } from "./pages/RiskPage";
import { StrategiesPage } from "./pages/StrategiesPage";
import { api } from "./services/api";
import { KillSwitchStatus } from "./types";

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>("dashboard");
  const [killSwitch, setKillSwitch] = useState<KillSwitchStatus | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  useEffect(() => {
    initAuthAndPoll();
    const interval = setInterval(fetchKillStatus, 4000);
    return () => clearInterval(interval);
  }, []);

  const initAuthAndPoll = async () => {
    try {
      // Ensure we have an active session token for operator actions
      if (!localStorage.getItem("jwt_token")) {
        try {
          await api.register("operator@trading.com", "SecurePassword123!");
        } catch {}
        try {
          await api.login("operator@trading.com", "SecurePassword123!");
        } catch {}
      }
      await fetchKillStatus();
    } catch (e) {
      console.error(e);
    }
  };

  const fetchKillStatus = async () => {
    try {
      const risk = await api.getRiskStatus();
      setKillSwitch(risk.kill_switch);
    } catch {}
  };

  const handleActivateKillSwitch = async (reason: string) => {
    await api.activateKillSwitch(reason);
    await fetchKillStatus();
  };

  const handleDeactivateKillSwitch = async () => {
    await api.deactivateKillSwitch();
    await fetchKillStatus();
  };

  return (
    <div className="min-h-screen flex flex-col bg-dark-900 text-slate-100">
      {/* Global Navbar */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        killSwitch={killSwitch}
        onOpenKillSwitchModal={() => setIsModalOpen(true)}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activeTab === "dashboard" && <DashboardPage />}
        {activeTab === "markets" && <LiveMarketsPage />}
        {activeTab === "strategies" && <StrategiesPage />}
        {activeTab === "orders" && <OrdersPage />}
        {activeTab === "positions" && <PositionsPage />}
        {activeTab === "backtesting" && <BacktestPage />}
        {activeTab === "risk" && <RiskPage />}
      </main>

      {/* Footer */}
      <footer className="border-t border-dark-800 bg-dark-900 py-4 text-center text-xs text-slate-500 font-mono">
        AI Trading Engine • Production Grade Multi-Market Architecture • LIVE_TRADING=false Enforced
      </footer>

      {/* Emergency Kill Switch Modal */}
      <KillSwitchModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        status={killSwitch}
        onActivate={handleActivateKillSwitch}
        onDeactivate={handleDeactivateKillSwitch}
      />
    </div>
  );
};

export default App;
