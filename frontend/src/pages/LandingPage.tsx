import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { DashboardSummary, RecoveryCaseItem } from '../types';
import { ProvenanceBadge } from '../components/common/ProvenanceBadge';
import {
  ShieldCheck,
  TrendingUp,
  Brain,
  CheckCircle2,
  Layers,
  ArrowRight,
  ExternalLink,
  Zap,
  RotateCcw,
  BarChart3,
  FileCheck2,
  ChevronRight,
} from 'lucide-react';

interface LandingPageProps {
  onNavigate: (path: string) => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onNavigate }) => {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [sampleCase, setSampleCase] = useState<RecoveryCaseItem | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    async function loadData() {
      try {
        const [sumData, caseData] = await Promise.allSettled([
          api.getDashboardSummary(),
          api.listCases({ limit: 1 }),
        ]);

        if (isMounted) {
          if (sumData.status === 'fulfilled') setSummary(sumData.value);
          if (caseData.status === 'fulfilled' && caseData.value.cases.length > 0) {
            setSampleCase(caseData.value.cases[0]);
          }
        }
      } catch (err) {
        console.error('Landing page load error:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadData();
    return () => {
      isMounted = false;
    };
  }, []);

  const totalAtRisk = summary?.revenue_at_risk_rupees ?? 0;
  const verifiedRecovered = summary?.total_verified_recovered_rupees ?? 0;
  const recoveryRatePct = (summary?.revenue_recovery_rate ?? 0) * 100;

  return (
    <div className="min-h-screen bg-[#0B0F17] text-slate-100 font-sans selection:bg-emerald-500/30 selection:text-emerald-200">
      {/* Top Navigation */}
      <header className="sticky top-0 z-50 backdrop-blur-md bg-[#0B0F17]/90 border-b border-slate-800/80">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => onNavigate('/')}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-400 via-teal-500 to-indigo-600 p-[1px] shadow-lg shadow-emerald-500/10">
              <div className="w-full h-full bg-slate-950 rounded-[11px] flex items-center justify-center">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
              </div>
            </div>
            <div>
              <span className="text-xl font-bold tracking-tight text-white font-mono">NIVARAN</span>
              <span className="block text-[10px] text-slate-400 font-mono tracking-wider">REVENUE RECOVERY</span>
            </div>
          </div>

          <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-300">
            <a href="#how-it-works" className="hover:text-emerald-400 transition-colors">How It Works</a>
            <a href="#evidence" className="hover:text-emerald-400 transition-colors">Evidence & Trust</a>
            <a href="#why-nivaran" className="hover:text-emerald-400 transition-colors">Why Nivaran</a>
            <button
              onClick={() => onNavigate('/evidence')}
              className="hover:text-emerald-400 transition-colors text-xs font-mono"
            >
              AUDIT LOGS
            </button>
          </nav>

          <div className="flex items-center gap-4">
            <button
              onClick={() => onNavigate('/home')}
              className="px-5 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-sm transition-all shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/30 flex items-center gap-2"
            >
              <span>OPEN DASHBOARD</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative pt-16 pb-24 border-b border-slate-800/60 overflow-hidden">
        {/* Background glow effects */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[300px] bg-emerald-500/5 blur-[120px] pointer-events-none rounded-full" />
        <div className="absolute top-1/3 right-10 w-[400px] h-[250px] bg-indigo-500/5 blur-[100px] pointer-events-none rounded-full" />

        <div className="max-w-7xl mx-auto px-6 relative z-10">
          <div className="max-w-3xl mx-auto text-center mb-12">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900 border border-slate-800 text-emerald-400 text-xs font-mono mb-6">
              <Zap className="w-3.5 h-3.5" />
              <span>AI REVENUE RECOVERY · BOUNDED EXECUTION</span>
            </div>

            <h1 className="text-4xl md:text-6xl font-normal tracking-tight text-white font-serif leading-[1.1] mb-6">
              Failed payments deserve a <span className="italic text-emerald-400 font-serif">better decision.</span>
            </h1>

            <p className="text-lg text-slate-300 leading-relaxed font-sans font-light mb-8">
              Nivaran diagnoses payment failures, selects optimal recovery strategies using empirical evidence, enforces deterministic safety policy, and verifies authoritative outcomes.
            </p>

            <div className="flex flex-wrap items-center justify-center gap-4">
              <button
                onClick={() => onNavigate('/home')}
                className="px-8 py-3.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-base transition-all shadow-xl shadow-emerald-500/25 flex items-center gap-2"
              >
                <span>OPEN DASHBOARD</span>
                <ArrowRight className="w-5 h-5" />
              </button>
              <a
                href="#how-it-works"
                className="px-6 py-3.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-200 font-medium text-base transition-all flex items-center gap-2"
              >
                <span>SEE HOW IT WORKS</span>
                <ChevronRight className="w-4 h-4 text-slate-400" />
              </a>
            </div>
          </div>

          {/* Interactive Proof Sequence Visual */}
          <div className="mt-12 max-w-5xl mx-auto">
            <div className="p-6 md:p-8 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-2xl backdrop-blur-sm relative">
              <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-6">
                <div className="flex items-center gap-3">
                  <div className="w-3 h-3 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">LIVE DECISION FLOW PROOF</span>
                </div>
                <div className="flex items-center gap-2">
                  <ProvenanceBadge category="VERIFIED" />
                </div>
              </div>

              {/* Step Sequence */}
              <div className="grid grid-cols-1 md:grid-cols-5 gap-4 relative">
                {/* 1. Failed Payment */}
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/80">
                  <span className="text-[10px] font-mono text-slate-500 block mb-1">01. FAILURE</span>
                  <div className="text-sm font-semibold text-slate-200">
                    {sampleCase ? `Case #${sampleCase.id.substring(0, 6)}` : 'Case #A9F102'}
                  </div>
                  <div className="text-[11px] text-red-400 font-mono mt-1">
                    AUTHENTICATION_FAILURE
                  </div>
                </div>

                {/* 2. Context & Segment */}
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/80">
                  <span className="text-[10px] font-mono text-slate-500 block mb-1">02. 4D TAXONOMY</span>
                  <div className="text-xs font-mono text-indigo-300 truncate" title={sampleCase?.segment_name || 'card_mid_returning'}>
                    {sampleCase?.segment_name || 'card_mid_returning'}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1">
                    Recoverability: <span className="text-emerald-400 font-mono">78%</span>
                  </div>
                </div>

                {/* 3. Strategy Selection */}
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/80">
                  <span className="text-[10px] font-mono text-slate-500 block mb-1">03. STRATEGY</span>
                  <div className="text-xs font-semibold text-emerald-400 font-mono">
                    PAYMENT_LINK
                  </div>
                  <div className="text-[10px] text-slate-400 mt-1">Empirical Score: 0.44</div>
                </div>

                {/* 4. Policy Gate */}
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/80">
                  <span className="text-[10px] font-mono text-slate-500 block mb-1">04. TRUST GATE</span>
                  <div className="text-xs font-semibold text-emerald-400 flex items-center gap-1">
                    <ShieldCheck className="w-3.5 h-3.5" />
                    <span>APPROVED</span>
                  </div>
                  <div className="text-[10px] text-slate-400 mt-1">0 Violations</div>
                </div>

                {/* 5. Verification */}
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/80">
                  <span className="text-[10px] font-mono text-slate-500 block mb-1">05. VERIFICATION</span>
                  <div className="text-xs font-semibold text-emerald-400 flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span>VERIFIED</span>
                  </div>
                  <div className="text-[10px] text-slate-500 font-mono mt-1">Razorpay Test API</div>
                </div>
              </div>

              {/* Real Backend KPI Summary Bar */}
              <div className="mt-6 pt-6 border-t border-slate-800 flex flex-wrap items-center justify-between gap-4 text-xs font-mono text-slate-400">
                <div>
                  TOTAL REVENUE AT RISK:{' '}
                  <span className="text-slate-200 font-semibold font-serif text-sm">
                    {loading ? '...' : `₹${totalAtRisk.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`}
                  </span>
                </div>
                <div>
                  VERIFIED RECOVERED:{' '}
                  <span className="text-emerald-400 font-semibold font-serif text-sm">
                    {loading ? '...' : `₹${verifiedRecovered.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`}
                  </span>
                </div>
                <div>
                  RECOVERY RATE:{' '}
                  <span className="text-emerald-400 font-semibold font-serif text-sm">
                    {loading ? '...' : `${recoveryRatePct.toFixed(2)}%`}
                  </span>
                </div>
                <div>
                  DATA PROVENANCE:{' '}
                  <span className="text-slate-300 font-semibold">OBSERVED + VERIFIED</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="py-24 border-b border-slate-800/60 bg-slate-950/40">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <span className="text-xs font-mono text-emerald-400 uppercase tracking-widest block mb-2">END-TO-END PIPELINE</span>
            <h2 className="text-3xl md:text-4xl font-serif text-white mb-4">
              How Nivaran Resolves Revenue
            </h2>
            <p className="text-slate-400 text-sm font-sans font-light">
              Every failed payment passes through an 11-stage decision architecture governed by deterministic safety controls.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
            <div className="p-6 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition-all">
              <div className="text-xs font-mono text-emerald-400 mb-4 font-bold">01 DETECT</div>
              <h3 className="text-base font-semibold text-slate-100 mb-2">Failure Ingestion</h3>
              <p className="text-xs text-slate-400 font-sans leading-relaxed">
                Captures failed payments via Razorpay API & webhooks, assembling rich customer context.
              </p>
            </div>

            <div className="p-6 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition-all">
              <div className="text-xs font-mono text-indigo-400 mb-4 font-bold">02 TRUST GATE</div>
              <h3 className="text-base font-semibold text-slate-100 mb-2">Policy Gate</h3>
              <p className="text-xs text-slate-400 font-sans leading-relaxed">
                Enforces contact limits, cooling periods, and authorization constraints before evaluation.
              </p>
            </div>

            <div className="p-6 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition-all">
              <div className="text-xs font-mono text-purple-400 mb-4 font-bold">03 DIAGNOSE</div>
              <h3 className="text-base font-semibold text-slate-100 mb-2">4D Taxonomy</h3>
              <p className="text-xs text-slate-400 font-sans leading-relaxed">
                Categorizes failure into canonical segment (Failure × Method × Amount × Customer).
              </p>
            </div>

            <div className="p-6 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition-all">
              <div className="text-xs font-mono text-amber-400 mb-4 font-bold">04 DECIDE</div>
              <h3 className="text-base font-semibold text-slate-100 mb-2">Strategy Selection</h3>
              <p className="text-xs text-slate-400 font-sans leading-relaxed">
                Compares candidate strategies using empirical evidence, sample sizes, and economic value.
              </p>
            </div>

            <div className="p-6 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition-all">
              <div className="text-xs font-mono text-emerald-400 mb-4 font-bold">05 VERIFY</div>
              <h3 className="text-base font-semibold text-slate-100 mb-2">Authoritative Proof</h3>
              <p className="text-xs text-slate-400 font-sans leading-relaxed">
                Recovery is counted only upon Razorpay payment link confirmation.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Real Integration Section */}
      <section id="evidence" className="py-24 border-b border-slate-800/60">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900 border border-slate-800 text-cyan-400 text-xs font-mono mb-4">
                <FileCheck2 className="w-3.5 h-3.5" />
                <span>RAZORPAY TEST MODE INTEGRATION</span>
              </div>
              <h2 className="text-3xl md:text-4xl font-serif text-white mb-6">
                Recovery is proven, never assumed.
              </h2>
              <p className="text-slate-300 font-sans leading-relaxed font-light mb-6">
                Nivaran does not pretend creating a payment link equals recovered revenue. Every intervention is tracked to authoritative confirmation on Razorpay Test Mode before outcome attribution.
              </p>

              <div className="space-y-4 font-mono text-xs text-slate-300">
                <div className="flex items-center gap-3 p-3 rounded-lg bg-slate-900/80 border border-slate-800">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  <span>Authoritative Razorpay API state verification</span>
                </div>
                <div className="flex items-center gap-3 p-3 rounded-lg bg-slate-900/80 border border-slate-800">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  <span>HMAC SHA256 Webhook signature validation</span>
                </div>
                <div className="flex items-center gap-3 p-3 rounded-lg bg-slate-900/80 border border-slate-800">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  <span>Sanitized immutable audit trail log</span>
                </div>
              </div>

              <div className="mt-8 flex gap-4">
                <button
                  onClick={() => onNavigate('/evidence')}
                  className="px-6 py-3 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 font-mono text-xs font-semibold transition-all flex items-center gap-2"
                >
                  <span>VIEW AUDIT LOGS</span>
                  <ExternalLink className="w-3.5 h-3.5 text-slate-400" />
                </button>
              </div>
            </div>

            <div className="p-8 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl font-mono text-xs space-y-4">
              <div className="text-slate-400 text-[10px] uppercase border-b border-slate-800 pb-2">
                VERIFICATION PIPELINE AUDIT
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-slate-300">
                  <span>RAZORPAY LINK CREATED:</span>
                  <span className="text-emerald-400">plink_Pz92kX01</span>
                </div>
                <div className="flex justify-between text-slate-300">
                  <span>PAYMENT EVENT:</span>
                  <span className="text-emerald-400">payment_link.paid</span>
                </div>
                <div className="flex justify-between text-slate-300">
                  <span>OUTCOME ATTRIBUTION:</span>
                  <span className="text-emerald-400">VERIFIED_RECOVERED</span>
                </div>
                <div className="flex justify-between text-slate-300">
                  <span>MONETARY PRECISION:</span>
                  <span className="text-slate-200">Integer Paise Correctness</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Portfolio Scale & Bounded Capabilities */}
      <section id="why-nivaran" className="py-24 border-b border-slate-800/60 bg-slate-950/40">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <span className="text-xs font-mono text-indigo-400 uppercase tracking-widest block mb-2">SYSTEM BOUNDARIES</span>
            <h2 className="text-3xl md:text-4xl font-serif text-white mb-4">
              AI Recommends. Code Authorizes.
            </h2>
            <p className="text-slate-400 text-sm font-sans font-light">
              Nivaran separates advisory intelligence from execution authority. No AI model can unilaterally trigger payment interventions.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="p-6 rounded-xl bg-slate-900/60 border border-slate-800">
              <Brain className="w-6 h-6 text-indigo-400 mb-4" />
              <h3 className="text-base font-semibold text-slate-100 mb-2">01 DIAGNOSE</h3>
              <p className="text-xs text-slate-400 font-sans leading-relaxed">
                Read-only LLM context analysis across OpenAI & Gemini with deterministic fallbacks.
              </p>
            </div>

            <div className="p-6 rounded-xl bg-slate-900/60 border border-slate-800">
              <TrendingUp className="w-6 h-6 text-emerald-400 mb-4" />
              <h3 className="text-base font-semibold text-slate-100 mb-2">02 RECOMMEND</h3>
              <p className="text-xs text-slate-400 font-sans leading-relaxed">
                Strategy selection backed by empirical sample sizes and Wilson score lower bounds.
              </p>
            </div>

            <div className="p-6 rounded-xl bg-slate-900/60 border border-slate-800">
              <BarChart3 className="w-6 h-6 text-amber-400 mb-4" />
              <h3 className="text-base font-semibold text-slate-100 mb-2">03 SIMULATE</h3>
              <p className="text-xs text-slate-400 font-sans leading-relaxed">
                Counterfactual policy simulator comparing baseline vs. optimized policy without mutating live state.
              </p>
            </div>

            <div className="p-6 rounded-xl bg-slate-900/60 border border-slate-800">
              <RotateCcw className="w-6 h-6 text-cyan-400 mb-4" />
              <h3 className="text-base font-semibold text-slate-100 mb-2">04 LEARN</h3>
              <p className="text-xs text-slate-400 font-sans leading-relaxed">
                Closed-loop empirical attribution updating strategy performance upon verified payment proof.
              </p>
            </div>
          </div>

          <div className="mt-12 text-center">
            <button
              onClick={() => onNavigate('/segments')}
              className="px-6 py-3 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 font-mono text-xs transition-all inline-flex items-center gap-2"
            >
              <Layers className="w-4 h-4 text-indigo-400" />
              <span>EXPLORE 145 CANONICAL SEGMENTS</span>
            </button>
          </div>
        </div>
      </section>

      {/* Final Landing CTA */}
      <section className="py-24 relative overflow-hidden">
        <div className="max-w-4xl mx-auto text-center px-6">
          <h2 className="text-3xl md:text-5xl font-serif text-white mb-6">
            Find the leak. Decide the response.<br />
            <span className="italic text-emerald-400 font-serif">Prove the recovery.</span>
          </h2>
          <p className="text-slate-400 font-sans font-light text-base mb-8">
            Experience the complete revenue recovery decision system.
          </p>

          <button
            onClick={() => onNavigate('/home')}
            className="px-10 py-4 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-lg transition-all shadow-2xl shadow-emerald-500/30 inline-flex items-center gap-3"
          >
            <span>OPEN DASHBOARD</span>
            <ArrowRight className="w-5 h-5" />
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-950 py-12 text-xs font-mono text-slate-500">
        <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span className="text-slate-200 font-bold">NIVARAN</span>
            </div>
            <p className="text-slate-500 text-[11px] font-sans">Revenue recovery, resolved intelligently.</p>
          </div>

          <div className="text-center md:text-right space-y-1">
            <div>Razorpay Test Mode Configured · Synthetic Demo Dataset</div>
            <div className="flex items-center justify-center md:justify-end gap-4 mt-2">
              <a
                href="https://github.com/AmArChOuBeYu2/RecoverAI"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-slate-300 transition-colors inline-flex items-center gap-1"
              >
                <span>GitHub Repository</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};
