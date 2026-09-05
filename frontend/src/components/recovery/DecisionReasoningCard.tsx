import React from 'react';
import type { DecisionResponse } from '../../types';
import { Brain, HelpCircle } from 'lucide-react';

interface DecisionReasoningCardProps {
  decision: DecisionResponse | null;
}

export const DecisionReasoningCard: React.FC<DecisionReasoningCardProps> = ({ decision }) => {
  if (!decision) {
    return (
      <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 text-slate-400 text-xs font-mono">
        <HelpCircle className="w-5 h-5 text-slate-500 mb-2" />
        Strategy Engine has not yet evaluated this case. Click "Evaluate Strategy" to synthesize AI & empirical evidence.
      </div>
    );
  }

  const confidencePct = Math.round((decision.ai_confidence || 0) * 100);

  return (
    <div className="p-6 rounded-xl bg-slate-900/90 border border-slate-800 shadow-xl space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <Brain className="w-5 h-5 text-emerald-400" />
          <h4 className="text-sm font-semibold text-slate-100">WHY THIS STRATEGY? (DECISION EXPLANATION)</h4>
        </div>
        <span className="text-xs font-mono px-2.5 py-1 rounded bg-indigo-950/80 border border-indigo-500/30 text-indigo-300">
          PROVIDER: {decision.llm_provider.toUpperCase()}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Recommended & Selected Strategy */}
        <div className="p-4 rounded-lg bg-slate-950 border border-emerald-500/30">
          <span className="text-[10px] font-mono text-emerald-400 uppercase tracking-wider block mb-1">
            SELECTED STRATEGY
          </span>
          <div className="text-lg font-bold text-slate-100 font-mono">
            {decision.selected_strategy}
          </div>
          <p className="text-xs text-slate-400 mt-1">
            AI Recommendation: <strong className="text-slate-200">{decision.ai_recommended_strategy}</strong> ({confidencePct}% AI Confidence)
          </p>
        </div>

        {/* Diagnosis Summary */}
        <div className="p-4 rounded-lg bg-slate-950 border border-slate-800">
          <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block mb-1">
            ROOT CAUSE DIAGNOSIS
          </span>
          <p className="text-xs text-slate-200 leading-relaxed font-sans">
            {decision.ai_diagnosis}
          </p>
        </div>
      </div>

      {/* Reasoning Chain */}
      <div className="p-4 rounded-lg bg-slate-950/80 border border-slate-800/80">
        <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block mb-1">
          EVIDENCE SYNTHESIS & REASONING SUMMARY
        </span>
        <p className="text-xs text-slate-300 leading-relaxed font-sans">
          {decision.reasoning_summary}
        </p>
      </div>

      {/* Competing Strategies Considered */}
      {decision.competing_strategies && decision.competing_strategies.length > 0 && (
        <div>
          <span className="text-xs font-mono text-slate-400 block mb-2">
            COMPETING STRATEGIES EVALUATED:
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs font-mono">
            {decision.competing_strategies.map((cs: any, idx: number) => (
              <div key={idx} className="p-2.5 rounded bg-slate-950 border border-slate-800 flex justify-between items-center">
                <span className="text-slate-300">{cs.strategy_type || cs.name}</span>
                <span className="text-emerald-400 text-[11px]">
                  {cs.score ? `${Math.round(cs.score * 100)}%` : cs.recovery_rate ? `${Math.round(cs.recovery_rate * 100)}%` : 'Evaluated'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
