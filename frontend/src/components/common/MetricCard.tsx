import React from 'react';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: string;
  trendPositive?: boolean;
  accent?: 'emerald' | 'teal' | 'amber' | 'indigo' | 'rose' | 'default';
  icon?: React.ElementType;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtitle,
  trend,
  trendPositive = true,
  accent = 'default',
  icon: Icon,
}) => {
  const accentBorders = {
    emerald: 'border-l-4 border-l-emerald-500 border-t border-r border-b border-slate-800',
    teal: 'border-l-4 border-l-teal-500 border-t border-r border-b border-slate-800',
    amber: 'border-l-4 border-l-amber-500 border-t border-r border-b border-slate-800',
    indigo: 'border-l-4 border-l-indigo-500 border-t border-r border-b border-slate-800',
    rose: 'border-l-4 border-l-rose-500 border-t border-r border-b border-slate-800',
    default: 'border border-slate-800',
  }[accent];

  return (
    <div className={`bg-slate-900/80 rounded-lg p-5 shadow-lg relative overflow-hidden ${accentBorders}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs uppercase font-medium tracking-wider text-slate-400">{title}</span>
        {Icon && <Icon className="w-4 h-4 text-slate-500" />}
      </div>
      
      <div className="flex items-baseline gap-2">
        <div className="font-serif-title text-3xl md:text-4xl font-normal text-slate-50 tracking-tight">
          {value}
        </div>
        {trend && (
          <span className={`text-xs font-mono font-medium ${trendPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
            {trendPositive ? '↑' : '↓'} {trend}
          </span>
        )}
      </div>

      {subtitle && (
        <p className="text-xs text-slate-400 mt-2 font-sans line-clamp-1">{subtitle}</p>
      )}
    </div>
  );
};
