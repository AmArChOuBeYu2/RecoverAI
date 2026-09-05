import React from 'react';
import type { DashboardSummary } from '../../types';
import { ArrowRight, ShieldCheck, Zap, Layers, AlertTriangle } from 'lucide-react';

interface HeroFunnelProps {
  summary: DashboardSummary | null;
}

export const HeroFunnelVisualization: React.FC<HeroFunnelProps> = ({ summary }) => {
  const atRisk = summary?.revenue_at_risk_rupees || 0;
  const eligibleCases = summary?.eligible_cases || 0;
  const totalCases = summary?.total_cases || 1;
  const eligibleRatio = Math.round((eligibleCases / totalCases) * 100);
  const actionsAttempted = summary?.total_actions_attempted || 0;
  const verifiedCases = summary?.verified_recovered_cases || 0;
  const verifiedRecoveredRupees = summary?.total_verified_recovered_rupees || 0;
  const recoveryRate = summary?.revenue_recovery_rate || 0;

  return (
    <div className="bg-slate-900/90 rounded-2xl border border-slate-800 p-6 shadow-2xl relative overflow-hidden my-6">
      {/* Background ambient lighting */}
      <div className="absolute top-0 right-0 w-96 h-96 bg-emerald-500/5 rounded-full blur-3xl pointer-events-none"></div>

      <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-800/80">
        <div>
          <h3 className="text-sm font-mono uppercase tracking-widest text-emerald-400 font-semibold flex items-center gap-2">
            <Zap className="w-4 h-4" />
            RECOVERY VALUE PIPELINE FLOW
          </h3>
          <p className="text-xs text-slate-400 mt-1">
            Real-time portfolio revenue progression from failure detection to authoritative verification
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono px-2.5 py-1 rounded-md bg-emerald-950/80 border border-emerald-500/30 text-emerald-300">
            {((recoveryRate || 0) * 100).toFixed(1)}% REVENUE RECOVERY RATE
          </span>
        </div>
      </div>

      {/* 5-Stage Value Flow */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-3 relative">
        {/* Stage 1: At Risk */}
        <div className="bg-slate-950/80 rounded-xl p-4 border border-rose-900/30 flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs text-rose-400 font-mono mb-2">
            <span>1. AT RISK</span>
            <AlertTriangle className="w-3.5 h-3.5" />
          </div>
          <div>
            <div className="font-serif-title text-2xl font-normal text-slate-100">
              ₹{atRisk.toLocaleString('en-IN')}
            </div>
            <p className="text-[11px] text-slate-400 mt-1">{totalCases} failed payments</p>
          </div>
        </div>

        {/* Stage 2: Eligible */}
        <div className="bg-slate-950/80 rounded-xl p-4 border border-slate-800 flex flex-col justify-between relative">
          <div className="hidden md:block absolute -left-3.5 top-1/2 -translate-y-1/2 z-10 text-slate-600">
            <ArrowRight className="w-4 h-4" />
          </div>
          <div className="flex items-center justify-between text-xs text-slate-400 font-mono mb-2">
            <span>2. ELIGIBLE</span>
            <Layers className="w-3.5 h-3.5 text-slate-500" />
          </div>
          <div>
            <div className="font-serif-title text-2xl font-normal text-slate-100">
              {eligibleCases} Cases
            </div>
            <p className="text-[11px] font-mono text-emerald-400 mt-1">{eligibleRatio}% Gated Eligible</p>
          </div>
        </div>

        {/* Stage 3: Strategy Selection */}
        <div className="bg-slate-950/80 rounded-xl p-4 border border-slate-800 flex flex-col justify-between relative">
          <div className="hidden md:block absolute -left-3.5 top-1/2 -translate-y-1/2 z-10 text-slate-600">
            <ArrowRight className="w-4 h-4" />
          </div>
          <div className="flex items-center justify-between text-xs text-indigo-400 font-mono mb-2">
            <span>3. OPTIMIZED STRATEGY</span>
          </div>
          <div>
            <div className="text-sm font-medium text-slate-200">
              4D Segment Match
            </div>
            <p className="text-[11px] text-slate-400 mt-1">Wilson score & AI Evidence</p>
          </div>
        </div>

        {/* Stage 4: Action Attempted */}
        <div className="bg-slate-950/80 rounded-xl p-4 border border-slate-800 flex flex-col justify-between relative">
          <div className="hidden md:block absolute -left-3.5 top-1/2 -translate-y-1/2 z-10 text-slate-600">
            <ArrowRight className="w-4 h-4" />
          </div>
          <div className="flex items-center justify-between text-xs text-cyan-400 font-mono mb-2">
            <span>4. BOUNDED ACTION</span>
          </div>
          <div>
            <div className="font-serif-title text-2xl font-normal text-slate-100">
              {actionsAttempted} Actions
            </div>
            <p className="text-[11px] text-slate-400 mt-1">Payment Links & Retries</p>
          </div>
        </div>

        {/* Stage 5: Verified Recovery */}
        <div className="bg-emerald-950/40 rounded-xl p-4 border border-emerald-500/40 flex flex-col justify-between relative shadow-lg">
          <div className="hidden md:block absolute -left-3.5 top-1/2 -translate-y-1/2 z-10 text-emerald-500">
            <ArrowRight className="w-4 h-4" />
          </div>
          <div className="flex items-center justify-between text-xs text-emerald-400 font-mono mb-2">
            <span>5. VERIFIED RECOVERED</span>
            <ShieldCheck className="w-4 h-4" />
          </div>
          <div>
            <div className="font-serif-title text-2xl font-bold text-emerald-300">
              ₹{verifiedRecoveredRupees.toLocaleString('en-IN')}
            </div>
            <p className="text-[11px] font-mono text-emerald-400 mt-1">{verifiedCases} Confirmed Recoveries</p>
          </div>
        </div>
      </div>
    </div>
  );
};
