import React from 'react';
import { Sidebar } from './Sidebar';

interface AppShellProps {
  currentPath: string;
  onNavigate: (path: string) => void;
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ currentPath, onNavigate, children }) => {
  return (
    <div className="flex min-h-screen bg-[#080C14] text-slate-100 antialiased selection:bg-emerald-500/30 selection:text-emerald-200">
      <Sidebar currentPath={currentPath} onNavigate={onNavigate} />
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        {children}
      </main>
    </div>
  );
};
