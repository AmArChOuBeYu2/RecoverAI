import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { AuditEventItem } from '../types';
import { Header } from '../components/layout/Header';
import { AuditTimeline } from '../components/audit/AuditTimeline';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import { Filter } from 'lucide-react';

export const EvidencePage: React.FC = () => {
  const [events, setEvents] = useState<AuditEventItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedActor, setSelectedActor] = useState('');
  const [selectedEventType, setSelectedEventType] = useState('');

  const loadAuditEvents = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.queryAuditEvents({
        actor: selectedActor || undefined,
        event_type: selectedEventType || undefined,
        limit: 100,
      });
      setEvents(res.events || []);
    } catch (err: any) {
      setError(err.message || 'Failed to query audit trail events');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAuditEvents();
  }, [selectedActor, selectedEventType]);

  return (
    <div>
      <Header
        pageTitle="Audit Trail & Data Provenance"
        pageSubtitle="Chronological timeline of system events, AI diagnoses, policy approvals, bounded action executions, and authoritative verifications"
      />

      <div className="p-8 space-y-6 max-w-7xl mx-auto">
        {/* Filter Controls Bar */}
        <div className="flex flex-wrap items-center gap-4 bg-slate-900/90 p-4 rounded-xl border border-slate-800 shadow-lg">
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
            <Filter className="w-4 h-4 text-emerald-400" />
            <span>AUDIT FILTERS:</span>
          </div>

          <select
            value={selectedActor}
            onChange={(e) => setSelectedActor(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-slate-300 text-xs rounded-lg px-3 py-2 font-mono focus:outline-none focus:border-emerald-500 cursor-pointer"
          >
            <option value="">ALL ACTORS</option>
            <option value="SYSTEM">SYSTEM</option>
            <option value="POLICY_ENGINE">POLICY ENGINE</option>
            <option value="AI_DIAGNOSIS">AI DIAGNOSIS</option>
            <option value="TRUST_GATE">TRUST GATE</option>
            <option value="HUMAN">HUMAN OPERATOR</option>
          </select>

          <select
            value={selectedEventType}
            onChange={(e) => setSelectedEventType(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-slate-300 text-xs rounded-lg px-3 py-2 font-mono focus:outline-none focus:border-emerald-500 cursor-pointer"
          >
            <option value="">ALL EVENT TYPES</option>
            <option value="FAILURE_DETECTED">FAILURE DETECTED</option>
            <option value="AI_DIAGNOSIS_COMPLETED">AI DIAGNOSIS COMPLETED</option>
            <option value="POLICY_EVALUATED">POLICY EVALUATED</option>
            <option value="ACTION_EXECUTED">ACTION EXECUTED</option>
            <option value="OUTCOME_VERIFIED">OUTCOME VERIFIED</option>
            <option value="STRATEGY_ATTRIBUTED">STRATEGY ATTRIBUTED</option>
          </select>
        </div>

        {error && <ErrorState message={error} onRetry={loadAuditEvents} />}

        {loading ? (
          <LoadingState message="Querying audit trail timeline..." />
        ) : (
          <AuditTimeline events={events} />
        )}
      </div>
    </div>
  );
};
