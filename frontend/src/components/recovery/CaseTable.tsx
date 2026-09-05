import React from 'react';
import type { RecoveryCaseItem } from '../../types';
import { StatusPill } from '../common/StatusPill';
import { Eye, ChevronRight } from 'lucide-react';

interface CaseTableProps {
  cases: RecoveryCaseItem[];
  onSelectCase: (caseId: string) => void;
}

export const CaseTable: React.FC<CaseTableProps> = ({ cases, onSelectCase }) => {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/60 shadow-xl">
      <table className="w-full text-left text-xs">
        <thead className="bg-slate-950/80 text-slate-400 font-mono border-b border-slate-800">
          <tr>
            <th className="px-4 py-3 font-medium">RECOVERY CASE ID</th>
            <th className="px-4 py-3 font-medium">TRANSACTION ID</th>
            <th className="px-4 py-3 font-medium">SEGMENT</th>
            <th className="px-4 py-3 font-medium">STATUS</th>
            <th className="px-4 py-3 font-medium text-center">ATTEMPTS</th>
            <th className="px-4 py-3 font-medium">DETECTED AT</th>
            <th className="px-4 py-3 font-medium text-right">ACTION</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/60 text-slate-300 font-sans">
          {cases.map((c) => (
            <tr key={c.id} className="hover:bg-slate-800/40 transition-colors group">
              <td className="px-4 py-3 font-mono font-medium text-slate-200">
                {c.id.substring(0, 8)}...
              </td>
              <td className="px-4 py-3 font-mono text-slate-400">
                {c.transaction_id.substring(0, 8)}...
              </td>
              <td className="px-4 py-3">
                <span className="inline-block max-w-[180px] truncate text-slate-300 font-mono text-[11px]" title={c.segment_name || 'Unassigned'}>
                  {c.segment_name || 'Unassigned'}
                </span>
              </td>
              <td className="px-4 py-3">
                <StatusPill status={c.status} />
              </td>
              <td className="px-4 py-3 text-center font-mono">
                {c.attempt_count}
              </td>
              <td className="px-4 py-3 font-mono text-slate-400 text-[11px]">
                {c.detected_at ? new Date(c.detected_at).toLocaleString() : 'N/A'}
              </td>
              <td className="px-4 py-3 text-right">
                <button
                  onClick={() => onSelectCase(c.id)}
                  className="inline-flex items-center gap-1 px-3 py-1 rounded bg-slate-800 hover:bg-emerald-600 text-slate-300 hover:text-white font-medium transition-colors cursor-pointer"
                >
                  <Eye className="w-3.5 h-3.5" />
                  <span>Inspect</span>
                  <ChevronRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
