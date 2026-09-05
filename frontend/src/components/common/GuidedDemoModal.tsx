import React, { useState } from 'react';
import { api } from '../../api/client';
import { ShieldCheck, Play, CheckCircle2, AlertCircle, X, Loader2 } from 'lucide-react';

interface GuidedDemoModalProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete: () => void;
}

interface StepState {
  id: number;
  label: string;
  detail: string;
  status: 'idle' | 'running' | 'success' | 'error';
  resultInfo?: string;
}

export const GuidedDemoModal: React.FC<GuidedDemoModalProps> = ({ isOpen, onClose, onComplete }) => {
  const [running, setRunning] = useState(false);
  const [steps, setSteps] = useState<StepState[]>([
    { id: 1, label: 'Backend API Health Check', detail: 'Verifying FastAPI status & Razorpay configuration', status: 'idle' },
    { id: 2, label: 'Seed Synthetic Portfolio', detail: 'Generating 200 merchant failure transactions', status: 'idle' },
    { id: 3, label: 'Run Failure Detection', detail: 'Initializing recovery cases and canonical 4D taxonomy', status: 'idle' },
    { id: 4, label: 'Execute Recovery Pipeline', detail: 'Strategy selection, policy gate, action execution & verification', status: 'idle' },
    { id: 5, label: 'Policy Simulation', detail: 'Running counterfactual policy evaluation (Baseline vs Nivaran)', status: 'idle' },
    { id: 6, label: 'Portfolio Audit & Metrics', detail: 'Re-calculating portfolio KPIs and attribution stats', status: 'idle' },
  ]);

  if (!isOpen) return null;

  const updateStep = (id: number, status: 'running' | 'success' | 'error', resultInfo?: string) => {
    setSteps((prev) =>
      prev.map((s) => (s.id === id ? { ...s, status, resultInfo: resultInfo || s.resultInfo } : s))
    );
  };

  const handleStartDemo = async () => {
    setRunning(true);

    try {
      // Step 1: Health
      updateStep(1, 'running');
      const health = await api.getHealth();
      updateStep(1, 'success', `Service: ${health.service} v${health.version} (${health.status})`);

      // Step 2: Seed
      updateStep(2, 'running');
      const seedRes = await api.seedDataset(200);
      updateStep(2, 'success', `Seeded ${seedRes.transactions_created} transactions`);

      // Step 3: Detect
      updateStep(3, 'running');
      const detectRes = await api.runDetection(200);
      updateStep(3, 'success', `Detected ${detectRes.detected_count} recovery cases`);

      // Step 4: Run Recovery Pipeline
      updateStep(4, 'running');
      const runRes = await api.runBatchRecovery(200);
      updateStep(4, 'success', `Processed ${runRes.total_processed} cases, Recovered ₹${runRes.total_recovered_rupees.toLocaleString()}`);

      // Step 5: Simulator
      updateStep(5, 'running');
      const simRes = await api.getSimulatorCompare(200);
      updateStep(5, 'success', `Simulated Mode: ${simRes.simulation_mode}`);

      // Step 6: Summary Metrics
      updateStep(6, 'running');
      const summary = await api.getDashboardSummary();
      updateStep(6, 'success', `Portfolio Recovery Rate: ${(((summary?.revenue_recovery_rate ?? 0) * 100)).toFixed(1)}%`);

      setRunning(false);
      setTimeout(() => {
        onComplete();
      }, 500);
    } catch (err: any) {
      console.error('Guided Demo error:', err);
      setRunning(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-md p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-xl rounded-2xl bg-slate-900 border border-slate-800 shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="p-6 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center">
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-100 font-mono">NIVARAN GUIDED DEMO</h3>
              <p className="text-xs text-slate-400 font-sans">Live multi-step backend orchestration pipeline</p>
            </div>
          </div>
          <button onClick={onClose} disabled={running} className="text-slate-400 hover:text-slate-200 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Steps List */}
        <div className="p-6 space-y-4 overflow-y-auto font-mono text-xs">
          {steps.map((s) => (
            <div
              key={s.id}
              className={`p-4 rounded-xl border transition-all ${
                s.status === 'running'
                  ? 'bg-slate-950 border-emerald-500/50 shadow-lg shadow-emerald-500/5'
                  : s.status === 'success'
                  ? 'bg-slate-950/60 border-slate-800 text-slate-300'
                  : 'bg-slate-950/40 border-slate-800/60 text-slate-500'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2.5 font-semibold">
                  {s.status === 'running' ? (
                    <Loader2 className="w-4 h-4 text-emerald-400 animate-spin" />
                  ) : s.status === 'success' ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : s.status === 'error' ? (
                    <AlertCircle className="w-4 h-4 text-red-400" />
                  ) : (
                    <span className="w-4 h-4 rounded-full border border-slate-700 text-[10px] flex items-center justify-center text-slate-500">
                      {s.id}
                    </span>
                  )}
                  <span className={s.status === 'running' ? 'text-emerald-400' : 'text-slate-200'}>
                    {s.label}
                  </span>
                </div>

                {s.status === 'success' && (
                  <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-950 border border-emerald-500/30 text-emerald-300">
                    PASSED
                  </span>
                )}
              </div>

              <p className="text-[11px] text-slate-400 font-sans ml-6">{s.detail}</p>
              {s.resultInfo && (
                <div className="mt-2 ml-6 text-[10px] text-emerald-300 font-mono bg-emerald-950/40 p-2 rounded border border-emerald-900/50">
                  → {s.resultInfo}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Footer Actions */}
        <div className="p-6 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between">
          <span className="text-[11px] text-slate-500 font-mono">
            {running ? 'Orchestrating backend pipeline...' : 'Ready to execute live demo sequence'}
          </span>

          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              disabled={running}
              className="px-4 py-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 font-mono text-xs hover:bg-slate-800 transition-colors"
            >
              Close
            </button>
            <button
              onClick={handleStartDemo}
              disabled={running}
              className="px-5 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold font-mono text-xs transition-all shadow-lg shadow-emerald-500/20 flex items-center gap-2 disabled:opacity-50"
            >
              {running ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>RUNNING DEMO...</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  <span>START PIPELINE DEMO</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
