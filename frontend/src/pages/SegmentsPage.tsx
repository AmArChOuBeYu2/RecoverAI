import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { SegmentItem } from '../types';
import { Header } from '../components/layout/Header';
import { SegmentMatrix } from '../components/segments/SegmentMatrix';
import { SegmentDetailDrawer } from '../components/segments/SegmentDetailDrawer';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import { Filter } from 'lucide-react';

export const SegmentsPage: React.FC = () => {
  const [segments, setSegments] = useState<SegmentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [failureCat, setFailureCat] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('');
  const [amountRange, setAmountRange] = useState('');
  const [selectedSegmentId, setSelectedSegmentId] = useState<string | null>(null);

  const loadSegments = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listSegments({
        failure_category: failureCat || undefined,
        payment_method: paymentMethod || undefined,
        amount_range: amountRange || undefined,
        limit: 100,
      });
      setSegments(res.segments || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load canonical 4D segments');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSegments();
  }, [failureCat, paymentMethod, amountRange]);

  return (
    <div>
      <Header
        pageTitle="4D Canonical Segment Intelligence"
        pageSubtitle="Explore failure taxonomy across Failure Category × Payment Method × Amount Range × Customer Type"
      />

      <div className="p-8 space-y-6 max-w-7xl mx-auto">
        {/* Filters Bar */}
        <div className="flex flex-wrap items-center gap-4 bg-slate-900/90 p-4 rounded-xl border border-slate-800 shadow-lg">
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
            <Filter className="w-4 h-4 text-emerald-400" />
            <span>DIMENSIONAL FILTERS:</span>
          </div>

          <select
            value={failureCat}
            onChange={(e) => setFailureCat(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-slate-300 text-xs rounded-lg px-3 py-2 font-mono focus:outline-none focus:border-emerald-500 cursor-pointer"
          >
            <option value="">ALL FAILURE CATEGORIES</option>
            <option value="AUTHENTICATION_FAILURE">AUTHENTICATION FAILURE</option>
            <option value="BANK_TIMEOUT">BANK TIMEOUT</option>
            <option value="INSUFFICIENT_FUNDS">INSUFFICIENT FUNDS</option>
            <option value="CHECKOUT_ABANDONMENT">CHECKOUT ABANDONMENT</option>
          </select>

          <select
            value={paymentMethod}
            onChange={(e) => setPaymentMethod(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-slate-300 text-xs rounded-lg px-3 py-2 font-mono focus:outline-none focus:border-emerald-500 cursor-pointer"
          >
            <option value="">ALL PAYMENT METHODS</option>
            <option value="card">CARD</option>
            <option value="upi">UPI</option>
            <option value="netbanking">NETBANKING</option>
            <option value="wallet">WALLET</option>
          </select>

          <select
            value={amountRange}
            onChange={(e) => setAmountRange(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-slate-300 text-xs rounded-lg px-3 py-2 font-mono focus:outline-none focus:border-emerald-500 cursor-pointer"
          >
            <option value="">ALL AMOUNT RANGES</option>
            <option value="LOW">LOW (&lt;₹500)</option>
            <option value="MID">MID (₹500-₹5,000)</option>
            <option value="HIGH">HIGH (₹5,000-₹50,000)</option>
            <option value="PREMIUM">PREMIUM (&gt;₹50,000)</option>
          </select>
        </div>

        {error && <ErrorState message={error} onRetry={loadSegments} />}

        {loading ? (
          <LoadingState message="Loading canonical 4D segment matrix..." />
        ) : (
          <SegmentMatrix
            segments={segments}
            onSelectSegment={(id) => setSelectedSegmentId(id)}
          />
        )}

        {/* Segment Detail Drawer */}
        {selectedSegmentId && (
          <SegmentDetailDrawer
            segmentId={selectedSegmentId}
            onClose={() => setSelectedSegmentId(null)}
          />
        )}
      </div>
    </div>
  );
};
