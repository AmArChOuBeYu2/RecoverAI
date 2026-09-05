import React from 'react';
import type { SimulatorCompareResponse } from '../../types';
import { ProvenanceBadge } from '../common/ProvenanceBadge';
import { TrendingUp, CheckCircle } from 'lucide-react';

interface PolicyCompareCardProps {
  data: SimulatorCompareResponse | null;
}

export const PolicyCompareCard: React.FC<PolicyCompareCardProps> = ({ data }) => {
  if (!data) return null;

  const d = data as any;
  const baseline = d.baseline_policy || d.baseline || {};
  const optimized = d.nivaran_optimized_policy || d.recoverai_optimized || {};
  const uplift = d.projected_uplift || d.incremental_comparison || {};

  const baselineRate = Math.round(((baseline.recovery_rate ?? baseline.projected_recovery_rate) || 0) * 100);
  const optimizedRate = Math.round(((optimized.recovery_rate ?? optimized.projected_recovery_rate) || 0) * 100);
  const upliftRate = Math.round(((uplift.incremental_recovery_rate ?? uplift.incremental_recovery_rate_diff) || 0) * 100);
  const incrementalRupees = uplift.incremental_recovered_rupees || 0;
  const percentageImprovement = uplift.percentage_improvement || 0;

  return (
    <div className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-2xl space-y-6 my-6 relative overflow-hidden">
      {/* Simulation Banner */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <h3 className="text-base font-semibold text-slate-100 font-mono">POLICY SIMULATOR — BEFORE / AFTER COMPARISON</h3>
            <ProvenanceBadge category="PROJECTED" size="md" />
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Evaluates baseline policy (retry once) vs. NIVARAN 4D segment-aware strategy engine across {data.total_transactions_evaluated} transactions
          </p>
        </div>
      </div>

      {/* Side-by-Side Comparison Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Baseline Policy Card */}
        <div className="p-5 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
          <div className="text-xs font-mono text-slate-400 uppercase tracking-wider">
            BASELINE POLICY (GENERIC RETRY)
          </div>
          <div className="font-serif-title text-3xl text-slate-300">
            ₹{(baseline?.projected_recovered_rupees ?? 0).toLocaleString('en-IN')}
          </div>
          <div className="flex items-center justify-between text-xs font-mono text-slate-400 pt-2 border-t border-slate-800/80">
            <span>Projected Recovery Rate:</span>
            <span className="text-slate-200 font-bold">{baselineRate}%</span>
          </div>
        </div>

        {/* NIVARAN Optimized Card */}
        <div className="p-5 rounded-xl bg-emerald-950/40 border border-emerald-500/40 space-y-3 shadow-lg relative">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-emerald-400 font-bold tracking-wider">
              NIVARAN OPTIMIZED POLICY
            </span>
            <CheckCircle className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="font-serif-title text-3xl text-emerald-300 font-bold">
            ₹{(optimized?.projected_recovered_rupees ?? 0).toLocaleString('en-IN')}
          </div>
          <div className="flex items-center justify-between text-xs font-mono text-emerald-400 pt-2 border-t border-emerald-800/40">
            <span>Optimized Recovery Rate:</span>
            <span className="text-emerald-300 font-bold text-sm">{optimizedRate}%</span>
          </div>
        </div>

        {/* Projected Uplift Highlight Card */}
        <div className="p-5 rounded-xl bg-indigo-950/40 border border-indigo-500/40 space-y-3 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-1.5 text-xs font-mono text-indigo-400 font-semibold tracking-wider mb-2">
              <TrendingUp className="w-4 h-4" />
              <span>PROJECTED INCREMENTAL UPLIFT</span>
            </div>
            <div className="font-serif-title text-3xl text-indigo-200 font-bold">
              +₹{incrementalRupees.toLocaleString('en-IN')}
            </div>
            <p className="text-xs text-indigo-300/80 mt-1 font-mono">
              +{upliftRate}% Absolute Rate Uplift (+{percentageImprovement.toFixed(1)}% Improvement)
            </p>
          </div>
          <div className="text-[11px] font-mono text-slate-400 bg-slate-950/60 p-2 rounded border border-slate-800">
            READ-ONLY GUARANTEE: Zero Razorpay API calls or database mutations executed during policy simulation.
          </div>
        </div>
      </div>
    </div>
  );
};
