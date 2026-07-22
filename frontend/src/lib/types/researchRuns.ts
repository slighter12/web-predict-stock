import type {
  BaselineName,
  DefaultBundleVersion,
  ArtifactCompleteness,
  FeatureName,
  ModelType,
  PriceSource,
  ReviewArtifactName,
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
  market: "TW";
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
  direction_model?: {
    type: ModelType;
    params: Record<string, unknown>;
    positive_return_threshold: number;
    confirmation_probability_threshold: number;
    calibration_policy_version: "chronological_tail_20pct_min20_class5_v1";
    confirmation_policy_version: "regression_threshold_direction_probability_v1";
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
  score: number | null;
  position: number;
  signal_kind: "holdout_evaluation" | "forward_opinion";
  up_probability: number | null;
  predicted_direction: "up" | "down" | null;
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
  direction_classification: DirectionClassificationDiagnostics | null;
}

export interface DirectionClassificationDiagnostics {
  task: "binary_classification";
  evaluation_status: "evaluated" | "not_evaluated";
  status_reason: string | null;
  sample_count: number;
  positive_return_threshold: number;
  confirmation_probability_threshold: number;
  calibration_method: "sigmoid";
  calibration_sample_count: number;
  positive_prevalence: number | null;
  confusion_matrix: number[][];
  precision: number | null;
  recall: number | null;
  roc_auc: number | null;
  pr_auc: number | null;
  brier: number | null;
}

export interface OpinionRow {
  symbol: string;
  model_score: number;
  position_signal: number;
  signal_date: string;
  up_probability: number;
  confirmation_state: "confirmed" | "conflict";
  evidence_reason: string;
  risk_or_warning: string;
  invalidation_note: string;
}

export interface OpinionArtifact {
  artifact_version: string;
  state: "viable" | "no-opinion" | "do-not-adopt";
  state_reason: string;
  manual_adoption_only: true;
  opinion_as_of: string | null;
  evidence_limitations: string[];
  buy_candidates: OpinionRow[];
  sell_or_avoid: OpinionRow[];
  watch: OpinionRow[];
}

export interface ComparisonCaveat {
  code: string;
  label: string;
  severity: "blocker" | "note";
}

export interface ReviewArtifactSummary {
  artifact_completeness: ArtifactCompleteness;
  present_artifacts: ReviewArtifactName[];
  missing_artifacts: ReviewArtifactName[];
  not_required_artifacts: ReviewArtifactName[];
  comparison_caveats: ComparisonCaveat[];
}

export interface ResearchRunResponse
  extends VersionPack,
    P3Summary,
    GovernanceMetadata,
    FoundationMetadata,
    ReviewArtifactSummary {
  run_id: string;
  metrics: Metrics;
  equity_curve: EquityPoint[];
  signals: SignalPoint[];
  validation: ValidationSummary | null;
  model_diagnostics: RegressionDiagnostics | null;
  baselines: Record<string, Record<string, number>>;
  warnings: string[];
  opinion_artifact: OpinionArtifact;
  runtime_mode: RuntimeMode;
  default_bundle_version: DefaultBundleVersion | null;
  effective_strategy: EffectiveStrategy;
  config_sources: ConfigSources;
  fallback_audit: FallbackAudit;
}

export interface ResearchRunRecord
  extends VersionPack,
    P3Summary,
    GovernanceMetadata,
    FoundationMetadata,
    ReviewArtifactSummary {
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
  opinion_artifact: OpinionArtifact;
  created_at: string;
}
