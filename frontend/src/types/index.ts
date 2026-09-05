// System & Health Types
export interface HealthCheckResponse {
  status: string;
  service: string;
  version: string;
  components: {
    database: string;
    razorpay: string;
    llm_providers: {
      openai: string;
      gemini: string;
      fallback: string;
    };
  };
  evidence_categories: string[];
}

// Dashboard & Portfolio Metrics Types
export interface DashboardSummary {
  metric_scope: string;
  evidence_category: string;
  total_transactions: number;
  revenue_at_risk_paise: number;
  revenue_at_risk_rupees: number;
  total_cases: number;
  eligible_cases: number;
  ineligible_cases: number;
  total_actions_attempted: number;
  real_test_mode_actions: number;
  simulated_actions: number;
  verified_recovered_cases: number;
  unrecovered_cases: number;
  awaiting_verification_cases: number;
  total_verified_recovered_paise: number;
  total_verified_recovered_rupees: number;
  case_recovery_rate: number;
  revenue_recovery_rate: number;
  action_success_rate: number;
  computed_at: string;
}

export interface FailureBreakdownItem {
  category: string;
  count: number;
  amount_paise: number;
  amount_rupees: number;
  percentage: number;
}

export interface FailureBreakdownResponse {
  total_unrecovered_cases: number;
  total_unrecovered_paise: number;
  total_unrecovered_rupees: number;
  categories: FailureBreakdownItem[];
  policy_block_reasons: Record<string, number>;
}

// Recovery Case & Action Types
export interface RecoveryCaseItem {
  id: string;
  transaction_id: string;
  customer_id: string;
  segment_id: string | null;
  segment_name: string | null;
  status: string;
  attempt_count: number;
  is_terminal: boolean;
  detected_at: string | null;
}

export interface RecoveryCaseListResponse {
  total_count: number;
  offset: number;
  limit: number;
  cases: RecoveryCaseItem[];
}

export interface CaseContextResponse {
  case_id: string;
  case_status: string;
  attempt_count: number;
  detected_at: string;
  transaction: {
    id: string;
    razorpay_payment_id: string;
    razorpay_order_id: string | null;
    amount_paise: number;
    amount_rupees: number;
    currency: string;
    status: string;
    failure_code: string | null;
    failure_reason: string | null;
    failure_category: string;
    payment_method: string;
    created_at: string;
  };
  customer: {
    id: string;
    name: string;
    email: string;
    customer_type: string;
    total_transactions: number;
    successful_transactions: number;
    failed_transactions: number;
    contacts_count_24h: number;
  };
  segment: {
    id: string;
    name: string;
    failure_category: string;
    payment_method: string;
    amount_range: string;
    customer_type: string;
    description: string;
  } | null;
  historical_outcomes_summary: Record<string, any>;
  prior_actions: any[];
}

export interface DecisionResponse {
  id: string;
  case_id: string;
  case_status: string;
  selected_strategy: string;
  ai_recommended_strategy: string;
  ai_confidence: number;
  ai_diagnosis: string;
  reasoning_summary: string;
  strategy_evidence: Record<string, any> | null;
  competing_strategies: any[] | null;
  llm_provider: string;
  created_at: string | null;
}

export interface ExecutionResponse {
  case_id: string;
  case_status: string;
  action_id: string;
  action_type: string;
  execution_mode: string;
  status: string;
  razorpay_payment_link_id: string | null;
  payment_link_url: string | null;
  payload: Record<string, any> | null;
  executed_at: string | null;
}

export interface VerificationResponse {
  case_id: string;
  case_status: string;
  outcome: string;
  amount_recovered_paise: number;
  amount_recovered_rupees: number;
  attribution_status: string;
  strategy_type: string;
  segment_id: string;
  updated_strategy_recovery_rate: number;
}

// 4D Segment Types
export interface SegmentItem {
  id: string;
  name: string;
  failure_category: string;
  payment_method: string;
  amount_range: string;
  customer_type: string;
  description: string;
  strategy_count: number;
  total_attempts: number;
  total_recoveries: number;
  created_at: string | null;
}

export interface SegmentListResponse {
  total_count: number;
  offset: number;
  limit: number;
  segments: SegmentItem[];
}

export interface SegmentStrategyDetail {
  id: string;
  strategy_type: string;
  attempt_count: number;
  success_count: number;
  total_recovered_paise: number;
  recovery_rate: number;
  wilson_lower_bound: number;
  sample_size_sufficient: boolean;
  confidence_level: string;
  data_source: string;
}

export interface SegmentDetailResponse {
  id: string;
  name: string;
  failure_category: string;
  payment_method: string;
  amount_range: string;
  customer_type: string;
  description: string;
  created_at: string | null;
  strategies: SegmentStrategyDetail[];
}

// Strategy Performance Types
export interface StrategySummaryItem {
  strategy_type: string;
  attempt_count: number;
  success_count: number;
  total_recovered_paise: number;
  total_recovered_rupees: number;
  weighted_recovery_rate: number;
  wilson_lower_bound: number;
  economic_strategy_value: number;
  confidence_level: string;
  sample_size_tier: string;
  evidence_category: string;
}

export interface StrategyPerformanceSummaryResponse {
  metric_scope: string;
  evidence_category: string;
  total_attempts: number;
  total_successes: number;
  total_recovered_paise: number;
  total_recovered_rupees: number;
  strategies: StrategySummaryItem[];
}

// Policy Simulator Types
export interface PolicySimulationResultItem {
  id: string;
  batch_run_id: string | null;
  policy_name: string;
  total_transactions: number;
  revenue_at_risk_paise: number;
  revenue_at_risk_rupees: number;
  eligible_count: number;
  eligible_revenue_paise: number;
  projected_recovered_paise: number;
  projected_recovered_rupees: number;
  projected_recovery_rate: number;
  actions_projected: number;
  policy_blocks_projected: number;
  escalations_projected: number;
  contacts_projected: number;
  simulation_mode: string;
  created_at: string | null;
}

export interface SimulatorCompareResponse {
  simulation_mode: string;
  evidence_category: string;
  total_transactions_evaluated: number;
  baseline_policy: {
    name: string;
    recovery_rate: number;
    projected_recovered_paise: number;
    projected_recovered_rupees: number;
    actions_taken: number;
  };
  nivaran_optimized_policy: {
    name: string;
    recovery_rate: number;
    projected_recovered_paise: number;
    projected_recovered_rupees: number;
    actions_taken: number;
  };
  projected_uplift: {
    incremental_recovery_rate: number;
    incremental_recovered_paise: number;
    incremental_recovered_rupees: number;
    percentage_improvement: number;
  };
}

// Audit & Timeline Types
export interface AuditEventItem {
  id: string;
  recovery_case_id: string | null;
  event_type: string;
  event_id: string | null;
  actor: string;
  description: string;
  details: Record<string, any> | null;
  created_at: string | null;
}

export interface AuditQueryResponse {
  count: number;
  offset: number;
  limit: number;
  events: AuditEventItem[];
}
