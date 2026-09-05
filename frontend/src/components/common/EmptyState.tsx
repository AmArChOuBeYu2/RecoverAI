import React from 'react';
import { Database } from 'lucide-react';

interface EmptyStateProps {
  title?: string;
  message?: string;
  actionLabel?: string;
  onAction?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = 'No Records Found',
  message = 'No data matching the requested filter parameters could be located.',
  actionLabel,
  onAction,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-12 rounded-xl bg-slate-900/40 border border-slate-800 text-center my-4">
      <Database className="w-10 h-10 text-slate-600 mb-3" />
      <h4 className="text-base font-medium text-slate-300">{title}</h4>
      <p className="text-xs text-slate-400 mt-1 max-w-sm font-sans">{message}</p>
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="mt-4 px-4 py-2 text-xs font-medium bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors cursor-pointer"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
};
