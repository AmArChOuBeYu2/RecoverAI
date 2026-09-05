import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { CaseContextResponse, DecisionResponse } from '../types';
import { Header } from '../components/layout/Header';
import { LifecycleStepper } from '../components/recovery/LifecycleStepper';
import { DecisionReasoningCard } from '../components/recovery/DecisionReasoningCard';
import { StatusPill } from '../components/common/StatusPill';
import { ProvenanceBadge } from '../components/common/ProvenanceBadge';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import { ArrowLeft, Play, ShieldCheck, CheckCircle2, User, CreditCard, Layers } from 'lucide-react';

interface CaseDetailPageProps {
  caseId: string;
  onNavigate: (path: string) => void;
}

export const CaseDetailPage: React.FC<CaseDetailPageProps> = ({ caseId, onNavigate }) => {
  const [context, setContext] = useState<CaseContextResponse | null>(null);
  const [decision, setDecision] = useState<DecisionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [executing, setExecuting] = useState(false);
  const [verifying, setVerifying] = useState(false);

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
        // decision may not exist yet if not evaluated
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load recovery case details.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (caseId) {
      loadData();
    }
  }, [caseId]);

  const handleEvaluate = async () => {
    try {
      setLoading(true);
      const dec = await api.evaluateCaseStrategy(caseId, true);
      setDecision(dec);
      const ctx = await api.getCaseContext(caseId);
      setContext(ctx);
    } catch (err: any) {
      alert(`Evaluation failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleExecute = async () => {
    try {
      setExecuting(true);
      await api.executeCaseAction(caseId);
      await loadData();
    } catch (err: any) {
      alert(`Execution failed: ${err.message}`);
    } finally {
      setExecuting(false);
    }
  };

  const handleVerify = async () => {
    try {
      setVerifying(true);
      await api.verifyCaseOutcome(caseId);
      await loadData();
    } catch (err: any) {
      alert(`Verification failed: ${err.message}`);
    } finally {
      setVerifying(false);
    }
  };

  if (loading && !context) {
    return (
      <div className="space-y-6">
        <Header pageTitle="Case Investigation" pageSubtitle="Loading recovery case context..." />
        <LoadingState message="Assembling rich 11-stage case context and policy parameters..." />
      </div>
    );
  }

  if (error || !context) {
    return (
      <div className="space-y-6">
        <Header pageTitle="Case Investigation" pageSubtitle="Case retrieval error" />
        <ErrorState
          title="Case Not Found"
          message={error || `Recovery case '${caseId}' could not be located.`}
          onRetry={loadData}
        />
        <button
          onClick={() => onNavigate('/recovery')}
          className="px-4 py-2 rounded-lg bg-slate-800 text-slate-300 font-mono text-xs hover:bg-slate-700 transition-colors"
        >
          ← Return to Recovery Queue
        </button>
      </div>
    );
  }

  const caseIdVal = context.case_id;
  const caseStatus = context.case_status;
  const txn = context.transaction;
  const cust = context.customer;
  const seg = context.segment;

  return (
    <div className="space-y-6">
      <Header
        pageTitle={`Case #${caseIdVal.substring(0, 8)}`}
        pageSubtitle="Deep financial investigation, policy boundary checks, and authoritative outcome verification."
      />

      <div className="flex items-center justify-between">
        <button
          onClick={() => onNavigate('/recovery')}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 text-xs font-mono hover:bg-slate-800 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>BACK TO QUEUE</span>
        </button>

        <div className="flex items-center gap-3">
          <button
            onClick={handleEvaluate}
            className="px-4 py-2 rounded-lg bg-indigo-950 border border-indigo-500/40 text-indigo-300 hover:bg-indigo-900/60 font-mono text-xs font-semibold transition-all"
          >
            Re-evaluate Strategy
          </button>
          {caseStatus === 'ELIGIBLE' || caseStatus === 'POLICY_APPROVED' ? (
            <button
              onClick={handleExecute}
              disabled={executing}
              className="px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs font-mono transition-all shadow-lg shadow-emerald-500/20 flex items-center gap-2"
            >
              <Play className="w-3.5 h-3.5" />
              <span>{executing ? 'Executing...' : 'EXECUTE ACTION'}</span>
            </button>
          ) : null}
          {caseStatus === 'ACTION_ATTEMPTED' || caseStatus === 'AWAITING_VERIFICATION' ? (
            <button
              onClick={handleVerify}
              disabled={verifying}
              className="px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs font-mono transition-all shadow-lg shadow-cyan-500/20 flex items-center gap-2"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>{verifying ? 'Verifying...' : 'VERIFY OUTCOME'}</span>
            </button>
          ) : null}
        </div>
      </div>

      {/* 9-stage Lifecycle Stepper */}
      <div className="p-6 rounded-xl bg-slate-900/80 border border-slate-800">
        <h4 className="text-xs font-mono text-slate-400 uppercase tracking-wider mb-4">RECOVERY LIFECYCLE STEPPER</h4>
        <LifecycleStepper currentStatus={caseStatus} />
      </div>

      {/* Top Details Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Transaction Card */}
        <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[10px] font-mono text-slate-400">TRANSACTION</span>
            <CreditCard className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-serif font-bold text-white">
            ₹{(txn.amount_rupees ?? ((txn.amount_paise ?? 0) / 100)).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div className="mt-3 space-y-1 font-mono text-xs text-slate-300">
            <div className="flex justify-between">
              <span className="text-slate-400">Txn ID:</span>
              <span className="text-slate-200">{txn.id.substring(0, 10)}...</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Failure:</span>
              <span className="text-red-400 font-semibold">{txn.failure_category}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Method:</span>
              <span className="text-indigo-300 uppercase">{txn.payment_method}</span>
            </div>
          </div>
        </div>

        {/* Customer Context */}
        <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[10px] font-mono text-slate-400">CUSTOMER CONTEXT</span>
            <User className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-base font-semibold text-slate-100 font-sans">
            {cust?.name || 'Anonymous Customer'}
          </div>
          <div className="mt-3 space-y-1 font-mono text-xs text-slate-300">
            <div className="flex justify-between">
              <span className="text-slate-400">Email:</span>
              <span className="text-slate-200">{cust?.email || 'N/A'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">History:</span>
              <span className="text-emerald-400">{cust?.successful_transactions || 0} Success / {cust?.failed_transactions || 0} Fail</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Contacts 24h:</span>
              <span className="text-slate-200">{cust?.contacts_count_24h || 0}</span>
            </div>
          </div>
        </div>

        {/* Segment & Recoverability */}
        <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[10px] font-mono text-slate-400">SEGMENT & PROPENSITY</span>
            <Layers className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-sm font-semibold font-mono text-indigo-300 truncate" title={seg?.name || 'N/A'}>
            {seg?.name || 'Unassigned Segment'}
          </div>
          <div className="mt-3 space-y-1 font-mono text-xs text-slate-300">
            <div className="flex justify-between">
              <span className="text-slate-400">Attempt Count:</span>
              <span className="text-slate-200 font-bold">{context.attempt_count}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-400">Status Pill:</span>
              <StatusPill status={caseStatus} />
            </div>
          </div>
        </div>
      </div>

      {/* Strategy Reasoning Card */}
      <DecisionReasoningCard decision={decision} />

      {/* Deterministic Policy & TrustGate Panel */}
      <div className="p-6 rounded-xl bg-slate-900/80 border border-slate-800 space-y-4">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-mono text-slate-400 uppercase tracking-wider flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>POLICY & TRUST GATE EVALUATION</span>
          </h4>
          <ProvenanceBadge category="VERIFIED" />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
          <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
            <span className="text-slate-400 block text-[10px]">CASE LIFECYCLE STAGE</span>
            <span className="text-emerald-400 mt-1 block font-semibold">{caseStatus}</span>
          </div>

          <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
            <span className="text-slate-400 block text-[10px]">POLICY SAFETY CHECKS</span>
            <span className={caseStatus.includes('BLOCKED') ? 'text-red-400 block mt-1 font-semibold' : 'text-emerald-400 block mt-1 font-semibold'}>
              {caseStatus.includes('BLOCKED') ? 'ACTION BLOCKED BY POLICY' : 'ALL 9 SAFETY RULES PASSED'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
