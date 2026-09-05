import type {
  HealthCheckResponse,
  DashboardSummary,
  FailureBreakdownResponse,
  RecoveryCaseListResponse,
  CaseContextResponse,
  DecisionResponse,
  ExecutionResponse,
  VerificationResponse,
  SegmentListResponse,
  SegmentDetailResponse,
  StrategyPerformanceSummaryResponse,
  SimulatorCompareResponse,
  AuditQueryResponse,
} from '../types';

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

async function apiFetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  try {
    const res = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });

    if (!res.ok) {
      let errDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errJson = await res.json();
        if (errJson.detail) {
          errDetail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
        }
      } catch {
        // use default HTTP error
      }
      throw new Error(errDetail);
    }

    return (await res.json()) as T;
  } catch (err: any) {
    console.error(`[NIVARAN API Error] ${endpoint}:`, err);
    throw err;
  }
}

export const api = {
  // System Health
  getHealth: () => apiFetch<HealthCheckResponse>('/api/health'),

  // Dashboard & Metrics
  getDashboardSummary: () => apiFetch<DashboardSummary>('/api/dashboard/summary'),
  getFailureBreakdown: () => apiFetch<FailureBreakdownResponse>('/api/dashboard/failure-breakdown'),

  // Recovery Pipeline Operations
  seedDataset: (count = 500) => apiFetch<{ status: string; transactions_created: number; message: string }>(`/api/recovery/seed?count=${count}`, { method: 'POST' }),
  runBatchRecovery: (limit = 500) => apiFetch<any>(`/api/recovery/run?limit=${limit}`, { method: 'POST' }),
  runDetection: (limit = 500) => apiFetch<{ detected_count: number; cases: any[] }>(`/api/recovery/detect?limit=${limit}`, { method: 'POST' }),
  listCases: (params?: { status?: string; segment_id?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params?.status) q.append('status', params.status);
    if (params?.segment_id) q.append('segment_id', params.segment_id);
    if (params?.limit) q.append('limit', String(params.limit));
    if (params?.offset) q.append('offset', String(params.offset));
    return apiFetch<RecoveryCaseListResponse>(`/api/recovery/cases?${q.toString()}`);
  },
  getCaseDetail: (caseId: string) => apiFetch<CaseContextResponse>(`/api/recovery/cases/${caseId}`),
  getCaseContext: (caseId: string) => apiFetch<CaseContextResponse>(`/api/recovery/context/${caseId}`),
  evaluateCaseStrategy: (caseId: string, force = false) => apiFetch<DecisionResponse>(`/api/recovery/evaluate/${caseId}?force_reevaluate=${force}`, { method: 'POST' }),
  getCaseDecision: (caseId: string) => apiFetch<DecisionResponse>(`/api/recovery/decisions/${caseId}`),
  executeCaseAction: (caseId: string) => apiFetch<ExecutionResponse>(`/api/recovery/${caseId}/execute`, { method: 'POST' }),
  verifyCaseOutcome: (caseId: string) => apiFetch<VerificationResponse>(`/api/recovery/${caseId}/verify`, { method: 'POST' }),

  // 4D Canonical Segments
  listSegments: (params?: { failure_category?: string; payment_method?: string; amount_range?: string; customer_type?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params?.failure_category) q.append('failure_category', params.failure_category);
    if (params?.payment_method) q.append('payment_method', params.payment_method);
    if (params?.amount_range) q.append('amount_range', params.amount_range);
    if (params?.customer_type) q.append('customer_type', params.customer_type);
    if (params?.limit) q.append('limit', String(params.limit));
    if (params?.offset) q.append('offset', String(params.offset));
    return apiFetch<SegmentListResponse>(`/api/segments?${q.toString()}`);
  },
  getSegmentDetail: (segmentId: string) => apiFetch<SegmentDetailResponse>(`/api/segments/${segmentId}`),

  // Strategy Intelligence
  getStrategyPerformance: (params?: { failure_category?: string; payment_method?: string }) => {
    const q = new URLSearchParams();
    if (params?.failure_category) q.append('failure_category', params.failure_category);
    if (params?.payment_method) q.append('payment_method', params.payment_method);
    return apiFetch<StrategyPerformanceSummaryResponse>(`/api/strategies?${q.toString()}`);
  },
  compareStrategies: (params: { failure_category: string; payment_method?: string; amount_range?: string; customer_type?: string }) => {
    const q = new URLSearchParams({ failure_category: params.failure_category });
    if (params.payment_method) q.append('payment_method', params.payment_method);
    if (params.amount_range) q.append('amount_range', params.amount_range);
    if (params.customer_type) q.append('customer_type', params.customer_type);
    return apiFetch<any>(`/api/strategies/compare?${q.toString()}`);
  },

  // Policy Simulator
  runSimulation: (limit = 500) => apiFetch<any>(`/api/simulator/run?limit=${limit}`, { method: 'POST' }),
  getSimulatorCompare: (limit = 500) => apiFetch<SimulatorCompareResponse>(`/api/simulator/compare?limit=${limit}`),

  // Audit Log & Timeline
  queryAuditEvents: (params?: { recovery_case_id?: string; batch_run_id?: string; event_type?: string; actor?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams();
    if (params?.recovery_case_id) q.append('recovery_case_id', params.recovery_case_id);
    if (params?.batch_run_id) q.append('batch_run_id', params.batch_run_id);
    if (params?.event_type) q.append('event_type', params.event_type);
    if (params?.actor) q.append('actor', params.actor);
    if (params?.limit) q.append('limit', String(params.limit));
    if (params?.offset) q.append('offset', String(params.offset));
    return apiFetch<AuditQueryResponse>(`/api/audit/events?${q.toString()}`);
  },
  getCaseTimeline: (caseId: string) => apiFetch<any>(`/api/audit/timeline/${caseId}`),
};
