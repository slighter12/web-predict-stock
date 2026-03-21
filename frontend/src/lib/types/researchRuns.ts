import type {
  BaselineName,
  DefaultBundleVersion,
  FeatureName,
  MarketCode,
  PriceSource,
  ReturnTarget,
  ResearchMonitorProfileId,
  RunStatus,
  RuntimeMode,
  ValidationMethod,
} from "./common";
import type {
  ConfigSources,
  EffectiveStrategy,
  FallbackAudit,
  P3Summary,
  VersionPack,
} from "./runtime";

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

export interface ResearchRunCreateRequest {
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
  portfolio_aum?: number;
  monitor_profile_id?: ResearchMonitorProfileId | null;
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

export interface ResearchRunResponse extends VersionPack, P3Summary {
  run_id: string;
  metrics: Metrics;
  equity_curve: EquityPoint[];
  signals: SignalPoint[];
  validation: ValidationSummary | null;
  baselines: Record<string, Record<string, number>>;
  warnings: string[];
  runtime_mode: RuntimeMode;
  default_bundle_version: DefaultBundleVersion | null;
  effective_strategy: EffectiveStrategy;
  config_sources: ConfigSources;
  fallback_audit: FallbackAudit;
}

export interface ResearchRunRecord extends VersionPack, P3Summary {
  run_id: string;
  request_id: string | null;
  status: RunStatus;
  market: string | null;
  symbols: string[];
  strategy_type: string | null;
  runtime_mode: string | null;
  default_bundle_version: string | null;
  effective_strategy: EffectiveStrategy | null;
  allow_proactive_sells: boolean | null;
  config_sources: ConfigSources | null;
  fallback_audit: FallbackAudit | null;
  validation_outcome: Record<string, unknown> | null;
  rejection_reason: string | null;
  request_payload: Record<string, unknown> | null;
  metrics: Metrics | null;
  warnings: string[];
  created_at: string;
}
