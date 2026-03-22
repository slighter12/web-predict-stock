"""research foundations schema

Revision ID: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

metadata = sa.MetaData()

research_run_liquidity_coverages = sa.Table(
    "research_run_liquidity_coverages",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column(
        "run_id",
        sa.String(),
        sa.ForeignKey("research_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("bucket_key", sa.String(), nullable=False),
    sa.Column("bucket_label", sa.String(), nullable=False),
    sa.Column("full_universe_count", sa.Integer(), nullable=False),
    sa.Column("execution_universe_count", sa.Integer(), nullable=False),
    sa.Column("full_universe_ratio", sa.Float(), nullable=False),
    sa.Column("execution_coverage_ratio", sa.Float(), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.UniqueConstraint(
        "run_id",
        "bucket_key",
        name="uq_research_run_liquidity_coverages_run_bucket",
    ),
    sa.Index("ix_research_run_liquidity_coverages_created_at", "created_at"),
    sa.Index("ix_research_run_liquidity_coverages_run_id", "run_id"),
)

microstructure_observations = sa.Table(
    "microstructure_observations",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column(
        "run_id",
        sa.String(),
        sa.ForeignKey("research_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("monitor_profile_id", sa.String(), nullable=False),
    sa.Column("market", sa.String(), nullable=False),
    sa.Column("trading_date", sa.Date(), nullable=False),
    sa.Column("full_universe_count", sa.Integer(), nullable=False),
    sa.Column("execution_universe_count", sa.Integer(), nullable=False),
    sa.Column("execution_universe_ratio", sa.Float(), nullable=False),
    sa.Column("stale_mark_with_open_positions", sa.Boolean(), nullable=False),
    sa.Column("liquidity_bucket_schema_version", sa.String(), nullable=False),
    sa.Column("bucket_coverages_json", sa.Text(), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.UniqueConstraint(
        "monitor_profile_id",
        "market",
        "trading_date",
        name="uq_microstructure_observations_profile_market_date",
    ),
    sa.Index("ix_microstructure_observations_created_at", "created_at"),
    sa.Index("ix_microstructure_observations_market", "market"),
    sa.Index("ix_microstructure_observations_monitor_profile_id", "monitor_profile_id"),
    sa.Index("ix_microstructure_observations_run_id", "run_id"),
    sa.Index("ix_microstructure_observations_trading_date", "trading_date"),
)

external_raw_archives = sa.Table(
    "external_raw_archives",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("source_family", sa.String(), nullable=False),
    sa.Column("market", sa.String(), nullable=False),
    sa.Column("coverage_start", sa.Date(), nullable=False),
    sa.Column("coverage_end", sa.Date(), nullable=False),
    sa.Column("record_count", sa.Integer(), nullable=False),
    sa.Column("payload_body", sa.Text(), nullable=True),
    sa.Column("notes", sa.Text(), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_external_raw_archives_coverage_end", "coverage_end"),
    sa.Index("ix_external_raw_archives_coverage_start", "coverage_start"),
    sa.Index("ix_external_raw_archives_created_at", "created_at"),
    sa.Index("ix_external_raw_archives_market", "market"),
    sa.Index("ix_external_raw_archives_source_family", "source_family"),
)

external_signal_audits = sa.Table(
    "external_signal_audits",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("source_family", sa.String(), nullable=False),
    sa.Column("market", sa.String(), nullable=False),
    sa.Column("audit_window_start", sa.Date(), nullable=False),
    sa.Column("audit_window_end", sa.Date(), nullable=False),
    sa.Column("sample_size", sa.Integer(), nullable=False),
    sa.Column("fallback_sample_size", sa.Integer(), nullable=False),
    sa.Column("undocumented_count", sa.Integer(), nullable=False),
    sa.Column("draw_rule_version", sa.String(), nullable=False),
    sa.Column("result_json", sa.Text(), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_external_signal_audits_created_at", "created_at"),
    sa.Index("ix_external_signal_audits_market", "market"),
    sa.Index("ix_external_signal_audits_source_family", "source_family"),
)

external_signal_records = sa.Table(
    "external_signal_records",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column(
        "archive_id",
        sa.Integer(),
        sa.ForeignKey("external_raw_archives.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("source_family", sa.String(), nullable=False),
    sa.Column("source_record_type", sa.String(), nullable=False),
    sa.Column("symbol", sa.String(), nullable=False),
    sa.Column("market", sa.String(), nullable=False),
    sa.Column("effective_date", sa.Date(), nullable=False),
    sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("availability_mode", sa.String(), nullable=False),
    sa.Column("lineage_version", sa.String(), nullable=False),
    sa.Column("detail_json", sa.Text(), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("idx_external_signal_records_symbol_date", "symbol", "effective_date"),
    sa.Index("ix_external_signal_records_archive_id", "archive_id"),
    sa.Index("ix_external_signal_records_available_at", "available_at"),
    sa.Index("ix_external_signal_records_created_at", "created_at"),
    sa.Index("ix_external_signal_records_effective_date", "effective_date"),
    sa.Index("ix_external_signal_records_market", "market"),
    sa.Index("ix_external_signal_records_source_family", "source_family"),
    sa.Index("ix_external_signal_records_symbol", "symbol"),
)

factor_catalogs = sa.Table(
    "factor_catalogs",
    metadata,
    sa.Column("id", sa.String(), primary_key=True),
    sa.Column("market", sa.String(), nullable=False),
    sa.Column("source_family", sa.String(), nullable=False),
    sa.Column("lineage_version", sa.String(), nullable=False),
    sa.Column("minimum_coverage_ratio", sa.Float(), nullable=False),
    sa.Column("is_active", sa.Boolean(), nullable=False),
    sa.Column("notes", sa.Text(), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("idx_factor_catalogs_active_created_at", "is_active", "created_at"),
    sa.Index("ix_factor_catalogs_created_at", "created_at"),
    sa.Index("ix_factor_catalogs_market", "market"),
)

factor_catalog_entries = sa.Table(
    "factor_catalog_entries",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column(
        "catalog_id",
        sa.String(),
        sa.ForeignKey("factor_catalogs.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("factor_id", sa.String(), nullable=False),
    sa.Column("display_name", sa.String(), nullable=False),
    sa.Column("formula_definition", sa.Text(), nullable=False),
    sa.Column("lineage", sa.String(), nullable=False),
    sa.Column("timing_semantics", sa.String(), nullable=False),
    sa.Column("missing_value_policy", sa.String(), nullable=False),
    sa.Column("scoring_eligible", sa.Boolean(), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.UniqueConstraint(
        "catalog_id",
        "factor_id",
        name="uq_factor_catalog_entries_catalog_factor",
    ),
    sa.Index("ix_factor_catalog_entries_catalog_id", "catalog_id"),
    sa.Index("ix_factor_catalog_entries_created_at", "created_at"),
)

factor_materializations = sa.Table(
    "factor_materializations",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column(
        "run_id",
        sa.String(),
        sa.ForeignKey("research_runs.run_id", ondelete="CASCADE"),
        nullable=True,
    ),
    sa.Column(
        "catalog_id",
        sa.String(),
        sa.ForeignKey("factor_catalogs.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("factor_id", sa.String(), nullable=False),
    sa.Column("symbol", sa.String(), nullable=False),
    sa.Column("market", sa.String(), nullable=False),
    sa.Column("trading_date", sa.Date(), nullable=False),
    sa.Column("value", sa.Float(), nullable=True),
    sa.Column("source_available_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("factor_available_ts", sa.DateTime(timezone=True), nullable=True),
    sa.Column("availability_mode", sa.String(), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index(
        "idx_factor_materializations_run_symbol_date",
        "run_id",
        "symbol",
        "trading_date",
    ),
    sa.Index("ix_factor_materializations_catalog_id", "catalog_id"),
    sa.Index("ix_factor_materializations_created_at", "created_at"),
    sa.Index("ix_factor_materializations_factor_id", "factor_id"),
    sa.Index("ix_factor_materializations_market", "market"),
    sa.Index("ix_factor_materializations_run_id", "run_id"),
    sa.Index("ix_factor_materializations_symbol", "symbol"),
    sa.Index("ix_factor_materializations_trading_date", "trading_date"),
)

factor_usability_observations = sa.Table(
    "factor_usability_observations",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column(
        "run_id",
        sa.String(),
        sa.ForeignKey("research_runs.run_id", ondelete="CASCADE"),
        nullable=True,
    ),
    sa.Column(
        "catalog_id",
        sa.String(),
        sa.ForeignKey("factor_catalogs.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("trading_date", sa.Date(), nullable=False),
    sa.Column("factor_id", sa.String(), nullable=False),
    sa.Column("coverage_ratio", sa.Float(), nullable=False),
    sa.Column("materialization_latency_hours", sa.Float(), nullable=True),
    sa.Column("status", sa.String(), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_factor_usability_observations_catalog_id", "catalog_id"),
    sa.Index("ix_factor_usability_observations_created_at", "created_at"),
    sa.Index("ix_factor_usability_observations_factor_id", "factor_id"),
    sa.Index("ix_factor_usability_observations_run_id", "run_id"),
    sa.Index("ix_factor_usability_observations_trading_date", "trading_date"),
)

cluster_snapshots = sa.Table(
    "cluster_snapshots",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("snapshot_version", sa.String(), nullable=False),
    sa.Column(
        "run_id",
        sa.String(),
        sa.ForeignKey("research_runs.run_id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("factor_catalog_version", sa.String(), nullable=True),
    sa.Column("market", sa.String(), nullable=False),
    sa.Column("trading_date", sa.Date(), nullable=False),
    sa.Column("cluster_count", sa.Integer(), nullable=False),
    sa.Column("symbol_count", sa.Integer(), nullable=False),
    sa.Column("status", sa.String(), nullable=False),
    sa.Column("notes", sa.Text(), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_cluster_snapshots_created_at", "created_at"),
    sa.Index("ix_cluster_snapshots_market", "market"),
    sa.Index("ix_cluster_snapshots_run_id", "run_id"),
    sa.Index("ix_cluster_snapshots_snapshot_version", "snapshot_version"),
    sa.Index("ix_cluster_snapshots_trading_date", "trading_date"),
)

cluster_memberships = sa.Table(
    "cluster_memberships",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column(
        "snapshot_id",
        sa.Integer(),
        sa.ForeignKey("cluster_snapshots.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("symbol", sa.String(), nullable=False),
    sa.Column("cluster_label", sa.String(), nullable=False),
    sa.Column("distance_to_centroid", sa.Float(), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.UniqueConstraint(
        "snapshot_id",
        "symbol",
        name="uq_cluster_membership_snapshot_symbol",
    ),
    sa.Index("ix_cluster_memberships_created_at", "created_at"),
    sa.Index("ix_cluster_memberships_snapshot_id", "snapshot_id"),
    sa.Index("ix_cluster_memberships_symbol", "symbol"),
)

peer_feature_runs = sa.Table(
    "peer_feature_runs",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column(
        "run_id",
        sa.String(),
        sa.ForeignKey("research_runs.run_id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column(
        "snapshot_id",
        sa.Integer(),
        sa.ForeignKey("cluster_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("peer_policy_version", sa.String(), nullable=False),
    sa.Column("market", sa.String(), nullable=False),
    sa.Column("trading_date", sa.Date(), nullable=False),
    sa.Column("status", sa.String(), nullable=False),
    sa.Column("produced_feature_count", sa.Integer(), nullable=False),
    sa.Column("warning_count", sa.Integer(), nullable=False),
    sa.Column("warning_json", sa.Text(), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_peer_feature_runs_created_at", "created_at"),
    sa.Index("ix_peer_feature_runs_market", "market"),
    sa.Index("ix_peer_feature_runs_run_id", "run_id"),
    sa.Index("ix_peer_feature_runs_snapshot_id", "snapshot_id"),
    sa.Index("ix_peer_feature_runs_trading_date", "trading_date"),
)

peer_comparison_overlays = sa.Table(
    "peer_comparison_overlays",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column(
        "peer_feature_run_id",
        sa.Integer(),
        sa.ForeignKey("peer_feature_runs.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("symbol", sa.String(), nullable=False),
    sa.Column("peer_symbol_count", sa.Integer(), nullable=False),
    sa.Column("peer_feature_value", sa.Float(), nullable=True),
    sa.Column("detail_json", sa.Text(), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_peer_comparison_overlays_created_at", "created_at"),
    sa.Index("ix_peer_comparison_overlays_peer_feature_run_id", "peer_feature_run_id"),
    sa.Index("ix_peer_comparison_overlays_symbol", "symbol"),
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in metadata.sorted_tables:
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(metadata.sorted_tables):
        table.drop(bind=bind, checkfirst=True)
