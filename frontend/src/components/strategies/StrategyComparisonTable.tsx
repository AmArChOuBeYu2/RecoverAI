import React from 'react';
import type { StrategySummaryItem } from '../../types';
import { ProvenanceBadge } from '../common/ProvenanceBadge';

interface StrategyComparisonTableProps {
  strategies: StrategySummaryItem[];
}

export const StrategyComparisonTable: React.FC<StrategyComparisonTableProps> = ({ strategies }) => {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/80 shadow-xl">
      <table className="w-full text-left text-xs">
        <thead className="bg-slate-950 text-slate-400 font-mono border-b border-slate-800">
          <tr>
            <th className="px-4 py-3 font-medium">RECOVERY STRATEGY</th>
            <th className="px-4 py-3 font-medium text-center">ATTEMPTS</th>
            <th className="px-4 py-3 font-medium text-center">SUCCESSES</th>
            <th className="px-4 py-3 font-medium text-right">TOTAL RECOVERED (₹)</th>
            <th className="px-4 py-3 font-medium text-center">RECOVERY RATE</th>
            <th className="px-4 py-3 font-medium text-center">WILSON LOWER BOUND</th>
            <th className="px-4 py-3 font-medium text-right">ECONOMIC VALUE SCORE</th>
            <th className="px-4 py-3 font-medium text-center">EVIDENCE PROVENANCE</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/60 font-mono text-slate-200">
          {strategies.map((st) => {
            const ratePct = Math.round((st.weighted_recovery_rate || 0) * 100);
            const wilsonPct = Math.round((st.wilson_lower_bound || 0) * 100);

            return (
              <tr key={st.strategy_type} className="hover:bg-slate-800/40 transition-colors">
                <td className="px-4 py-3.5 font-bold text-slate-100">
                  {st.strategy_type}
                </td>
                <td className="px-4 py-3.5 text-center text-slate-300">
                  {st.attempt_count}
                </td>
                <td className="px-4 py-3.5 text-center text-emerald-400 font-semibold">
                  {st.success_count}
                </td>
                <td className="px-4 py-3.5 text-right font-bold text-emerald-300">
                  ₹{(st.total_recovered_rupees ?? (st.total_recovered_paise / 100)).toLocaleString('en-IN')}
                </td>
                <td className="px-4 py-3.5 text-center font-bold text-emerald-400">
                  {ratePct}%
                </td>
                <td className="px-4 py-3.5 text-center text-indigo-300">
                  {wilsonPct}%
                </td>
                <td className="px-4 py-3.5 text-right text-slate-300">
                  {st.economic_strategy_value ? st.economic_strategy_value.toFixed(2) : '0.00'}
                </td>
                <td className="px-4 py-3.5 text-center">
                  <ProvenanceBadge category={st.evidence_category} size="sm" />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
