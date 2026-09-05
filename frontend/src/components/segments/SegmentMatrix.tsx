import React from 'react';
import type { SegmentItem } from '../../types';

interface SegmentMatrixProps {
  segments: SegmentItem[];
  onSelectSegment: (segmentId: string) => void;
}

export const SegmentMatrix: React.FC<SegmentMatrixProps> = ({ segments, onSelectSegment }) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {segments.map((seg) => {
        const ratePct = seg.total_attempts > 0 ? Math.round((seg.total_recoveries / seg.total_attempts) * 100) : 0;
        
        return (
          <div
            key={seg.id}
            onClick={() => onSelectSegment(seg.id)}
            className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-emerald-500/40 transition-all cursor-pointer group flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-950 border border-indigo-500/30 text-indigo-300">
                  {(seg.payment_method || 'ANY').toUpperCase()}
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                  {seg.amount_range}
                </span>
              </div>

              <h4 className="text-sm font-semibold text-slate-100 font-mono group-hover:text-emerald-400 transition-colors line-clamp-1" title={seg.name}>
                {seg.name}
              </h4>
              <p className="text-xs text-slate-400 mt-1 line-clamp-2 font-sans">
                {seg.description}
              </p>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs font-mono">
              <div>
                <span className="text-slate-400 block text-[10px]">HISTORICAL RATE</span>
                <span className="text-emerald-400 font-bold text-sm">{ratePct}% Recovery</span>
              </div>

              <div className="text-right">
                <span className="text-slate-400 block text-[10px]">ATTEMPTS</span>
                <span className="text-slate-200 font-semibold">{seg.total_attempts}</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};
