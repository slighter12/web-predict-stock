import type {
  AdaptiveMode,
  BaselineName,
  DefaultBundleVersion,
  ExecutionRoute,
  FeatureName,
  MarketCode,
  ModelType,
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
  FoundationMetadata,
  GovernanceMetadata,
  P3Summary,
  VersionPack,
} from "./runtime";

export interface FeatureSpec {
  name: FeatureName;
  window: number;
  source: PriceSource;
  shift: number;
}

export interface ResearchFeatureDefinition {
  name: string;
  label: string;
  description: string;
  default_window: number;
  allowed_sources: PriceSource[];
}

export interface ResearchFeatureRegistryResponse {
  version: string;
  features: ResearchFeatureDefinition[];
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
    type: ModelType;
    params: Record<string, unknown>;
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
  factor_catalog_version?: string;
  scoring_factor_ids?: string[];
  external_signal_policy_version?: string;
  cluster_snapshot_version?: string;
  peer_policy_version?: string;
  execution_route?: ExecutionRoute;
  simulation_profile_id?: string;
  live_control_profile_id?: string;
  manual_confirmed?: boolean;
  adaptive_mode?: AdaptiveMode;
  adaptive_profile_id?: string;
  reward_definition_version?: string;
  state_definition_version?: string;
  rollout_control_version?: string;
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

export interface RegressionDiagnosticPoint {
  date: string;
  symbol: string;
  actual: number;
  predicted: number;
  residual: number;
}

export interface FeatureImportancePoint {
  feature: string;
  importance: number;
}

export interface RegressionDiagnostics {
  task: "regression";
  sample_count: number;
  rmse: number | null;
  mae: number | null;
  rank_ic: number | null;
  linear_ic: number | null;
  actual_vs_predicted: RegressionDiagnosticPoint[];
  residuals: RegressionDiagnosticPoint[];
  feature_importance: FeatureImportancePoint[];
}

export interface ResearchRunResponse
  extends VersionPack, P3Summary, GovernanceMetadata, FoundationMetadata {
  run_id: string;
  metrics: Metrics;
  equity_curve: EquityPoint[];
  signals: SignalPoint[];
  validation: ValidationSummary | null;
  model_diagnostics: RegressionDiagnostics | null;
  baselines: Record<string, Record<string, number>>;
  warnings: string[];
  runtime_mode: RuntimeMode;
  default_bundle_version: DefaultBundleVersion | null;
  effective_strategy: EffectiveStrategy;
  config_sources: ConfigSources;
  fallback_audit: FallbackAudit;
}

export interface ResearchRunRecord
  extends VersionPack, P3Summary, GovernanceMetadata, FoundationMetadata {
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
  equity_curve: EquityPoint[];
  signals: SignalPoint[];
  validation: ValidationSummary | null;
  model_diagnostics: RegressionDiagnostics | null;
  baselines: Record<string, Record<string, number>>;
  warnings: string[];
  created_at: string;
}
