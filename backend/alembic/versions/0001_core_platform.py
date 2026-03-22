"""core platform schema

Revision ID: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

metadata = sa.MetaData()

benchmark_profiles = sa.Table(
    "benchmark_profiles",
    metadata,
    sa.Column("id", sa.String(), primary_key=True),
    sa.Column("cpu_class", sa.String(), nullable=False),
    sa.Column("memory_size", sa.String(), nullable=False),
    sa.Column("storage_type", sa.String(), nullable=False),
    sa.Column("compression_settings", sa.String(), nullable=False),
    sa.Column("archive_layout_version", sa.String(), nullable=False),
    sa.Column("network_class", sa.String(), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_benchmark_profiles_created_at", "created_at"),
)

daily_ohlcv = sa.Table(
    "daily_ohlcv",
    metadata,
    sa.Column("date", sa.Date(), primary_key=True),
    sa.Column("symbol", sa.String(), primary_key=True),
    sa.Column("source", sa.String(), nullable=False),
    sa.Column("market", sa.String(), nullable=False),
    sa.Column("open", sa.Float(), nullable=False),
    sa.Column("high", sa.Float(), nullable=False),
    sa.Column("low", sa.Float(), nullable=False),
    sa.Column("close", sa.Float(), nullable=False),
    sa.Column("volume", sa.Integer(), nullable=False),
    sa.Column("raw_payload_id", sa.Integer(), nullable=True),
    sa.Column("archive_object_reference", sa.String(), nullable=True),
    sa.Column("parser_version", sa.String(), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("idx_daily_ohlcv_symbol_date", "symbol", "date"),
    sa.Index("ix_daily_ohlcv_market", "market"),
    sa.Index("ix_daily_ohlcv_raw_payload_id", "raw_payload_id"),
    sa.Index("ix_daily_ohlcv_source", "source"),
)

raw_ingest_audit = sa.Table(
    "raw_ingest_audit",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("source_name", sa.String(), nullable=False),
    sa.Column("symbol", sa.String(), nullable=False),
    sa.Column("market", sa.String(), nullable=False),
    sa.Column("fetch_timestamp", sa.DateTime(timezone=True), nullable=False),
    sa.Column("parser_version", sa.String(), nullable=False),
    sa.Column("fetch_status", sa.String(), nullable=False),
    sa.Column("expected_symbol_context", sa.String(), nullable=False),
    sa.Column("payload_body", sa.Text(), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_raw_ingest_audit_market", "market"),
    sa.Index("ix_raw_ingest_audit_source_name", "source_name"),
    sa.Index("ix_raw_ingest_audit_symbol", "symbol"),
)

research_runs = sa.Table(
    "research_runs",
    metadata,
    sa.Column("run_id", sa.String(), primary_key=True),
    sa.Column("request_id", sa.String(), nullable=True),
    sa.Column("status", sa.String(), nullable=False),
    sa.Column("market", sa.String(), nullable=True),
    sa.Column("symbols_json", sa.Text(), nullable=False),
    sa.Column("strategy_type", sa.String(), nullable=True),
    sa.Column("runtime_mode", sa.String(), nullable=True),
    sa.Column("default_bundle_version", sa.String(), nullable=True),
    sa.Column("effective_threshold", sa.Float(), nullable=True),
    sa.Column("effective_top_n", sa.Integer(), nullable=True),
    sa.Column("allow_proactive_sells", sa.Boolean(), nullable=True),
    sa.Column("config_sources_json", sa.Text(), nullable=True),
    sa.Column("fallback_audit_json", sa.Text(), nullable=True),
    sa.Column("validation_outcome_json", sa.Text(), nullable=True),
    sa.Column("rejection_reason", sa.Text(), nullable=True),
    sa.Column("request_payload_json", sa.Text(), nullable=True),
    sa.Column("metrics_json", sa.Text(), nullable=True),
    sa.Column("warnings_json", sa.Text(), nullable=True),
    sa.Column("threshold_policy_version", sa.String(), nullable=True),
    sa.Column("price_basis_version", sa.String(), nullable=True),
    sa.Column("benchmark_comparability_gate", sa.Boolean(), nullable=True),
    sa.Column("comparison_eligibility", sa.String(), nullable=True),
    sa.Column("investability_screening_active", sa.Boolean(), nullable=True),
    sa.Column("capacity_screening_active", sa.Boolean(), nullable=True),
    sa.Column("capacity_screening_version", sa.String(), nullable=True),
    sa.Column("adv_basis_version", sa.String(), nullable=True),
    sa.Column("missing_feature_policy_version", sa.String(), nullable=True),
    sa.Column("execution_cost_model_version", sa.String(), nullable=True),
    sa.Column("split_policy_version", sa.String(), nullable=True),
    sa.Column("bootstrap_policy_version", sa.String(), nullable=True),
    sa.Column("ic_overlap_policy_version", sa.String(), nullable=True),
    sa.Column("comparison_review_matrix_version", sa.String(), nullable=True),
    sa.Column("scheduled_review_cadence", sa.String(), nullable=True),
    sa.Column("model_family", sa.String(), nullable=True),
    sa.Column("training_output_contract_version", sa.String(), nullable=True),
    sa.Column("adoption_comparison_policy_version", sa.String(), nullable=True),
    sa.Column("factor_catalog_version", sa.String(), nullable=True),
    sa.Column("scoring_factor_ids_json", sa.Text(), nullable=True),
    sa.Column("external_signal_policy_version", sa.String(), nullable=True),
    sa.Column("external_lineage_version", sa.String(), nullable=True),
    sa.Column("cluster_snapshot_version", sa.String(), nullable=True),
    sa.Column("peer_policy_version", sa.String(), nullable=True),
    sa.Column("peer_comparison_policy_version", sa.String(), nullable=True),
    sa.Column("execution_route", sa.String(), nullable=True),
    sa.Column("simulation_profile_id", sa.String(), nullable=True),
    sa.Column("simulation_adapter_version", sa.String(), nullable=True),
    sa.Column("live_control_profile_id", sa.String(), nullable=True),
    sa.Column("live_control_version", sa.String(), nullable=True),
    sa.Column("adaptive_mode", sa.String(), nullable=True),
    sa.Column("adaptive_profile_id", sa.String(), nullable=True),
    sa.Column("adaptive_contract_version", sa.String(), nullable=True),
    sa.Column("reward_definition_version", sa.String(), nullable=True),
    sa.Column("state_definition_version", sa.String(), nullable=True),
    sa.Column("rollout_control_version", sa.String(), nullable=True),
    sa.Column("tradability_state", sa.String(), nullable=True),
    sa.Column("tradability_contract_version", sa.String(), nullable=True),
    sa.Column("missing_feature_policy_state", sa.String(), nullable=True),
    sa.Column("corporate_event_state", sa.String(), nullable=True),
    sa.Column("full_universe_count", sa.Integer(), nullable=True),
    sa.Column("execution_universe_count", sa.Integer(), nullable=True),
    sa.Column("execution_universe_ratio", sa.Float(), nullable=True),
    sa.Column("liquidity_bucket_schema_version", sa.String(), nullable=True),
    sa.Column("stale_mark_days_with_open_positions", sa.Integer(), nullable=True),
    sa.Column("stale_risk_share", sa.Float(), nullable=True),
    sa.Column("monitor_profile_id", sa.String(), nullable=True),
    sa.Column("monitor_observation_status", sa.String(), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_research_runs_adaptive_mode", "adaptive_mode"),
    sa.Index("ix_research_runs_adaptive_profile_id", "adaptive_profile_id"),
    sa.Index("ix_research_runs_created_at", "created_at"),
    sa.Index("ix_research_runs_execution_route", "execution_route"),
    sa.Index("ix_research_runs_factor_catalog_version", "factor_catalog_version"),
    sa.Index("ix_research_runs_live_control_profile_id", "live_control_profile_id"),
    sa.Index("ix_research_runs_market", "market"),
    sa.Index("ix_research_runs_model_family", "model_family"),
    sa.Index("ix_research_runs_monitor_profile_id", "monitor_profile_id"),
    sa.Index("ix_research_runs_request_id", "request_id"),
    sa.Index("ix_research_runs_runtime_mode", "runtime_mode"),
    sa.Index("ix_research_runs_simulation_profile_id", "simulation_profile_id"),
    sa.Index("ix_research_runs_status", "status"),
)

normalized_replay_runs = sa.Table(
    "normalized_replay_runs",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("raw_payload_id", sa.Integer(), nullable=False),
    sa.Column("source_name", sa.String(), nullable=False),
    sa.Column("symbol", sa.String(), nullable=False),
    sa.Column("market", sa.String(), nullable=False),
    sa.Column("archive_object_reference", sa.String(), nullable=True),
    sa.Column("parser_version", sa.String(), nullable=False),
    sa.Column("benchmark_profile_id", sa.String(), nullable=True),
    sa.Column("notes", sa.Text(), nullable=True),
    sa.Column("restore_status", sa.String(), nullable=False),
    sa.Column("abort_reason", sa.Text(), nullable=True),
    sa.Column("restored_row_count", sa.Integer(), nullable=False),
    sa.Column("replay_started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("replay_completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_normalized_replay_runs_created_at", "created_at"),
    sa.Index("ix_normalized_replay_runs_market", "market"),
    sa.Index("ix_normalized_replay_runs_raw_payload_id", "raw_payload_id"),
    sa.Index("ix_normalized_replay_runs_restore_status", "restore_status"),
    sa.Index("ix_normalized_replay_runs_source_name", "source_name"),
    sa.Index("ix_normalized_replay_runs_symbol", "symbol"),
)

recovery_drill_schedules = sa.Table(
    "recovery_drill_schedules",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("market", sa.String(), nullable=False),
    sa.Column("symbol", sa.String(), nullable=True),
    sa.Column("cadence", sa.String(), nullable=False),
    sa.Column("day_of_month", sa.Integer(), nullable=False),
    sa.Column("timezone", sa.String(), nullable=False),
    sa.Column("benchmark_profile_id", sa.String(), nullable=False),
    sa.Column("notes", sa.Text(), nullable=True),
    sa.Column("is_active", sa.Boolean(), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_recovery_drill_schedules_created_at", "created_at"),
    sa.Index(
        "idx_recovery_drill_schedules_active_created_at",
        "is_active",
        "created_at",
    ),
    sa.Index("ix_recovery_drill_schedules_market", "market"),
    sa.Index("ix_recovery_drill_schedules_symbol", "symbol"),
)

recovery_drills = sa.Table(
    "recovery_drills",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("raw_payload_id", sa.Integer(), nullable=True),
    sa.Column("replay_run_id", sa.Integer(), nullable=True),
    sa.Column("benchmark_profile_id", sa.String(), nullable=True),
    sa.Column("notes", sa.Text(), nullable=True),
    sa.Column("status", sa.String(), nullable=False),
    sa.Column("trigger_mode", sa.String(), nullable=False),
    sa.Column(
        "schedule_id",
        sa.Integer(),
        sa.ForeignKey("recovery_drill_schedules.id", ondelete="RESTRICT"),
        nullable=True,
    ),
    sa.Column("scheduled_for_date", sa.Date(), nullable=True),
    sa.Column("latest_replayable_day", sa.Date(), nullable=True),
    sa.Column("completed_trading_day_delta", sa.Integer(), nullable=True),
    sa.Column("abort_reason", sa.Text(), nullable=True),
    sa.Column("drill_started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("drill_completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.UniqueConstraint(
        "schedule_id",
        "scheduled_for_date",
        name="uq_recovery_drill_schedule_slot",
    ),
    sa.Index("ix_recovery_drills_created_at", "created_at"),
    sa.Index("ix_recovery_drills_raw_payload_id", "raw_payload_id"),
    sa.Index("ix_recovery_drills_replay_run_id", "replay_run_id"),
    sa.Index("ix_recovery_drills_schedule_id", "schedule_id"),
    sa.Index("ix_recovery_drills_scheduled_for_date", "scheduled_for_date"),
    sa.Index("ix_recovery_drills_status", "status"),
    sa.Index("ix_recovery_drills_trigger_mode", "trigger_mode"),
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in metadata.sorted_tables:
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(metadata.sorted_tables):
        table.drop(bind=bind, checkfirst=True)
