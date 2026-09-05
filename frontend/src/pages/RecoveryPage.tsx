import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { RecoveryCaseItem } from '../types';
import { Header } from '../components/layout/Header';
import { CaseTable } from '../components/recovery/CaseTable';
import { CaseDetailModal } from '../components/recovery/CaseDetailModal';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import { Search, Filter, Play } from 'lucide-react';

export const RecoveryPage: React.FC = () => {
  const [cases, setCases] = useState<RecoveryCaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);

  const [batchRunning, setBatchRunning] = useState(false);

  const loadCases = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listCases({
        status: selectedStatus || undefined,
        limit: 100,
      });
      setCases(res.cases || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load recovery cases');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCases();
  }, [selectedStatus]);

  const filteredCases = cases.filter((c) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      c.id.toLowerCase().includes(q) ||
      c.transaction_id.toLowerCase().includes(q) ||
      (c.segment_name && c.segment_name.toLowerCase().includes(q))
    );
  });

  const handleRunBatch = async () => {
    setBatchRunning(true);
    try {
      await api.runBatchRecovery(100);
      await loadCases();
    } catch (err: any) {
      setError(err.message || 'Batch run failed');
    } finally {
      setBatchRunning(false);
    }
  };

  return (
    <div>
      <Header
        pageTitle="Recovery Queue & Operations"
        pageSubtitle="Inspect recovery cases, evaluate AI strategies, enforce safety policies, execute actions, and verify authoritative outcomes"
      />

      <div className="p-8 space-y-6 max-w-7xl mx-auto">
        {/* Controls Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-slate-900/90 p-4 rounded-xl border border-slate-800 shadow-lg">
          {/* Search Box */}
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search Case ID, Transaction ID, Segment..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-4 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500 transition-colors font-mono"
            />
          </div>

          {/* Status Filter Dropdown & Action */}
          <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-slate-500" />
              <select
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value)}
                className="bg-slate-950 border border-slate-800 text-slate-300 text-xs rounded-lg px-3 py-2 font-mono focus:outline-none focus:border-emerald-500 cursor-pointer"
              >
                <option value="">ALL STATUSES</option>
                <option value="ELIGIBLE">ELIGIBLE</option>
                <option value="POLICY_APPROVED">POLICY APPROVED</option>
                <option value="AWAITING_VERIFICATION">AWAITING VERIFICATION</option>
                <option value="RECOVERED">RECOVERED</option>
                <option value="POLICY_BLOCKED">POLICY BLOCKED</option>
                <option value="ESCALATED">ESCALATED</option>
                <option value="UNRECOVERED">UNRECOVERED</option>
              </select>
            </div>

            <button
              onClick={handleRunBatch}
              disabled={batchRunning}
              className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold shadow-md transition-all cursor-pointer disabled:bg-slate-800"
            >
              <Play className={`w-3.5 h-3.5 ${batchRunning ? 'animate-spin' : ''}`} />
              <span>{batchRunning ? 'PROCESSING BATCH...' : 'RUN BATCH RECOVERY'}</span>
            </button>
          </div>
        </div>

        {error && <ErrorState message={error} onRetry={loadCases} />}

        {loading ? (
          <LoadingState message="Loading recovery operations queue..." />
        ) : (
          <CaseTable cases={filteredCases} onSelectCase={(id) => setSelectedCaseId(id)} />
        )}

        {/* Case Detail Modal / Deep Link */}
        {selectedCaseId && (
          <CaseDetailModal
            caseId={selectedCaseId}
            onClose={() => setSelectedCaseId(null)}
            onRefreshList={loadCases}
          />
        )}
      </div>
    </div>
  );
};
