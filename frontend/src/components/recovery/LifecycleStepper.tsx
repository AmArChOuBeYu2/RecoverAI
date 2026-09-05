import React from 'react';
import { CheckCircle2, AlertCircle, Clock } from 'lucide-react';

interface LifecycleStepperProps {
  currentStatus: string;
}

export const LifecycleStepper: React.FC<LifecycleStepperProps> = ({ currentStatus }) => {
  const status = (currentStatus || '').toUpperCase();

  const stages = [
    { key: 'DETECTED', label: '1. Detected' },
    { key: 'ANALYZED', label: '2. Context Assembled' },
    { key: 'SEGMENTED', label: '3. 4D Segmented' },
    { key: 'ELIGIBLE', label: '4. Gated Eligible' },
    { key: 'STRATEGIES_EVALUATED', label: '5. AI & Evidence Strategy' },
    { key: 'POLICY_APPROVED', label: '6. Policy Approved' },
    { key: 'ACTION_ATTEMPTED', label: '7. Bounded Action' },
    { key: 'AWAITING_VERIFICATION', label: '8. Awaiting Verification' },
    { key: 'RECOVERED', label: '9. Authoritative Outcome' },
  ];

  const getStageIndex = (s: string) => {
    switch (s) {
      case 'DETECTED': return 0;
      case 'ANALYZED': return 1;
      case 'SEGMENTED': return 2;
      case 'ELIGIBLE': return 3;
      case 'STRATEGIES_EVALUATED': return 4;
      case 'POLICY_APPROVED': return 5;
      case 'ACTION_ATTEMPTED': return 6;
      case 'AWAITING_VERIFICATION': return 7;
      case 'RECOVERED':
      case 'UNRECOVERED':
      case 'POLICY_BLOCKED':
      case 'ESCALATED':
      case 'INELIGIBLE': return 8;
      default: return 0;
    }
  };

  const currentIndex = getStageIndex(status);

  return (
    <div className="py-4">
      <div className="flex items-center justify-between overflow-x-auto gap-1 pb-2">
        {stages.map((stage, idx) => {
          const isDone = idx < currentIndex;
          const isCurrent = idx === currentIndex;
          const isFailed = (status === 'UNRECOVERED' || status === 'POLICY_BLOCKED' || status === 'INELIGIBLE') && idx === 8;

          return (
            <div key={stage.key} className="flex flex-col items-center text-center min-w-[90px] flex-1">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-mono mb-1 transition-all ${
                  isFailed
                    ? 'bg-rose-900 border border-rose-500 text-rose-300'
                    : isDone
                    ? 'bg-emerald-950 border border-emerald-500 text-emerald-400'
                    : isCurrent
                    ? 'bg-emerald-600 border border-emerald-400 text-white animate-pulse'
                    : 'bg-slate-900 border border-slate-800 text-slate-500'
                }`}
              >
                {isFailed ? (
                  <AlertCircle className="w-3.5 h-3.5" />
                ) : isDone ? (
                  <CheckCircle2 className="w-3.5 h-3.5" />
                ) : isCurrent ? (
                  <Clock className="w-3.5 h-3.5" />
                ) : (
                  idx + 1
                )}
              </div>
              <span
                className={`text-[10px] font-mono leading-tight ${
                  isCurrent ? 'text-emerald-300 font-semibold' : isDone ? 'text-slate-300' : 'text-slate-500'
                }`}
              >
                {stage.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
