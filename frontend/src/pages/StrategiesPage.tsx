import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { StrategyPerformanceSummaryResponse } from '../types';
import { Header } from '../components/layout/Header';
import { StrategyAllocationChart } from '../components/strategies/StrategyAllocationChart';
import { StrategyComparisonTable } from '../components/strategies/StrategyComparisonTable';
import { ProvenanceBadge } from '../components/common/ProvenanceBadge';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import { Award } from 'lucide-react';

export const StrategiesPage: React.FC = () => {
  const [data, setData] = useState<StrategyPerformanceSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadStrategies = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getStrategyPerformance();
      setData(res);
    } catch (err: any) {
      setError(err.message || 'Failed to load strategy performance');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStrategies();
  }, []);

  return (
    <div>
      <Header
        pageTitle="Strategy Intelligence & Performance"
        pageSubtitle="Rank candidate recovery strategies by attempt-weighted recovery rate, Wilson lower bound, and Economic Strategy Value"
      />

      <div className="p-8 space-y-6 max-w-7xl mx-auto">
        {error && <ErrorState message={error} onRetry={loadStrategies} />}

        {loading ? (
          <LoadingState message="Computing strategy performance metrics & empirical evidence..." />
        ) : data ? (
          <>
            {/* Header Summary Banner */}
            <div className="p-6 rounded-xl bg-slate-900/90 border border-slate-800 flex items-center justify-between shadow-xl">
              <div>
                <span className="text-xs font-mono text-emerald-400">PORTFOLIO STRATEGY ALLOCATION SUMMARY</span>
                <div className="font-serif-title text-3xl font-normal text-slate-100 mt-1">
                  ₹{data.total_recovered_rupees.toLocaleString('en-IN')} Total Recovered
                </div>
                <p className="text-xs text-slate-400 mt-1">
                  Across {data.total_attempts} attempts & {data.total_successes} verified strategy recoveries
                </p>
              </div>

              <ProvenanceBadge category={data.evidence_category} size="lg" />
            </div>

            {/* Recharts Bar Visualization */}
            <StrategyAllocationChart strategies={data.strategies} />

            {/* Strategy Comparison Matrix Table */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-semibold text-slate-100 font-mono flex items-center gap-2">
                  <Award className="w-4 h-4 text-emerald-400" />
                  CANDIDATE STRATEGY ALLOCATION MATRIX
                </h4>
              </div>

              <StrategyComparisonTable strategies={data.strategies} />
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
};
