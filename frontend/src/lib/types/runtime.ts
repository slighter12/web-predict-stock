import type {
  ComparisonEligibility,
  ConfigValueSource,
  CorporateEventState,
  FallbackOutcome,
  MissingFeaturePolicyState,
  MonitorObservationStatus,
  TradabilityState,
  VersionFieldStatus,
} from "./common";

export interface EffectiveStrategy {
  threshold: number;
  top_n: number;
}

export interface ConfigSources {
  strategy: {
    threshold: ConfigValueSource;
    top_n: ConfigValueSource;
  };
}

export interface FallbackAudit {
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
}

export interface VersionPack {
  threshold_policy_version: string | null;
  price_basis_version: string | null;
  benchmark_comparability_gate: boolean | null;
  comparison_eligibility: ComparisonEligibility | null;
  investability_screening_active: boolean | null;
  capacity_screening_version: string | null;
  adv_basis_version: string | null;
  missing_feature_policy_version: string | null;
  execution_cost_model_version: string | null;
  split_policy_version: string | null;
  bootstrap_policy_version: string | null;
  ic_overlap_policy_version: string | null;
  version_pack_status: Record<string, VersionFieldStatus>;
}

export interface GovernanceMetadata {
  comparison_review_matrix_version: string | null;
  scheduled_review_cadence: string | null;
  model_family: string | null;
  training_output_contract_version: string | null;
  adoption_comparison_policy_version: string | null;
}

export interface LiquidityBucketCoverage {
  bucket_key: string;
  bucket_label: string;
  full_universe_count: number;
  execution_universe_count: number;
  full_universe_ratio: number;
  execution_coverage_ratio: number;
}

export interface P3Summary {
  tradability_state: TradabilityState | null;
  capacity_screening_active: boolean | null;
  missing_feature_policy_state: MissingFeaturePolicyState | null;
  corporate_event_state: CorporateEventState | null;
  full_universe_count: number | null;
  execution_universe_count: number | null;
  execution_universe_ratio: number | null;
  liquidity_bucket_schema_version: string | null;
  liquidity_bucket_coverages: LiquidityBucketCoverage[];
  stale_mark_days_with_open_positions: number | null;
  stale_risk_share: number | null;
  monitor_observation_status: MonitorObservationStatus | null;
}
