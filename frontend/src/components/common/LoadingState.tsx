import React from 'react';

interface LoadingStateProps {
  message?: string;
}

export const LoadingState: React.FC<LoadingStateProps> = ({ message = 'Loading pipeline context...' }) => {
  return (
    <div className="flex flex-col items-center justify-center p-12 space-y-4 rounded-xl bg-slate-900/50 border border-slate-800/80 my-4">
      <div className="relative w-12 h-12">
        <div className="absolute inset-0 rounded-full border-2 border-emerald-500/20 animate-ping"></div>
        <div className="absolute inset-0 rounded-full border-2 border-t-emerald-500 border-r-teal-500 border-b-transparent border-l-transparent animate-spin"></div>
      </div>
      <p className="text-sm font-mono text-slate-400 tracking-wide">{message}</p>
    </div>
  );
};
