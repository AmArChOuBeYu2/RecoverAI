import React from 'react';
import { ShieldCheck, Eye, Cpu, BarChart3 } from 'lucide-react';

interface ProvenanceBadgeProps {
  category: 'VERIFIED' | 'OBSERVED' | 'SIMULATED' | 'PROJECTED' | string;
  size?: 'sm' | 'md' | 'lg';
}

export const ProvenanceBadge: React.FC<ProvenanceBadgeProps> = ({ category, size = 'md' }) => {
  const cat = (category || 'OBSERVED').toUpperCase();

  const config = {
    VERIFIED: {
      label: 'VERIFIED OUTCOME',
      bg: 'bg-emerald-950/70 border-emerald-500/30 text-emerald-400',
      dot: 'bg-emerald-400',
      icon: ShieldCheck,
    },
    OBSERVED: {
      label: 'EMPIRICAL OBSERVED',
      bg: 'bg-teal-950/70 border-teal-500/30 text-teal-300',
      dot: 'bg-teal-400',
      icon: Eye,
    },
    SIMULATED: {
      label: 'LOCAL SIMULATION',
      bg: 'bg-amber-950/70 border-amber-500/30 text-amber-400',
      dot: 'bg-amber-400',
      icon: Cpu,
    },
    PROJECTED: {
      label: 'PROJECTED MODEL',
      bg: 'bg-indigo-950/70 border-indigo-500/30 text-indigo-300',
      dot: 'bg-indigo-400',
      icon: BarChart3,
    },
  }[cat] || {
    label: cat,
    bg: 'bg-slate-800 border-slate-700 text-slate-300',
    dot: 'bg-slate-400',
    icon: Eye,
  };

  const Icon = config.icon;
  const padding = size === 'sm' ? 'px-2 py-0.5 text-xs' : size === 'lg' ? 'px-3 py-1.5 text-sm font-medium' : 'px-2.5 py-1 text-xs font-medium';

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border ${config.bg} ${padding} tracking-wide`}>
      <Icon className={size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5'} />
      <span>{config.label}</span>
    </span>
  );
};
