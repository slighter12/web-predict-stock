export type MarketCode = "TW" | "US";
export type PriceSource = "open" | "high" | "low" | "close" | "volume";
export type FeatureName = "ma" | "rsi";
export type ReturnTarget = "open_to_open" | "close_to_close" | "open_to_close";
export type ValidationMethod = "holdout" | "walk_forward" | "rolling_window" | "expanding_window";
export type BaselineName = "buy_and_hold" | "naive_momentum" | "ma_crossover";
export type RuntimeMode = "runtime_compatibility_mode" | "vnext_spec_mode";
export type DefaultBundleVersion = "research_spec_v1";
export type ConfigValueSource = "request_override" | "spec_default";
export type FallbackOutcome = "not_needed" | "accepted" | "rejected";
export type ComparisonEligibility =
  | "comparison_metadata_only"
  | "sample_window_pending"
  | "strategy_pair_comparable"
  | "research_only_comparable"
  | "unresolved_event_quarantine";

export interface FeatureSpec {
  name: FeatureName;
  window: number;
  source: PriceSource;
  shift: number;
}

export interface ValidationConfig {
  method: ValidationMethod;
  splits: number;
  test_size: number;
}

export interface BacktestRequest {
  runtime_mode: RuntimeMode;
  default_bundle_version?: DefaultBundleVersion;
  market: MarketCode;
  symbols: string[];
  date_range: {
    start: string;
    end: string;
  };
  return_target: ReturnTarget;
  horizon_days: number;
  features: FeatureSpec[];
  model: {
    type: "xgboost";
    params: Record<string, never>;
  };
  strategy: {
    type: "research_v1";
    threshold?: number;
    top_n?: number;
    allow_proactive_sells: boolean;
  };
  execution: {
    slippage: number;
    fees: number;
  };
  validation?: ValidationConfig;
  baselines: BaselineName[];
}

export interface Metrics {
  total_return: number | null;
  sharpe: number | null;
  max_drawdown: number | null;
  turnover: number | null;
}

export interface EquityPoint {
  date: string;
  equity: number;
}

export interface SignalPoint {
  date: string;
  symbol: string;
  score: number;
  position: number;
}

export interface ValidationSummary {
  method: ValidationMethod;
  metrics: Record<string, number>;
}

export interface BacktestResponse {
  run_id: string;
  metrics: Metrics;
  equity_curve: EquityPoint[];
  signals: SignalPoint[];
  validation: ValidationSummary | null;
  baselines: Record<string, Record<string, number>>;
  warnings: string[];
  runtime_mode: RuntimeMode;
  default_bundle_version: DefaultBundleVersion | null;
  effective_strategy: {
    threshold: number;
    top_n: number;
  };
  config_sources: {
    strategy: {
      threshold: ConfigValueSource;
      top_n: ConfigValueSource;
    };
  };
  fallback_audit: {
    strategy: {
      threshold: {
        attempted: boolean;
        outcome: FallbackOutcome;
      };
      top_n: {
        attempted: boolean;
        outcome: FallbackOutcome;
      };
    };
  };
  threshold_policy_version: string | null;
  price_basis_version: string | null;
  benchmark_comparability_gate: boolean;
  comparison_eligibility: ComparisonEligibility;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export interface ApiErrorPayload {
  error: {
    code: string;
    message: string;
    details?: {
      fields?: Array<{
        field: string;
        code: string;
        reason: string;
      }>;
    };
  };
  meta?: {
    request_id?: string;
  };
}

export interface AppError {
  status: number;
  code: string;
  message: string;
  requestId: string | null;
  details?: ApiErrorPayload["error"]["details"];
}

export interface FormFeatureRow {
  id: string;
  name: FeatureName;
  window: number;
  source: PriceSource;
  shift: number;
}

export interface DashboardFormState {
  runtimeMode: RuntimeMode;
  defaultBundleVersion: DefaultBundleVersion | null;
  market: MarketCode;
  symbolsInput: string;
  startDate: string;
  endDate: string;
  returnTarget: ReturnTarget;
  horizonDays: number;
  features: FormFeatureRow[];
  threshold: number | null;
  topN: number | null;
  allowProactiveSells: boolean;
  slippage: number;
  fees: number;
  enableValidation: boolean;
  validationMethod: ValidationMethod;
  validationSplits: number;
  validationTestSize: number;
  baselines: BaselineName[];
}
