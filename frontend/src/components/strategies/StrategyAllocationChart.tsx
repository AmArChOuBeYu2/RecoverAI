import React from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell } from 'recharts';
import type { StrategySummaryItem } from '../../types';

interface StrategyAllocationChartProps {
  strategies: StrategySummaryItem[];
}

export const StrategyAllocationChart: React.FC<StrategyAllocationChartProps> = ({ strategies }) => {
  const chartData = (strategies || []).map((st) => ({
    name: st.strategy_type,
    rate: Math.round(((st.recovery_rate ?? st.weighted_recovery_rate) || 0) * 100),
    wilson: Math.round((st.wilson_lower_bound || 0) * 100),
    recoveredRupees: st.total_recovered_rupees ?? ((st.total_recovered_paise ?? 0) / 100),
    attempts: st.attempt_count,
  }));

  const COLORS = ['#10B981', '#14B8A6', '#06B6D4', '#3B82F6', '#6366F1', '#8B5CF6', '#F59E0B'];

  return (
    <div className="p-6 rounded-xl bg-slate-900/90 border border-slate-800 shadow-xl my-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h4 className="text-sm font-semibold text-slate-100 font-mono">PORTFOLIO STRATEGY RECOVERY RATES (%)</h4>
          <p className="text-xs text-slate-400">Weighted recovery rates across all canonical segments</p>
        </div>
      </div>

      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 20, right: 20, left: 0, bottom: 20 }}>
            <XAxis dataKey="name" stroke="#64748B" fontSize={11} tickLine={false} />
            <YAxis stroke="#64748B" fontSize={11} tickLine={false} unit="%" domain={[0, 100]} />
            <Tooltip
              contentStyle={{ backgroundColor: '#0F172A', borderColor: '#334155', borderRadius: '8px', fontSize: '12px' }}
              formatter={(val: any) => [`${val}%`, 'Recovery Rate']}
            />
            <Bar dataKey="rate" radius={[6, 6, 0, 0]}>
              {chartData.map((_, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
