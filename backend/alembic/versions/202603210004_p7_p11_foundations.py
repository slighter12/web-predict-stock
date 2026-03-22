"""add p7-p11 structural foundation tables

Revision ID: 202603210004
Revises: 202603210003
"""

import sqlalchemy as sa
from alembic import op

revision = "202603210004"
down_revision = "202603210003"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(
        column["name"] == column_name
        for column in sa.inspect(op.get_bind()).get_columns(table_name)
    )


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(
        index["name"] == index_name
        for index in sa.inspect(op.get_bind()).get_indexes(table_name)
    )


def _create_index_if_missing(
    index_name: str, table_name: str, columns: list[str], unique: bool = False
) -> None:
    if _has_table(table_name) and not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def _drop_index_if_exists(index_name: str, table_name: str) -> None:
    if _has_index(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    research_run_columns = [
        ("factor_catalog_version", sa.String(), True),
        ("scoring_factor_ids_json", sa.Text(), True),
        ("external_signal_policy_version", sa.String(), True),
        ("external_lineage_version", sa.String(), True),
        ("cluster_snapshot_version", sa.String(), True),
        ("peer_policy_version", sa.String(), True),
        ("peer_comparison_policy_version", sa.String(), True),
        ("execution_route", sa.String(), True),
        ("simulation_profile_id", sa.String(), True),
        ("simulation_adapter_version", sa.String(), True),
        ("live_control_profile_id", sa.String(), True),
        ("live_control_version", sa.String(), True),
        ("adaptive_mode", sa.String(), True),
        ("adaptive_profile_id", sa.String(), True),
        ("adaptive_contract_version", sa.String(), True),
        ("reward_definition_version", sa.String(), True),
        ("state_definition_version", sa.String(), True),
        ("rollout_control_version", sa.String(), True),
    ]
    for column_name, column_type, nullable in research_run_columns:
        if not _has_column("research_runs", column_name):
            op.add_column(
                "research_runs",
                sa.Column(column_name, column_type, nullable=nullable),
            )
    _create_index_if_missing(
        "ix_research_runs_factor_catalog_version",
        "research_runs",
        ["factor_catalog_version"],
    )
    _create_index_if_missing(
        "ix_research_runs_execution_route",
        "research_runs",
        ["execution_route"],
    )
    _create_index_if_missing(
        "ix_research_runs_simulation_profile_id",
        "research_runs",
        ["simulation_profile_id"],
    )
    _create_index_if_missing(
        "ix_research_runs_live_control_profile_id",
        "research_runs",
        ["live_control_profile_id"],
    )
    _create_index_if_missing(
        "ix_research_runs_adaptive_mode",
        "research_runs",
        ["adaptive_mode"],
    )
    _create_index_if_missing(
        "ix_research_runs_adaptive_profile_id",
        "research_runs",
        ["adaptive_profile_id"],
    )

    if not _has_table("external_raw_archives"):
        op.create_table(
            "external_raw_archives",
            sa.Column("id", sa.Integer(), nullable=False),
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
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_external_raw_archives_source_family", ["source_family"]),
        ("ix_external_raw_archives_market", ["market"]),
        ("ix_external_raw_archives_coverage_start", ["coverage_start"]),
        ("ix_external_raw_archives_coverage_end", ["coverage_end"]),
        ("ix_external_raw_archives_created_at", ["created_at"]),
    ):
        _create_index_if_missing(index_name, "external_raw_archives", columns)

    if not _has_table("external_signal_records"):
        op.create_table(
            "external_signal_records",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("archive_id", sa.Integer(), nullable=True),
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
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["archive_id"],
                ["external_raw_archives.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_external_signal_records_archive_id", ["archive_id"]),
        ("ix_external_signal_records_source_family", ["source_family"]),
        ("ix_external_signal_records_symbol", ["symbol"]),
        ("ix_external_signal_records_market", ["market"]),
        ("ix_external_signal_records_effective_date", ["effective_date"]),
        ("ix_external_signal_records_available_at", ["available_at"]),
        ("ix_external_signal_records_created_at", ["created_at"]),
        ("idx_external_signal_records_symbol_date", ["symbol", "effective_date"]),
    ):
        _create_index_if_missing(index_name, "external_signal_records", columns)

    if not _has_table("external_signal_audits"):
        op.create_table(
            "external_signal_audits",
            sa.Column("id", sa.Integer(), nullable=False),
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
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_external_signal_audits_source_family", ["source_family"]),
        ("ix_external_signal_audits_market", ["market"]),
        ("ix_external_signal_audits_created_at", ["created_at"]),
    ):
        _create_index_if_missing(index_name, "external_signal_audits", columns)

    if not _has_table("factor_catalogs"):
        op.create_table(
            "factor_catalogs",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("market", sa.String(), nullable=False),
            sa.Column("source_family", sa.String(), nullable=False),
            sa.Column("lineage_version", sa.String(), nullable=False),
            sa.Column("minimum_coverage_ratio", sa.Float(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_factor_catalogs_market", ["market"]),
        ("ix_factor_catalogs_is_active", ["is_active"]),
        ("ix_factor_catalogs_created_at", ["created_at"]),
    ):
        _create_index_if_missing(index_name, "factor_catalogs", columns)

    if not _has_table("factor_catalog_entries"):
        op.create_table(
            "factor_catalog_entries",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("catalog_id", sa.String(), nullable=False),
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
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["catalog_id"], ["factor_catalogs.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "catalog_id",
                "factor_id",
                name="uq_factor_catalog_entries_catalog_factor",
            ),
        )
    for index_name, columns in (
        ("ix_factor_catalog_entries_catalog_id", ["catalog_id"]),
        ("ix_factor_catalog_entries_created_at", ["created_at"]),
    ):
        _create_index_if_missing(index_name, "factor_catalog_entries", columns)

    if not _has_table("factor_materializations"):
        op.create_table(
            "factor_materializations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("run_id", sa.String(), nullable=True),
            sa.Column("catalog_id", sa.String(), nullable=True),
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
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["catalog_id"], ["factor_catalogs.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["run_id"], ["research_runs.run_id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_factor_materializations_run_id", ["run_id"]),
        ("ix_factor_materializations_catalog_id", ["catalog_id"]),
        ("ix_factor_materializations_factor_id", ["factor_id"]),
        ("ix_factor_materializations_symbol", ["symbol"]),
        ("ix_factor_materializations_market", ["market"]),
        ("ix_factor_materializations_trading_date", ["trading_date"]),
        ("ix_factor_materializations_created_at", ["created_at"]),
        (
            "idx_factor_materializations_run_symbol_date",
            ["run_id", "symbol", "trading_date"],
        ),
    ):
        _create_index_if_missing(index_name, "factor_materializations", columns)

    if not _has_table("factor_usability_observations"):
        op.create_table(
            "factor_usability_observations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("run_id", sa.String(), nullable=True),
            sa.Column("catalog_id", sa.String(), nullable=True),
            sa.Column("trading_date", sa.Date(), nullable=False),
            sa.Column("factor_id", sa.String(), nullable=False),
            sa.Column("coverage_ratio", sa.Float(), nullable=False),
            sa.Column("materialization_latency_hours", sa.Float(), nullable=True),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["catalog_id"], ["factor_catalogs.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["run_id"], ["research_runs.run_id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_factor_usability_observations_run_id", ["run_id"]),
        ("ix_factor_usability_observations_catalog_id", ["catalog_id"]),
        ("ix_factor_usability_observations_trading_date", ["trading_date"]),
        ("ix_factor_usability_observations_factor_id", ["factor_id"]),
        ("ix_factor_usability_observations_created_at", ["created_at"]),
    ):
        _create_index_if_missing(index_name, "factor_usability_observations", columns)

    if not _has_table("cluster_snapshots"):
        op.create_table(
            "cluster_snapshots",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("snapshot_version", sa.String(), nullable=False),
            sa.Column("run_id", sa.String(), nullable=True),
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
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["run_id"], ["research_runs.run_id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_cluster_snapshots_snapshot_version", ["snapshot_version"]),
        ("ix_cluster_snapshots_run_id", ["run_id"]),
        ("ix_cluster_snapshots_market", ["market"]),
        ("ix_cluster_snapshots_trading_date", ["trading_date"]),
        ("ix_cluster_snapshots_created_at", ["created_at"]),
    ):
        _create_index_if_missing(index_name, "cluster_snapshots", columns)

    if not _has_table("cluster_memberships"):
        op.create_table(
            "cluster_memberships",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("snapshot_id", sa.Integer(), nullable=False),
            sa.Column("symbol", sa.String(), nullable=False),
            sa.Column("cluster_label", sa.String(), nullable=False),
            sa.Column("distance_to_centroid", sa.Float(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["snapshot_id"], ["cluster_snapshots.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "snapshot_id", "symbol", name="uq_cluster_membership_snapshot_symbol"
            ),
        )
    for index_name, columns in (
        ("ix_cluster_memberships_snapshot_id", ["snapshot_id"]),
        ("ix_cluster_memberships_symbol", ["symbol"]),
        ("ix_cluster_memberships_created_at", ["created_at"]),
    ):
        _create_index_if_missing(index_name, "cluster_memberships", columns)

    if not _has_table("peer_feature_runs"):
        op.create_table(
            "peer_feature_runs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("run_id", sa.String(), nullable=True),
            sa.Column("snapshot_id", sa.Integer(), nullable=True),
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
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["run_id"], ["research_runs.run_id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["snapshot_id"], ["cluster_snapshots.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_peer_feature_runs_run_id", ["run_id"]),
        ("ix_peer_feature_runs_snapshot_id", ["snapshot_id"]),
        ("ix_peer_feature_runs_trading_date", ["trading_date"]),
        ("ix_peer_feature_runs_created_at", ["created_at"]),
    ):
        _create_index_if_missing(index_name, "peer_feature_runs", columns)

    if not _has_table("peer_comparison_overlays"):
        op.create_table(
            "peer_comparison_overlays",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("peer_feature_run_id", sa.Integer(), nullable=False),
            sa.Column("symbol", sa.String(), nullable=False),
            sa.Column("peer_symbol_count", sa.Integer(), nullable=False),
            sa.Column("peer_feature_value", sa.Float(), nullable=True),
            sa.Column("detail_json", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["peer_feature_run_id"], ["peer_feature_runs.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_peer_comparison_overlays_peer_feature_run_id", ["peer_feature_run_id"]),
        ("ix_peer_comparison_overlays_symbol", ["symbol"]),
        ("ix_peer_comparison_overlays_created_at", ["created_at"]),
    ):
        _create_index_if_missing(index_name, "peer_comparison_overlays", columns)

    if not _has_table("simulation_profiles"):
        op.create_table(
            "simulation_profiles",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("market", sa.String(), nullable=False),
            sa.Column("ack_latency_seconds", sa.Float(), nullable=False),
            sa.Column("fill_latency_seconds", sa.Float(), nullable=False),
            sa.Column("slippage_bps", sa.Float(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_simulation_profiles_market", ["market"]),
        ("ix_simulation_profiles_created_at", ["created_at"]),
    ):
        _create_index_if_missing(index_name, "simulation_profiles", columns)

    if not _has_table("execution_failure_taxonomies"):
        op.create_table(
            "execution_failure_taxonomies",
            sa.Column("code", sa.String(), nullable=False),
            sa.Column("route", sa.String(), nullable=False),
            sa.Column("category", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("code"),
        )
    for index_name, columns in (
        ("ix_execution_failure_taxonomies_route", ["route"]),
        ("ix_execution_failure_taxonomies_created_at", ["created_at"]),
    ):
        _create_index_if_missing(index_name, "execution_failure_taxonomies", columns)

    if not _has_table("execution_orders"):
        op.create_table(
            "execution_orders",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("run_id", sa.String(), nullable=True),
            sa.Column("route", sa.String(), nullable=False),
            sa.Column("market", sa.String(), nullable=False),
            sa.Column("symbol", sa.String(), nullable=False),
            sa.Column("side", sa.String(), nullable=False),
            sa.Column("quantity", sa.Float(), nullable=False),
            sa.Column("requested_price", sa.Float(), nullable=True),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("simulation_profile_id", sa.String(), nullable=True),
            sa.Column("live_control_profile_id", sa.String(), nullable=True),
            sa.Column("failure_code", sa.String(), nullable=True),
            sa.Column("manual_confirmation", sa.Boolean(), nullable=False),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["run_id"], ["research_runs.run_id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["simulation_profile_id"],
                ["simulation_profiles.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_execution_orders_run_id", ["run_id"]),
        ("ix_execution_orders_route", ["route"]),
        ("ix_execution_orders_market", ["market"]),
        ("ix_execution_orders_symbol", ["symbol"]),
        ("ix_execution_orders_status", ["status"]),
        ("ix_execution_orders_simulation_profile_id", ["simulation_profile_id"]),
        ("ix_execution_orders_live_control_profile_id", ["live_control_profile_id"]),
        ("ix_execution_orders_failure_code", ["failure_code"]),
        ("ix_execution_orders_created_at", ["created_at"]),
    ):
        _create_index_if_missing(index_name, "execution_orders", columns)

    if not _has_table("execution_order_events"):
        op.create_table(
            "execution_order_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("event_ts", sa.DateTime(timezone=True), nullable=False),
            sa.Column("detail_json", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["order_id"], ["execution_orders.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_execution_order_events_order_id", ["order_id"]),
        ("ix_execution_order_events_event_type", ["event_type"]),
        ("ix_execution_order_events_event_ts", ["event_ts"]),
        ("ix_execution_order_events_created_at", ["created_at"]),
    ):
        _create_index_if_missing(index_name, "execution_order_events", columns)

    if not _has_table("execution_fill_events"):
        op.create_table(
            "execution_fill_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("fill_ts", sa.DateTime(timezone=True), nullable=False),
            sa.Column("fill_price", sa.Float(), nullable=False),
            sa.Column("quantity", sa.Float(), nullable=False),
            sa.Column("slippage_bps", sa.Float(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["order_id"], ["execution_orders.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_execution_fill_events_order_id", ["order_id"]),
        ("ix_execution_fill_events_fill_ts", ["fill_ts"]),
        ("ix_execution_fill_events_created_at", ["created_at"]),
    ):
        _create_index_if_missing(index_name, "execution_fill_events", columns)

    if not _has_table("execution_position_snapshots"):
        op.create_table(
            "execution_position_snapshots",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=True),
            sa.Column("run_id", sa.String(), nullable=True),
            sa.Column("route", sa.String(), nullable=False),
            sa.Column("market", sa.String(), nullable=False),
            sa.Column("symbol", sa.String(), nullable=False),
            sa.Column("quantity", sa.Float(), nullable=False),
            sa.Column("avg_price", sa.Float(), nullable=False),
            sa.Column("snapshot_ts", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["order_id"], ["execution_orders.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["run_id"], ["research_runs.run_id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_execution_position_snapshots_order_id", ["order_id"]),
        ("ix_execution_position_snapshots_run_id", ["run_id"]),
        ("ix_execution_position_snapshots_route", ["route"]),
        ("ix_execution_position_snapshots_market", ["market"]),
        ("ix_execution_position_snapshots_symbol", ["symbol"]),
        ("ix_execution_position_snapshots_snapshot_ts", ["snapshot_ts"]),
        ("ix_execution_position_snapshots_created_at", ["created_at"]),
    ):
        _create_index_if_missing(index_name, "execution_position_snapshots", columns)

    if not _has_table("live_risk_checks"):
        op.create_table(
            "live_risk_checks",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("detail_json", sa.Text(), nullable=False),
            sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["order_id"], ["execution_orders.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_live_risk_checks_order_id", ["order_id"]),
        ("ix_live_risk_checks_status", ["status"]),
        ("ix_live_risk_checks_checked_at", ["checked_at"]),
        ("ix_live_risk_checks_created_at", ["created_at"]),
    ):
        _create_index_if_missing(index_name, "live_risk_checks", columns)

    if not _has_table("kill_switch_events"):
        op.create_table(
            "kill_switch_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("scope_type", sa.String(), nullable=False),
            sa.Column("market", sa.String(), nullable=True),
            sa.Column("is_enabled", sa.Boolean(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_kill_switch_events_scope_type", ["scope_type"]),
        ("ix_kill_switch_events_market", ["market"]),
        ("ix_kill_switch_events_created_at", ["created_at"]),
    ):
        _create_index_if_missing(index_name, "kill_switch_events", columns)

    if not _has_table("adaptive_profiles"):
        op.create_table(
            "adaptive_profiles",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("market", sa.String(), nullable=False),
            sa.Column("reward_definition_version", sa.String(), nullable=False),
            sa.Column("state_definition_version", sa.String(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_adaptive_profiles_market", ["market"]),
        ("ix_adaptive_profiles_created_at", ["created_at"]),
    ):
        _create_index_if_missing(index_name, "adaptive_profiles", columns)

    if not _has_table("adaptive_rollout_controls"):
        op.create_table(
            "adaptive_rollout_controls",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("profile_id", sa.String(), nullable=False),
            sa.Column("rollout_control_version", sa.String(), nullable=False),
            sa.Column("mode", sa.String(), nullable=False),
            sa.Column("detail_json", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["profile_id"], ["adaptive_profiles.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_adaptive_rollout_controls_profile_id", ["profile_id"]),
        ("ix_adaptive_rollout_controls_created_at", ["created_at"]),
    ):
        _create_index_if_missing(index_name, "adaptive_rollout_controls", columns)

    if not _has_table("adaptive_training_runs"):
        op.create_table(
            "adaptive_training_runs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("profile_id", sa.String(), nullable=True),
            sa.Column("run_id", sa.String(), nullable=True),
            sa.Column("market", sa.String(), nullable=False),
            sa.Column("adaptive_mode", sa.String(), nullable=False),
            sa.Column("reward_definition_version", sa.String(), nullable=False),
            sa.Column("state_definition_version", sa.String(), nullable=False),
            sa.Column("rollout_control_version", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("dataset_summary_json", sa.Text(), nullable=False),
            sa.Column("artifact_registry_json", sa.Text(), nullable=False),
            sa.Column("validation_error", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["profile_id"], ["adaptive_profiles.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["run_id"], ["research_runs.run_id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_adaptive_training_runs_profile_id", ["profile_id"]),
        ("ix_adaptive_training_runs_run_id", ["run_id"]),
        ("ix_adaptive_training_runs_market", ["market"]),
        ("ix_adaptive_training_runs_adaptive_mode", ["adaptive_mode"]),
        ("ix_adaptive_training_runs_status", ["status"]),
        ("ix_adaptive_training_runs_created_at", ["created_at"]),
    ):
        _create_index_if_missing(index_name, "adaptive_training_runs", columns)

    if not _has_table("adaptive_surface_exclusions"):
        op.create_table(
            "adaptive_surface_exclusions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("run_id", sa.String(), nullable=False),
            sa.Column("exclusion_surface", sa.String(), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["run_id"], ["research_runs.run_id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("run_id"),
        )
    for index_name, columns in (
        ("ix_adaptive_surface_exclusions_run_id", ["run_id"]),
        ("ix_adaptive_surface_exclusions_created_at", ["created_at"]),
    ):
        _create_index_if_missing(index_name, "adaptive_surface_exclusions", columns)


def downgrade() -> None:
    for table_name, indexes in (
        (
            "adaptive_surface_exclusions",
            [
                "ix_adaptive_surface_exclusions_created_at",
                "ix_adaptive_surface_exclusions_run_id",
            ],
        ),
        (
            "adaptive_training_runs",
            [
                "ix_adaptive_training_runs_created_at",
                "ix_adaptive_training_runs_status",
                "ix_adaptive_training_runs_adaptive_mode",
                "ix_adaptive_training_runs_market",
                "ix_adaptive_training_runs_run_id",
                "ix_adaptive_training_runs_profile_id",
            ],
        ),
        (
            "adaptive_rollout_controls",
            [
                "ix_adaptive_rollout_controls_created_at",
                "ix_adaptive_rollout_controls_profile_id",
            ],
        ),
        (
            "adaptive_profiles",
            ["ix_adaptive_profiles_created_at", "ix_adaptive_profiles_market"],
        ),
        (
            "kill_switch_events",
            [
                "ix_kill_switch_events_created_at",
                "ix_kill_switch_events_market",
                "ix_kill_switch_events_scope_type",
            ],
        ),
        (
            "live_risk_checks",
            [
                "ix_live_risk_checks_created_at",
                "ix_live_risk_checks_checked_at",
                "ix_live_risk_checks_status",
                "ix_live_risk_checks_order_id",
            ],
        ),
        (
            "execution_position_snapshots",
            [
                "ix_execution_position_snapshots_created_at",
                "ix_execution_position_snapshots_snapshot_ts",
                "ix_execution_position_snapshots_symbol",
                "ix_execution_position_snapshots_market",
                "ix_execution_position_snapshots_route",
                "ix_execution_position_snapshots_run_id",
                "ix_execution_position_snapshots_order_id",
            ],
        ),
        (
            "execution_fill_events",
            [
                "ix_execution_fill_events_created_at",
                "ix_execution_fill_events_fill_ts",
                "ix_execution_fill_events_order_id",
            ],
        ),
        (
            "execution_order_events",
            [
                "ix_execution_order_events_created_at",
                "ix_execution_order_events_event_ts",
                "ix_execution_order_events_event_type",
                "ix_execution_order_events_order_id",
            ],
        ),
        (
            "execution_orders",
            [
                "ix_execution_orders_created_at",
                "ix_execution_orders_failure_code",
                "ix_execution_orders_live_control_profile_id",
                "ix_execution_orders_simulation_profile_id",
                "ix_execution_orders_status",
                "ix_execution_orders_symbol",
                "ix_execution_orders_market",
                "ix_execution_orders_route",
                "ix_execution_orders_run_id",
            ],
        ),
        (
            "execution_failure_taxonomies",
            [
                "ix_execution_failure_taxonomies_created_at",
                "ix_execution_failure_taxonomies_route",
            ],
        ),
        (
            "simulation_profiles",
            ["ix_simulation_profiles_created_at", "ix_simulation_profiles_market"],
        ),
        (
            "peer_comparison_overlays",
            [
                "ix_peer_comparison_overlays_created_at",
                "ix_peer_comparison_overlays_symbol",
                "ix_peer_comparison_overlays_peer_feature_run_id",
            ],
        ),
        (
            "peer_feature_runs",
            [
                "ix_peer_feature_runs_created_at",
                "ix_peer_feature_runs_trading_date",
                "ix_peer_feature_runs_snapshot_id",
                "ix_peer_feature_runs_run_id",
            ],
        ),
        (
            "cluster_memberships",
            [
                "ix_cluster_memberships_created_at",
                "ix_cluster_memberships_symbol",
                "ix_cluster_memberships_snapshot_id",
            ],
        ),
        (
            "cluster_snapshots",
            [
                "ix_cluster_snapshots_created_at",
                "ix_cluster_snapshots_trading_date",
                "ix_cluster_snapshots_market",
                "ix_cluster_snapshots_run_id",
                "ix_cluster_snapshots_snapshot_version",
            ],
        ),
        (
            "factor_usability_observations",
            [
                "ix_factor_usability_observations_created_at",
                "ix_factor_usability_observations_factor_id",
                "ix_factor_usability_observations_trading_date",
                "ix_factor_usability_observations_catalog_id",
                "ix_factor_usability_observations_run_id",
            ],
        ),
        (
            "factor_materializations",
            [
                "idx_factor_materializations_run_symbol_date",
                "ix_factor_materializations_created_at",
                "ix_factor_materializations_trading_date",
                "ix_factor_materializations_market",
                "ix_factor_materializations_symbol",
                "ix_factor_materializations_factor_id",
                "ix_factor_materializations_catalog_id",
                "ix_factor_materializations_run_id",
            ],
        ),
        (
            "factor_catalog_entries",
            [
                "ix_factor_catalog_entries_created_at",
                "ix_factor_catalog_entries_catalog_id",
            ],
        ),
        (
            "factor_catalogs",
            [
                "ix_factor_catalogs_created_at",
                "ix_factor_catalogs_is_active",
                "ix_factor_catalogs_market",
            ],
        ),
        (
            "external_signal_audits",
            [
                "ix_external_signal_audits_created_at",
                "ix_external_signal_audits_market",
                "ix_external_signal_audits_source_family",
            ],
        ),
        (
            "external_signal_records",
            [
                "idx_external_signal_records_symbol_date",
                "ix_external_signal_records_created_at",
                "ix_external_signal_records_available_at",
                "ix_external_signal_records_effective_date",
                "ix_external_signal_records_market",
                "ix_external_signal_records_symbol",
                "ix_external_signal_records_source_family",
                "ix_external_signal_records_archive_id",
            ],
        ),
        (
            "external_raw_archives",
            [
                "ix_external_raw_archives_created_at",
                "ix_external_raw_archives_coverage_end",
                "ix_external_raw_archives_coverage_start",
                "ix_external_raw_archives_market",
                "ix_external_raw_archives_source_family",
            ],
        ),
    ):
        for index_name in indexes:
            _drop_index_if_exists(index_name, table_name)
        if _has_table(table_name):
            op.drop_table(table_name)

    for index_name in (
        "ix_research_runs_adaptive_profile_id",
        "ix_research_runs_adaptive_mode",
        "ix_research_runs_live_control_profile_id",
        "ix_research_runs_simulation_profile_id",
        "ix_research_runs_execution_route",
        "ix_research_runs_factor_catalog_version",
    ):
        _drop_index_if_exists(index_name, "research_runs")
    for column_name in (
        "rollout_control_version",
        "state_definition_version",
        "reward_definition_version",
        "adaptive_contract_version",
        "adaptive_profile_id",
        "adaptive_mode",
        "live_control_version",
        "live_control_profile_id",
        "simulation_adapter_version",
        "simulation_profile_id",
        "execution_route",
        "peer_comparison_policy_version",
        "peer_policy_version",
        "cluster_snapshot_version",
        "external_lineage_version",
        "external_signal_policy_version",
        "scoring_factor_ids_json",
        "factor_catalog_version",
    ):
        if _has_column("research_runs", column_name):
            op.drop_column("research_runs", column_name)
