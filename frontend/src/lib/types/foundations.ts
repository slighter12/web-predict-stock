import type {
  AdaptiveMode,
  ExecutionOrderSide,
  ExecutionRoute,
  MarketCode,
} from "./common";

export interface ExternalRawArchiveRecord {
  id: number;
  source_family: string;
  market: MarketCode;
  coverage_start: string;
  coverage_end: string;
  record_count: number;
  payload_body: string | null;
  notes: string | null;
  created_at: string;
}

export interface ExternalSignalRecord {
  id: number;
  archive_id: number | null;
  source_family: string;
  source_record_type: string;
  symbol: string;
  market: MarketCode;
  effective_date: string;
  available_at: string | null;
  availability_mode: string;
  lineage_version: string;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface ExternalSignalAuditRecord {
  id: number;
  source_family: string;
  market: MarketCode;
  audit_window_start: string;
  audit_window_end: string;
  sample_size: number;
  fallback_sample_size: number;
  undocumented_count: number;
  draw_rule_version: string;
  result: Record<string, unknown>;
  created_at: string;
}

export interface FactorCatalogEntryRecord {
  id: number;
  catalog_id: string;
  factor_id: string;
  display_name: string;
  formula_definition: string;
  lineage: string;
  timing_semantics: string;
  missing_value_policy: string;
  scoring_eligible: boolean;
  created_at: string;
}

export interface FactorCatalogRecord {
  id: string;
  market: MarketCode;
  source_family: string;
  lineage_version: string;
  minimum_coverage_ratio: number;
  is_active: boolean;
  notes: string | null;
  created_at: string;
  entries: FactorCatalogEntryRecord[];
}

export interface FactorMaterializationRecord {
  id: number;
  run_id: string | null;
  catalog_id: string | null;
  factor_id: string;
  symbol: string;
  market: MarketCode;
  trading_date: string;
  value: number | null;
  source_available_at: string | null;
  factor_available_ts: string | null;
  availability_mode: string;
  created_at: string;
}

export interface ClusterMembershipRecord {
  id: number;
  snapshot_id: number;
  symbol: string;
  cluster_label: string;
  distance_to_centroid: number | null;
  created_at: string;
}

export interface ClusterSnapshotRecord {
  id: number;
  snapshot_version: string;
  run_id: string | null;
  factor_catalog_version: string | null;
  market: MarketCode;
  trading_date: string;
  cluster_count: number;
  symbol_count: number;
  status: string;
  notes: string | null;
  memberships: ClusterMembershipRecord[];
  created_at: string;
}

export interface PeerComparisonOverlayRecord {
  id: number;
  peer_feature_run_id: number;
  symbol: string;
  peer_symbol_count: number;
  peer_feature_value: number | null;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface PeerFeatureRunRecord {
  id: number;
  run_id: string | null;
  snapshot_id: number | null;
  peer_policy_version: string;
  market: MarketCode;
  trading_date: string;
  status: string;
  produced_feature_count: number;
  warning_count: number;
  warnings: string[];
  overlays: PeerComparisonOverlayRecord[];
  created_at: string;
}

export interface ExecutionOrderEventRecord {
  id: number;
  order_id: number;
  event_type: string;
  event_ts: string;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface ExecutionFillEventRecord {
  id: number;
  order_id: number;
  fill_ts: string;
  fill_price: number;
  quantity: number;
  slippage_bps: number | null;
  created_at: string;
}

export interface ExecutionPositionSnapshotRecord {
  id: number;
  order_id: number | null;
  run_id: string | null;
  route: ExecutionRoute;
  market: MarketCode;
  symbol: string;
  quantity: number;
  avg_price: number;
  snapshot_ts: string;
  created_at: string;
}

export interface LiveRiskCheckRecord {
  id: number;
  order_id: number;
  status: string;
  detail: Record<string, unknown>;
  checked_at: string;
  created_at: string;
}

export interface ExecutionOrderRecord {
  id: number;
  run_id: string | null;
  route: ExecutionRoute;
  market: MarketCode;
  symbol: string;
  side: ExecutionOrderSide;
  quantity: number;
  requested_price: number | null;
  status: string;
  simulation_profile_id: string | null;
  live_control_profile_id: string | null;
  failure_code: string | null;
  manual_confirmation: boolean;
  rejection_reason: string | null;
  submitted_at: string;
  acknowledged_at: string | null;
  created_at: string;
  events: ExecutionOrderEventRecord[];
  fills: ExecutionFillEventRecord[];
  positions: ExecutionPositionSnapshotRecord[];
  risk_checks?: LiveRiskCheckRecord[];
}

export interface KillSwitchRecord {
  id: number;
  scope_type: string;
  market: MarketCode | null;
  is_enabled: boolean;
  reason: string | null;
  created_at: string;
}

export interface AdaptiveProfileRecord {
  id: string;
  market: MarketCode;
  reward_definition_version: string;
  state_definition_version: string;
  notes: string | null;
  rollout_control_version: string | null;
  rollout_mode: AdaptiveMode | null;
  rollout_detail: Record<string, unknown>;
  created_at: string;
}

export interface AdaptiveTrainingRunRecord {
  id: number;
  profile_id: string | null;
  run_id: string | null;
  market: MarketCode;
  adaptive_mode: AdaptiveMode;
  reward_definition_version: string;
  state_definition_version: string;
  rollout_control_version: string;
  status: string;
  dataset_summary: Record<string, unknown>;
  artifact_registry: Record<string, unknown>;
  validation_error: string | null;
  created_at: string;
}
