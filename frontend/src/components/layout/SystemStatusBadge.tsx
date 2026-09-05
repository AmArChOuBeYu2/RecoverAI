import React, { useEffect, useState } from 'react';
import { api } from '../../api/client';
import type { HealthCheckResponse } from '../../types';

export const SystemStatusBadge: React.FC = () => {
  const [health, setHealth] = useState<HealthCheckResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    api.getHealth()
      .then(res => {
        if (isMounted) {
          setHealth(res);
          setLoading(false);
        }
      })
      .catch(() => {
        if (isMounted) setLoading(false);
      });
    return () => { isMounted = false; };
  }, []);

  if (loading) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono bg-slate-800 text-slate-400 border border-slate-700">
        <span className="w-2 h-2 rounded-full bg-slate-400 animate-ping"></span>
        Connecting...
      </span>
    );
  }

  const isHealthy = health?.status === 'healthy';
  const isRzpConfigured = health?.components?.razorpay === 'configured';

  return (
    <div className="flex items-center gap-2">
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono border ${
        isHealthy 
          ? 'bg-emerald-950/60 border-emerald-500/30 text-emerald-300' 
          : 'bg-rose-950/60 border-rose-500/30 text-rose-300'
      }`}>
        <span className={`w-2 h-2 rounded-full ${isHealthy ? 'bg-emerald-400' : 'bg-rose-400'}`}></span>
        {isHealthy ? 'SYSTEM HEALTHY' : 'DEGRADED'}
      </span>

      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono bg-amber-950/60 border border-amber-500/30 text-amber-300">
        <span className="w-2 h-2 rounded-full bg-amber-400"></span>
        {isRzpConfigured ? 'RAZORPAY TEST MODE' : 'DEMO MODE'}
      </span>
    </div>
  );
};
