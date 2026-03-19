import type {
  ComparisonEligibility,
  ConfigValueSource,
  FallbackOutcome,
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
