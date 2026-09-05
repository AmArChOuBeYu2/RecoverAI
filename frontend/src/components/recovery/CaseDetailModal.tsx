import React, { useEffect, useState } from 'react';
import { api } from '../../api/client';
import type { CaseContextResponse, DecisionResponse } from '../../types';
import { LifecycleStepper } from './LifecycleStepper';
import { DecisionReasoningCard } from './DecisionReasoningCard';
import { StatusPill } from '../common/StatusPill';
import { ProvenanceBadge } from '../common/ProvenanceBadge';
import { LoadingState } from '../common/LoadingState';
import { ErrorState } from '../common/ErrorState';
import { X, Play, ShieldCheck, CheckCircle2, User, CreditCard, Layers, ExternalLink } from 'lucide-react';

interface CaseDetailModalProps {
  caseId: string;
  onClose: () => void;
  onRefreshList?: () => void;
}

export const CaseDetailModal: React.FC<CaseDetailModalProps> = ({ caseId, onClose, onRefreshList }) => {
  const [context, setContext] = useState<CaseContextResponse | null>(null);
  const [decision, setDecision] = useState<DecisionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [executing, setExecuting] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [actionSuccessMsg, setActionSuccessMsg] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const ctx = await api.getCaseContext(caseId);
      setContext(ctx);

      try {
        const dec = await api.getCaseDecision(caseId);
        setDecision(dec);
      } catch {
        setDecision(null);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load case context');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [caseId]);

  const handleEvaluateStrategy = async () => {
    setLoading(true);
    try {
      const dec = await api.evaluateCaseStrategy(caseId, true);
      setDecision(dec);
      await loadData();
      if (onRefreshList) onRefreshList();
    } catch (err: any) {
      setError(err.message || 'Strategy evaluation failed');
      setLoading(false);
    }
  };

  const handleExecuteAction = async () => {
    setExecuting(true);
    setActionSuccessMsg(null);
    try {
      const res = await api.executeCaseAction(caseId);
      setActionSuccessMsg(`Action Executed Successfully! Type: ${res.action_type}, Mode: ${res.execution_mode}`);
      await loadData();
      if (onRefreshList) onRefreshList();
    } catch (err: any) {
      setError(err.message || 'Action execution failed');
    } finally {
      setExecuting(false);
    }
  };

  const handleVerifyOutcome = async () => {
    setVerifying(true);
    setActionSuccessMsg(null);
    try {
      const res = await api.verifyCaseOutcome(caseId);
      setActionSuccessMsg(`Verification Completed! Outcome: ${res.outcome}, Recovered: ₹${res.amount_recovered_rupees}`);
      await loadData();
      if (onRefreshList) onRefreshList();
    } catch (err: any) {
      setError(err.message || 'Outcome verification failed');
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden my-auto">
        
        {/* Modal Header */}
        <div className="p-6 border-b border-slate-800 flex items-center justify-between bg-slate-950/80">
          <div>
            <div className="flex items-center gap-3">
              <span className="font-mono text-xs text-slate-400">CASE INSPECTOR</span>
              {context && <StatusPill status={context.case_status} />}
            </div>
            <h3 className="font-serif-title text-2xl font-normal text-slate-100 mt-1">
              Case #{caseId.substring(0, 12)}...
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {actionSuccessMsg && (
            <div className="p-4 rounded-xl bg-emerald-950/80 border border-emerald-500/40 text-emerald-300 text-xs font-mono flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>{actionSuccessMsg}</span>
            </div>
          )}

          {error && <ErrorState message={error} onRetry={loadData} />}

          {loading ? (
            <LoadingState message="Assembling recovery context & decision trail..." />
          ) : context ? (
            <>
              {/* 9-Stage Visual Lifecycle Stepper */}
              <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800/80">
                <span className="text-[10px] font-mono text-slate-400 block mb-2">RECOVERY LIFECYCLE PROGRESSION</span>
                <LifecycleStepper currentStatus={context.case_status} />
              </div>

              {/* Transaction & Customer Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Transaction Card */}
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                  <div className="flex items-center gap-2 text-xs font-mono text-slate-400 mb-2">
                    <CreditCard className="w-4 h-4 text-emerald-400" />
                    <span>TRANSACTION DETAILS</span>
                  </div>
                  <div className="font-serif-title text-2xl text-slate-100">
                    ₹{context.transaction.amount_rupees.toLocaleString('en-IN')}
                  </div>
                  <div className="mt-2 space-y-1 text-xs font-mono text-slate-400">
                    <p>Method: <strong className="text-slate-200 uppercase">{context.transaction.payment_method}</strong></p>
                    <p>Payment ID: <span className="text-slate-300">{context.transaction.razorpay_payment_id}</span></p>
                    <p>Failure: <span className="text-rose-400 font-semibold">{context.transaction.failure_category}</span></p>
                  </div>
                </div>

                {/* Customer Card */}
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                  <div className="flex items-center gap-2 text-xs font-mono text-slate-400 mb-2">
                    <User className="w-4 h-4 text-teal-400" />
                    <span>CUSTOMER CONTEXT</span>
                  </div>
                  <div className="text-sm font-semibold text-slate-200">{context.customer.name}</div>
                  <p className="text-xs text-slate-400 font-mono">{context.customer.email}</p>
                  <div className="mt-2 space-y-1 text-xs font-mono text-slate-400">
                    <p>Type: <strong className="text-slate-200">{context.customer.customer_type}</strong></p>
                    <p>Prior History: <span className="text-emerald-400">{context.customer.successful_transactions} Paid</span> / <span className="text-rose-400">{context.customer.failed_transactions} Failed</span></p>
                  </div>
                </div>

                {/* 4D Segment Card */}
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                  <div className="flex items-center gap-2 text-xs font-mono text-slate-400 mb-2">
                    <Layers className="w-4 h-4 text-indigo-400" />
                    <span>4D CANONICAL SEGMENT</span>
                  </div>
                  <div className="text-xs font-mono font-semibold text-slate-200 truncate" title={context.segment?.name}>
                    {context.segment?.name || 'Unassigned'}
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1 line-clamp-2">
                    {context.segment?.description}
                  </p>
                  <div className="mt-2">
                    <ProvenanceBadge category="OBSERVED" size="sm" />
                  </div>
                </div>
              </div>

              {/* Explainable Decision Card */}
              <DecisionReasoningCard decision={decision} />

              {/* Prior Attempted Actions */}
              {context.prior_actions && context.prior_actions.length > 0 && (
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                  <h4 className="text-xs font-mono text-slate-400 mb-2">EXECUTED RECOVERY ACTIONS</h4>
                  <div className="space-y-2">
                    {context.prior_actions.map((act: any, idx: number) => (
                      <div key={idx} className="p-3 rounded bg-slate-900 border border-slate-800 flex items-center justify-between text-xs font-mono">
                        <div>
                          <span className="text-slate-200 font-semibold">{act.action_type}</span>
                          <span className="text-slate-500 ml-2">[{act.execution_mode}]</span>
                        </div>
                        <div className="flex items-center gap-3">
                          {act.payment_link_url && (
                            <a
                              href={act.payment_link_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-emerald-400 hover:underline inline-flex items-center gap-1"
                            >
                              <span>Payment Link</span>
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          )}
                          <span className="text-slate-400">{act.status}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : null}
        </div>

        {/* Modal Footer / Action Bar */}
        {context && (
          <div className="p-4 border-t border-slate-800 bg-slate-950/90 flex items-center justify-between">
            <div className="text-xs font-mono text-slate-400">
              Attempts: <span className="text-slate-200">{context.attempt_count}</span>
            </div>

            <div className="flex items-center gap-3">
              {context.case_status === 'ELIGIBLE' && (
                <button
                  onClick={handleEvaluateStrategy}
                  disabled={loading}
                  className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs transition-colors cursor-pointer"
                >
                  Evaluate AI & Evidence Strategy
                </button>
              )}

              {context.case_status === 'POLICY_APPROVED' && (
                <button
                  onClick={handleExecuteAction}
                  disabled={executing}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs shadow-lg transition-all cursor-pointer"
                >
                  <Play className={`w-3.5 h-3.5 ${executing ? 'animate-spin' : ''}`} />
                  <span>{executing ? 'Executing Action...' : 'EXECUTE BOUNDED ACTION (TEST MODE)'}</span>
                </button>
              )}

              {context.case_status === 'AWAITING_VERIFICATION' && (
                <button
                  onClick={handleVerifyOutcome}
                  disabled={verifying}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs shadow-lg transition-all cursor-pointer"
                >
                  <ShieldCheck className={`w-3.5 h-3.5 ${verifying ? 'animate-spin' : ''}`} />
                  <span>{verifying ? 'Verifying Outcome...' : 'VERIFY AUTHORITATIVE OUTCOME'}</span>
                </button>
              )}

              <button
                onClick={onClose}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors cursor-pointer"
              >
                Close Inspector
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
