import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { SimulatorCompareResponse } from '../types';
import { Header } from '../components/layout/Header';
import { PolicyCompareCard } from '../components/simulator/PolicyCompareCard';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorState } from '../components/common/ErrorState';
import { PlayCircle } from 'lucide-react';

export const SimulatorPage: React.FC = () => {
  const [data, setData] = useState<SimulatorCompareResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [simulating, setSimulating] = useState(false);

  const loadSimulationData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getSimulatorCompare(500);
      setData(res);
    } catch (err: any) {
      setError(err.message || 'Failed to load policy simulation comparison');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSimulationData();
  }, []);

  const handleRunSimulation = async () => {
    setSimulating(true);
    try {
      await api.runSimulation(500);
      await loadSimulationData();
    } catch (err: any) {
      setError(err.message || 'Policy simulation failed');
    } finally {
      setSimulating(false);
    }
  };

  return (
    <div>
      <Header
        pageTitle="Policy Simulator — Baseline vs NIVARAN"
        pageSubtitle="Evaluate read-only policy scenarios to project incremental revenue recovery uplift without modifying live cases"
      />

      <div className="p-8 space-y-6 max-w-7xl mx-auto">
        {/* Simulator Control Header */}
        <div className="p-6 rounded-xl bg-slate-900/90 border border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-xl">
          <div>
            <h3 className="text-sm font-semibold font-mono text-slate-100">READ-ONLY POLICY SCENARIO SIMULATION</h3>
            <p className="text-xs text-slate-400 mt-1">
              Simulates baseline policy (retry once) vs. NIVARAN 4D segment-aware strategy optimization across historical transactions.
            </p>
          </div>

          <button
            onClick={handleRunSimulation}
            disabled={simulating}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs shadow-lg transition-all cursor-pointer disabled:bg-slate-800"
          >
            <PlayCircle className={`w-4 h-4 ${simulating ? 'animate-spin' : ''}`} />
            <span>{simulating ? 'Running Simulation...' : 'RUN POLICY SIMULATION (500 CASES)'}</span>
          </button>
        </div>

        {error && <ErrorState message={error} onRetry={loadSimulationData} />}

        {loading ? (
          <LoadingState message="Executing read-only policy simulation..." />
        ) : (
          <PolicyCompareCard data={data} />
        )}
      </div>
    </div>
  );
};
