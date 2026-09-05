import React from 'react';

interface StatusPillProps {
  status: string;
}

export const StatusPill: React.FC<StatusPillProps> = ({ status }) => {
  const s = (status || '').toUpperCase();

  let style = 'bg-slate-800 border-slate-700 text-slate-300';
  let label = s;

  switch (s) {
    case 'RECOVERED':
      style = 'bg-emerald-950/80 border-emerald-500/40 text-emerald-400 font-semibold';
      label = '● RECOVERED';
      break;
    case 'AWAITING_VERIFICATION':
      style = 'bg-sky-950/80 border-sky-500/40 text-sky-300 animate-pulse';
      label = '⚡ AWAITING VERIFICATION';
      break;
    case 'ACTION_ATTEMPTED':
      style = 'bg-cyan-950/80 border-cyan-500/40 text-cyan-300';
      label = 'ACTION ATTEMPTED';
      break;
    case 'POLICY_APPROVED':
      style = 'bg-teal-950/80 border-teal-500/40 text-teal-300';
      label = 'POLICY APPROVED';
      break;
    case 'STRATEGIES_EVALUATED':
      style = 'bg-indigo-950/80 border-indigo-500/40 text-indigo-300';
      label = 'STRATEGIES EVALUATED';
      break;
    case 'ELIGIBLE':
      style = 'bg-emerald-950/40 border-emerald-500/20 text-emerald-300';
      label = 'ELIGIBLE';
      break;
    case 'INELIGIBLE':
      style = 'bg-rose-950/50 border-rose-800/30 text-rose-400';
      label = 'INELIGIBLE';
      break;
    case 'POLICY_BLOCKED':
      style = 'bg-rose-950/80 border-rose-500/40 text-rose-300 font-semibold';
      label = 'POLICY BLOCKED';
      break;
    case 'ESCALATED':
    case 'HUMAN_REVIEW':
      style = 'bg-amber-950/80 border-amber-500/40 text-amber-300 font-semibold';
      label = 'HUMAN REVIEW / ESCALATED';
      break;
    case 'UNRECOVERED':
      style = 'bg-slate-900 border-slate-700 text-slate-400';
      label = 'UNRECOVERED';
      break;
    default:
      style = 'bg-slate-800 border-slate-700 text-slate-300';
      label = s;
  }

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded text-xs font-mono border ${style}`}>
      {label}
    </span>
  );
};
