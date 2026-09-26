import React, { useState } from "react";
import { AlertOctagon, CheckCircle2, ShieldAlert, X } from "lucide-react";
import { KillSwitchStatus } from "../types";

interface KillSwitchModalProps {
  isOpen: boolean;
  onClose: () => void;
  status: KillSwitchStatus | null;
  onActivate: (reason: string) => Promise<void>;
  onDeactivate: () => Promise<void>;
}

export const KillSwitchModal: React.FC<KillSwitchModalProps> = ({
  isOpen,
  onClose,
  status,
  onActivate,
  onDeactivate,
}) => {
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const isActive = status?.is_active ?? false;

  const handleAction = async () => {
    setLoading(true);
    setError(null);
    try {
      if (isActive) {
        await onDeactivate();
      } else {
        if (!reason.trim()) {
          setError("A valid operational reason is required to activate the kill switch.");
          setLoading(false);
          return;
        }
        await onActivate(reason);
      }
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to execute kill switch command.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="bg-dark-800 border border-dark-600 rounded-xl max-w-md w-full shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className={`p-4 flex items-center justify-between border-b ${
          isActive ? "bg-red-950/40 border-red-900/50" : "bg-dark-700/50 border-dark-600"
        }`}>
          <div className="flex items-center space-x-2">
            {isActive ? (
              <AlertOctagon className="w-5 h-5 text-red-500" />
            ) : (
              <ShieldAlert className="w-5 h-5 text-amber-500" />
            )}
            <h3 className="font-bold text-slate-100">
              {isActive ? "Disengage Emergency Kill Switch" : "Emergency Kill Switch Activation"}
            </h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4">
          {isActive ? (
            <div className="space-y-3">
              <div className="p-3 bg-red-950/30 border border-red-900/60 rounded-lg text-sm text-red-300">
                <p className="font-bold">Trading is currently HALTED.</p>
                <p className="text-xs text-red-400 mt-1">Reason: {status?.reason}</p>
                <p className="text-xs text-slate-400 mt-1">Operator: {status?.operator_id}</p>
              </div>
              <p className="text-sm text-slate-300">
                Disengaging the kill switch will restore order submission capabilities. Ensure market
                conditions are stable before proceeding.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-slate-300">
                Activating the Emergency Kill Switch will immediately:
              </p>
              <ul className="text-xs space-y-1.5 text-slate-400 list-disc list-inside">
                <li>Block all incoming order submissions</li>
                <li>Halt automated strategy execution</li>
                <li>Lock the pre-trade risk engine with HTTP 423 Locked</li>
                <li>Record an immutable event in the audit trail</li>
              </ul>

              <div className="pt-2">
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                  Operational Justification (Required)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Extreme market volatility / upstream feed failure"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className="w-full bg-dark-900 border border-dark-600 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-red-500"
                />
              </div>
            </div>
          )}

          {error && (
            <div className="p-2.5 rounded bg-red-950/50 border border-red-800 text-xs text-red-400">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 bg-dark-900/50 border-t border-dark-700 flex justify-end space-x-3">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm font-medium text-slate-400 hover:text-slate-200 hover:bg-dark-700 transition"
          >
            Cancel
          </button>
          <button
            onClick={handleAction}
            disabled={loading}
            className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center space-x-2 transition ${
              isActive
                ? "bg-emerald-600 hover:bg-emerald-500 text-white"
                : "bg-red-600 hover:bg-red-500 text-white shadow-lg shadow-red-600/30"
            }`}
          >
            {isActive ? (
              <>
                <CheckCircle2 className="w-4 h-4" />
                <span>{loading ? "Disengaging..." : "Disengage Kill Switch"}</span>
              </>
            ) : (
              <>
                <AlertOctagon className="w-4 h-4" />
                <span>{loading ? "Activating..." : "Engage Emergency Kill Switch"}</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
