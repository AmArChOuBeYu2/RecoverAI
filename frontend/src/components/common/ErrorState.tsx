import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'API Communication Failure',
  message,
  onRetry,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-8 rounded-xl bg-rose-950/20 border border-rose-900/40 text-center my-4">
      <AlertCircle className="w-10 h-10 text-rose-400 mb-3" />
      <h4 className="text-base font-semibold text-rose-200">{title}</h4>
      <p className="text-xs text-rose-300/80 mt-1 max-w-md font-mono">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 inline-flex items-center gap-2 px-4 py-2 text-xs font-medium bg-rose-900/40 hover:bg-rose-800/60 border border-rose-700/50 text-rose-200 rounded-lg transition-colors cursor-pointer"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Retry Connection</span>
        </button>
      )}
    </div>
  );
};
