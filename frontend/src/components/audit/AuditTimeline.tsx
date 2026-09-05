import React from 'react';
import type { AuditEventItem } from '../../types';

interface AuditTimelineProps {
  events: AuditEventItem[];
}

export const AuditTimeline: React.FC<AuditTimelineProps> = ({ events }) => {
  const getActorBadge = (actor: string) => {
    const act = (actor || '').toUpperCase();
    switch (act) {
      case 'POLICY_ENGINE':
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-teal-950 border border-teal-500/30 text-teal-300">POLICY ENGINE</span>;
      case 'AI_DIAGNOSIS':
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-indigo-950 border border-indigo-500/30 text-indigo-300">AI DIAGNOSIS</span>;
      case 'TRUST_GATE':
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-rose-950 border border-rose-500/30 text-rose-300">TRUST GATE</span>;
      case 'HUMAN':
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-amber-950 border border-amber-500/30 text-amber-300">HUMAN OPERATOR</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-400">SYSTEM</span>;
    }
  };

  return (
    <div className="space-y-4 relative before:absolute before:inset-0 before:left-6 before:w-0.5 before:bg-slate-800">
      {events.map((evt) => (
        <div key={evt.id} className="relative pl-12 group">
          {/* Node Icon */}
          <div className="absolute left-4 top-1 -translate-x-1/2 w-5 h-5 rounded-full bg-slate-900 border border-slate-700 group-hover:border-emerald-500 flex items-center justify-center text-slate-400 transition-colors">
            <div className="w-2 h-2 rounded-full bg-emerald-400"></div>
          </div>

          {/* Timeline Event Card */}
          <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 transition-colors space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold text-slate-100">{evt.event_type}</span>
                {getActorBadge(evt.actor)}
              </div>
              <span className="text-[11px] font-mono text-slate-500">
                {evt.created_at ? new Date(evt.created_at).toLocaleString() : 'N/A'}
              </span>
            </div>

            <p className="text-xs text-slate-300 font-sans leading-relaxed">
              {evt.description}
            </p>

            {evt.details && Object.keys(evt.details).length > 0 && (
              <details className="mt-2 text-xs font-mono text-slate-400">
                <summary className="cursor-pointer hover:text-slate-200">View Sanitized Event Metadata</summary>
                <pre className="mt-2 p-3 rounded bg-slate-950 border border-slate-800 text-[11px] text-emerald-400/90 overflow-x-auto">
                  {JSON.stringify(evt.details, null, 2)}
                </pre>
              </details>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};
