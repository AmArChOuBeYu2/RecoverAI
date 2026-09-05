import React, { useState } from 'react';
import { Sidebar } from './Sidebar';
import { GuidedDemoModal } from '../common/GuidedDemoModal';

interface AppShellProps {
  currentPath: string;
  onNavigate: (path: string) => void;
  children: React.ReactNode;
  onRefreshData?: () => void;
}

export const AppShell: React.FC<AppShellProps> = ({ currentPath, onNavigate, children, onRefreshData }) => {
  const [isDemoOpen, setIsDemoOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-[#080C14] text-slate-100 antialiased selection:bg-emerald-500/30 selection:text-emerald-200">
      <Sidebar currentPath={currentPath} onNavigate={onNavigate} />
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto relative">
        {/* Floating Start Guided Demo Button */}
        <div className="fixed bottom-6 right-6 z-40">
          <button
            onClick={() => setIsDemoOpen(true)}
            className="px-4 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs font-mono transition-all shadow-xl shadow-emerald-500/25 flex items-center gap-2 border border-emerald-400/50"
          >
            <span className="w-2 h-2 rounded-full bg-slate-950 animate-ping" />
            <span>START GUIDED DEMO</span>
          </button>
        </div>

        {children}

        <GuidedDemoModal
          isOpen={isDemoOpen}
          onClose={() => setIsDemoOpen(false)}
          onComplete={() => {
            setIsDemoOpen(false);
            if (onRefreshData) onRefreshData();
          }}
        />
      </main>
    </div>
  );
};
