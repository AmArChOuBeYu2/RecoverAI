import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { DashboardSummary, FailureBreakdownResponse, StrategyPerformanceSummaryResponse } from '../types';
import { Header } from '../components/layout/Header';
import { MetricCard } from '../components/common/MetricCard';
import { HeroFunnelVisualization } from '../components/overview/HeroFunnelVisualization';
import { ProvenanceBadge } from '../components/common/ProvenanceBadge';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import { DollarSign, ShieldCheck, Percent, Layers, Sparkles } from 'lucide-react';

export const OverviewPage: React.FC = () => {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [breakdown, setBreakdown] = useState<FailureBreakdownResponse | null>(null);
  const [strategies, setStrategies] = useState<StrategyPerformanceSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDemoRunning, setIsDemoRunning] = useState(false);
  const [demoBanner, setDemoBanner] = useState<string | null>(null);

  const loadDashboardData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sumRes, breakRes, stratRes] = await Promise.all([
        api.getDashboardSummary(),
        api.getFailureBreakdown(),
        api.getStrategyPerformance(),
      ]);
      setSummary(sumRes);
      setBreakdown(breakRes);
      setStrategies(stratRes);
    } catch (err: any) {
      setError(err.message || 'Failed to load executive dashboard summary');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  const handleStartGuidedDemo = async () => {
    setIsDemoRunning(true);
    setDemoBanner('Seeding 500 synthetic transaction records...');
    try {
      await api.seedDataset(500);
      setDemoBanner('Dataset seeded! Running end-to-end NIVARAN recovery pipeline...');
      await api.runBatchRecovery(500);
      setDemoBanner('Guided demo pipeline completed successfully! Portfolio metrics refreshed.');
      await loadDashboardData();
    } catch (err: any) {
      setError(`Guided demo error: ${err.message}`);
    } finally {
      setIsDemoRunning(false);
    }
  };

  return (
    <div>
      <Header
        pageTitle="Executive Overview"
        pageSubtitle="Portfolio-level revenue recovery intelligence, verified outcome learning, and strategy analytics"
        onStartDemo={handleStartGuidedDemo}
        isDemoRunning={isDemoRunning}
      />

      <div className="p-8 space-y-6 max-w-7xl mx-auto">
        {demoBanner && (
          <div className="p-4 rounded-xl bg-emerald-950/80 border border-emerald-500/40 text-emerald-300 text-xs font-mono flex items-center justify-between shadow-lg">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-emerald-400 animate-spin" />
              <span>{demoBanner}</span>
            </div>
            <button onClick={() => setDemoBanner(null)} className="text-slate-400 hover:text-slate-200">Dismiss</button>
          </div>
        )}

        {error && <ErrorState message={error} onRetry={loadDashboardData} />}

        {loading ? (
          <LoadingState message="Computing portfolio metrics & empirical strategy evidence..." />
        ) : summary ? (
          <>
            {/* Top Key Financial Metric Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <MetricCard
                title="REVENUE AT RISK"
                value={`₹${((summary.revenue_at_risk_rupees ?? summary.total_transaction_value_rupees) ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                subtitle={`${(summary.total_cases ?? summary.total_transaction_count) ?? 0} total failed transaction records`}
                accent="rose"
                icon={DollarSign}
              />
              <MetricCard
                title="VERIFIED RECOVERED"
                value={`₹${((summary.total_verified_recovered_rupees ?? summary.verified_recovered_rupees) ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                subtitle={(summary.verified_recovered_cases ?? summary.verified_recovered_count ?? 0) > 0 
                  ? `${summary.verified_recovered_cases ?? summary.verified_recovered_count} verified recovered payments` 
                  : "No authoritative Razorpay payment confirmation recorded yet"}
                accent="emerald"
                icon={ShieldCheck}
              />
              <MetricCard
                title="SIMULATED RECOVERED"
                value={`₹${(summary.simulated_recovered_rupees ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                subtitle={`${summary.simulated_recovered_count ?? 0} simulated batch recoveries (Simulation Engine)`}
                accent="teal"
                icon={Percent}
              />
              <MetricCard
                title="ELIGIBLE CASES GATED"
                value={summary.gated_eligible_cases ?? (summary.eligible_cases - (summary.policy_blocked_count ?? 0))}
                subtitle={`${summary.policy_blocked_count ?? summary.ineligible_cases ?? 0} cases blocked by policy rules`}
                accent="indigo"
                icon={Layers}
              />
            </div>

            {/* Hero Value Funnel Visualization */}
            <HeroFunnelVisualization summary={summary} />

            {/* Bottom Grid: Root Cause Breakdown & Strategy Distribution */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Failure Category Breakdown */}
              <div className="p-6 rounded-xl bg-slate-900/90 border border-slate-800 space-y-4 shadow-xl">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div>
                    <h4 className="text-sm font-semibold text-slate-100 font-mono">UNRECOVERED ROOT CAUSES</h4>
                    <p className="text-xs text-slate-400">Categorization of lost revenue by system root cause</p>
                  </div>
                  <ProvenanceBadge category="OBSERVED" size="sm" />
                </div>

                {breakdown?.categories && (
                  <div className="space-y-3">
                    {breakdown.categories.map((cat) => (
                      <div key={cat.category} className="space-y-1">
                        <div className="flex items-center justify-between text-xs font-mono">
                          <span className="text-slate-300 font-medium">{cat.category}</span>
                          <span className="text-slate-400">
                            ₹{(cat.amount_rupees ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ({(cat.percentage ?? 0).toFixed(1)}%)
                          </span>
                        </div>
                        <div className="w-full bg-slate-950 h-2 rounded-full overflow-hidden">
                          <div
                            className="bg-rose-500 h-full rounded-full transition-all"
                            style={{ width: `${cat.percentage ?? 0}%` }}
                          ></div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Top Performing Strategies Summary */}
              <div className="p-6 rounded-xl bg-slate-900/90 border border-slate-800 space-y-4 shadow-xl">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div>
                    <h4 className="text-sm font-semibold text-slate-100 font-mono">TOP RECOVERY STRATEGIES</h4>
                    <p className="text-xs text-slate-400">Strategy ranking by attempt-weighted recovery rate</p>
                  </div>
                  <ProvenanceBadge category={strategies?.evidence_category || 'SIMULATED'} size="sm" />
                </div>

                {strategies?.strategies && (
                  <div className="space-y-3">
                    {strategies.strategies.slice(0, 4).map((st) => {
                      const ratePct = Math.round(((st.recovery_rate ?? st.weighted_recovery_rate) ?? 0) * 100);
                      const recoveredRupees = st.total_recovered_rupees ?? ((st.total_recovered_paise ?? 0) / 100);
                      const category = st.evidence_category || 'SIMULATED';
                      const recoveryLabel = category === 'SIMULATED' ? 'Simulated Recoveries' : category === 'VERIFIED' ? 'Verified Recoveries' : 'Recoveries';

                      return (
                        <div key={st.strategy_type} className="p-3 rounded-lg bg-slate-950 border border-slate-800/80 flex items-center justify-between text-xs font-mono">
                          <div>
                            <span className="font-bold text-slate-100 block">{st.strategy_type}</span>
                            <span className="text-[11px] text-slate-400 mt-0.5 block">{st.attempt_count ?? 0} Attempts · {st.success_count ?? 0} {recoveryLabel}</span>
                          </div>
                          <div className="text-right">
                            <span className="text-emerald-400 font-bold text-sm block">{ratePct}%</span>
                            <span className="text-[10px] text-indigo-300">₹{recoveredRupees.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
};
