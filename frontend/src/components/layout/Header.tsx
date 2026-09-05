import React from 'react';
import { SystemStatusBadge } from './SystemStatusBadge';
import { Play } from 'lucide-react';

interface HeaderProps {
  pageTitle: string;
  pageSubtitle?: string;
  onStartDemo?: () => void;
  isDemoRunning?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  pageTitle,
  pageSubtitle,
  onStartDemo,
  isDemoRunning = false,
}) => {
  return (
    <header className="h-16 bg-slate-900/60 border-b border-slate-800 px-8 flex items-center justify-between sticky top-0 backdrop-blur-md z-20">
      <div>
        <h2 className="text-lg font-semibold text-slate-100 tracking-tight">{pageTitle}</h2>
        {pageSubtitle && (
          <p className="text-xs text-slate-400">{pageSubtitle}</p>
        )}
      </div>

      <div className="flex items-center gap-4">
        {onStartDemo && (
          <button
            onClick={onStartDemo}
            disabled={isDemoRunning}
            className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-500 text-white shadow-md transition-all cursor-pointer"
          >
            <Play className={`w-3.5 h-3.5 ${isDemoRunning ? 'animate-spin' : ''}`} />
            <span>{isDemoRunning ? 'RUNNING PIPELINE...' : 'START GUIDED DEMO'}</span>
          </button>
        )}

        <SystemStatusBadge />
      </div>
    </header>
  );
};
