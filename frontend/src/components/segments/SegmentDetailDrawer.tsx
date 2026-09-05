import React, { useEffect, useState } from 'react';
import { api } from '../../api/client';
import type { SegmentDetailResponse } from '../../types';
import { LoadingState } from '../common/LoadingState';
import { ErrorState } from '../common/ErrorState';
import { ProvenanceBadge } from '../common/ProvenanceBadge';
import { X, Award } from 'lucide-react';

interface SegmentDetailDrawerProps {
  segmentId: string;
  onClose: () => void;
}

export const SegmentDetailDrawer: React.FC<SegmentDetailDrawerProps> = ({ segmentId, onClose }) => {
  const [segment, setSegment] = useState<SegmentDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api.getSegmentDetail(segmentId)
      .then(res => {
        setSegment(res);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message || 'Failed to load segment details');
        setLoading(false);
      });
  }, [segmentId]);

  return (
    <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex justify-end">
      <div className="bg-slate-900 border-l border-slate-800 w-full max-w-xl h-full flex flex-col shadow-2xl overflow-hidden">
        
        {/* Drawer Header */}
        <div className="p-6 border-b border-slate-800 flex items-center justify-between bg-slate-950">
          <div>
            <span className="text-xs font-mono text-emerald-400">CANONICAL 4D SEGMENT DETAIL</span>
            <h3 className="font-serif-title text-xl text-slate-100 mt-0.5 truncate max-w-md font-normal" title={segment?.name}>
              {segment?.name || 'Loading...'}
            </h3>
          </div>
          <button onClick={onClose} className="p-2 rounded hover:bg-slate-800 text-slate-400 cursor-pointer">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Drawer Content */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {error && <ErrorState message={error} />}

          {loading ? (
            <LoadingState message="Fetching segment strategy performance..." />
          ) : segment ? (
            <>
              {/* 4D Dimensions Pill Grid */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 grid grid-cols-2 gap-3 text-xs font-mono">
                <div>
                  <span className="text-slate-500 block text-[10px]">FAILURE CATEGORY</span>
                  <span className="text-rose-400 font-semibold">{segment.failure_category}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">PAYMENT METHOD</span>
                  <span className="text-indigo-300 font-semibold">{segment.payment_method.toUpperCase()}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">AMOUNT RANGE</span>
                  <span className="text-slate-200 font-semibold">{segment.amount_range}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">CUSTOMER TYPE</span>
                  <span className="text-slate-200 font-semibold">{segment.customer_type}</span>
                </div>
              </div>

              {/* Description */}
              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800/80">
                <span className="text-[10px] font-mono text-slate-400 block mb-1">SEGMENT DESCRIPTION</span>
                <p className="text-xs text-slate-300 font-sans leading-relaxed">{segment.description}</p>
              </div>

              {/* Strategy Rankings Table */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-xs font-mono font-semibold text-slate-200 flex items-center gap-2">
                    <Award className="w-4 h-4 text-emerald-400" />
                    CANDIDATE STRATEGY PERFORMANCE RANKING
                  </h4>
                  <ProvenanceBadge category="OBSERVED" size="sm" />
                </div>

                <div className="space-y-3">
                  {segment.strategies.map((st) => {
                    const ratePct = Math.round((st.recovery_rate || 0) * 100);
                    const wilsonPct = Math.round((st.wilson_lower_bound || 0) * 100);

                    return (
                      <div key={st.id} className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                        <div className="flex items-center justify-between font-mono text-xs">
                          <span className="font-bold text-slate-100">{st.strategy_type}</span>
                          <span className="text-emerald-400 font-bold">{ratePct}% Recovery</span>
                        </div>

                        {/* Progress Bar */}
                        <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                          <div className="bg-emerald-500 h-full rounded-full transition-all" style={{ width: `${ratePct}%` }}></div>
                        </div>

                        <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 pt-1">
                          <span>Attempts: <strong className="text-slate-200">{st.attempt_count}</strong> ({st.success_count} Recovered)</span>
                          <span>Wilson Lower Bound: <strong className="text-indigo-300">{wilsonPct}%</strong></span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-950 text-right">
          <button onClick={onClose} className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg cursor-pointer">
            Close Drawer
          </button>
        </div>
      </div>
    </div>
  );
};
