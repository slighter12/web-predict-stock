"""initial platform schema

Revision ID: 202603180001
"""

import sqlalchemy as sa
from alembic import op

revision = "202603180001"
down_revision = None
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    indexes = sa.inspect(op.get_bind()).get_indexes(table_name)
    return any(index["name"] == index_name for index in indexes)


def _create_index_if_missing(
    index_name: str, table_name: str, columns: list[str]
) -> None:
    if not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def _drop_index_if_exists(index_name: str, table_name: str) -> None:
    if _has_index(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def _drop_table_if_exists(table_name: str) -> None:
    if _has_table(table_name):
        op.drop_table(table_name)


def upgrade() -> None:
    if not _has_table("daily_ohlcv"):
        op.create_table(
            "daily_ohlcv",
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("symbol", sa.String(), nullable=False),
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
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("date", "symbol"),
        )
    _create_index_if_missing(
        "idx_daily_ohlcv_symbol_date", "daily_ohlcv", ["symbol", "date"]
    )
    _create_index_if_missing("ix_daily_ohlcv_market", "daily_ohlcv", ["market"])
    _create_index_if_missing(
        "ix_daily_ohlcv_raw_payload_id", "daily_ohlcv", ["raw_payload_id"]
    )
    _create_index_if_missing("ix_daily_ohlcv_source", "daily_ohlcv", ["source"])

    if not _has_table("raw_ingest_audit"):
        op.create_table(
            "raw_ingest_audit",
            sa.Column("id", sa.Integer(), nullable=False),
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
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_raw_ingest_audit_market", "raw_ingest_audit", ["market"])
    _create_index_if_missing(
        "ix_raw_ingest_audit_source_name", "raw_ingest_audit", ["source_name"]
    )
    _create_index_if_missing("ix_raw_ingest_audit_symbol", "raw_ingest_audit", ["symbol"])

    if not _has_table("research_runs"):
        op.create_table(
            "research_runs",
            sa.Column("run_id", sa.String(), nullable=False),
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
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("run_id"),
        )
    _create_index_if_missing("ix_research_runs_created_at", "research_runs", ["created_at"])
    _create_index_if_missing("ix_research_runs_request_id", "research_runs", ["request_id"])
    _create_index_if_missing(
        "ix_research_runs_runtime_mode", "research_runs", ["runtime_mode"]
    )
    _create_index_if_missing("ix_research_runs_status", "research_runs", ["status"])
    _create_index_if_missing("ix_research_runs_market", "research_runs", ["market"])

    if not _has_table("normalized_replay_runs"):
        op.create_table(
            "normalized_replay_runs",
            sa.Column("id", sa.Integer(), nullable=False),
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
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(
        "ix_normalized_replay_runs_created_at", "normalized_replay_runs", ["created_at"]
    )
    _create_index_if_missing(
        "ix_normalized_replay_runs_market", "normalized_replay_runs", ["market"]
    )
    _create_index_if_missing(
        "ix_normalized_replay_runs_raw_payload_id",
        "normalized_replay_runs",
        ["raw_payload_id"],
    )
    _create_index_if_missing(
        "ix_normalized_replay_runs_restore_status",
        "normalized_replay_runs",
        ["restore_status"],
    )
    _create_index_if_missing(
        "ix_normalized_replay_runs_source_name",
        "normalized_replay_runs",
        ["source_name"],
    )
    _create_index_if_missing(
        "ix_normalized_replay_runs_symbol", "normalized_replay_runs", ["symbol"]
    )

    if not _has_table("recovery_drills"):
        op.create_table(
            "recovery_drills",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("raw_payload_id", sa.Integer(), nullable=False),
            sa.Column("replay_run_id", sa.Integer(), nullable=True),
            sa.Column("benchmark_profile_id", sa.String(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("latest_replayable_day", sa.Date(), nullable=True),
            sa.Column("completed_trading_day_delta", sa.Integer(), nullable=True),
            sa.Column("abort_reason", sa.Text(), nullable=True),
            sa.Column("drill_started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("drill_completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_recovery_drills_created_at", "recovery_drills", ["created_at"])
    _create_index_if_missing(
        "ix_recovery_drills_raw_payload_id", "recovery_drills", ["raw_payload_id"]
    )
    _create_index_if_missing(
        "ix_recovery_drills_replay_run_id", "recovery_drills", ["replay_run_id"]
    )
    _create_index_if_missing("ix_recovery_drills_status", "recovery_drills", ["status"])

    if not _has_table("symbol_lifecycle_records"):
        op.create_table(
            "symbol_lifecycle_records",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("symbol", sa.String(), nullable=False),
            sa.Column("market", sa.String(), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("effective_date", sa.Date(), nullable=False),
            sa.Column("reference_symbol", sa.String(), nullable=True),
            sa.Column("source_name", sa.String(), nullable=False),
            sa.Column("raw_payload_id", sa.Integer(), nullable=True),
            sa.Column("archive_object_reference", sa.String(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "symbol",
                "market",
                "event_type",
                "effective_date",
                name="uq_symbol_lifecycle_record",
            ),
        )
    _create_index_if_missing(
        "ix_symbol_lifecycle_records_created_at",
        "symbol_lifecycle_records",
        ["created_at"],
    )
    _create_index_if_missing(
        "ix_symbol_lifecycle_records_effective_date",
        "symbol_lifecycle_records",
        ["effective_date"],
    )
    _create_index_if_missing(
        "ix_symbol_lifecycle_records_event_type",
        "symbol_lifecycle_records",
        ["event_type"],
    )
    _create_index_if_missing(
        "ix_symbol_lifecycle_records_market", "symbol_lifecycle_records", ["market"]
    )
    _create_index_if_missing(
        "ix_symbol_lifecycle_records_raw_payload_id",
        "symbol_lifecycle_records",
        ["raw_payload_id"],
    )
    _create_index_if_missing(
        "ix_symbol_lifecycle_records_symbol", "symbol_lifecycle_records", ["symbol"]
    )

    if not _has_table("important_events"):
        op.create_table(
            "important_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("symbol", sa.String(), nullable=False),
            sa.Column("market", sa.String(), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("effective_date", sa.Date(), nullable=True),
            sa.Column("event_publication_ts", sa.DateTime(timezone=True), nullable=False),
            sa.Column("timestamp_source_class", sa.String(), nullable=False),
            sa.Column("source_name", sa.String(), nullable=False),
            sa.Column("raw_payload_id", sa.Integer(), nullable=True),
            sa.Column("archive_object_reference", sa.String(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "symbol",
                "market",
                "event_type",
                "event_publication_ts",
                name="uq_important_event",
            ),
        )
    _create_index_if_missing(
        "ix_important_events_created_at", "important_events", ["created_at"]
    )
    _create_index_if_missing(
        "ix_important_events_effective_date", "important_events", ["effective_date"]
    )
    _create_index_if_missing(
        "ix_important_events_event_publication_ts",
        "important_events",
        ["event_publication_ts"],
    )
    _create_index_if_missing(
        "ix_important_events_event_type", "important_events", ["event_type"]
    )
    _create_index_if_missing("ix_important_events_market", "important_events", ["market"])
    _create_index_if_missing(
        "ix_important_events_raw_payload_id", "important_events", ["raw_payload_id"]
    )
    _create_index_if_missing("ix_important_events_symbol", "important_events", ["symbol"])


def downgrade() -> None:
    _drop_index_if_exists("ix_important_events_symbol", "important_events")
    _drop_index_if_exists("ix_important_events_raw_payload_id", "important_events")
    _drop_index_if_exists("ix_important_events_market", "important_events")
    _drop_index_if_exists("ix_important_events_event_type", "important_events")
    _drop_index_if_exists(
        "ix_important_events_event_publication_ts", "important_events"
    )
    _drop_index_if_exists("ix_important_events_effective_date", "important_events")
    _drop_index_if_exists("ix_important_events_created_at", "important_events")
    _drop_table_if_exists("important_events")

    _drop_index_if_exists(
        "ix_symbol_lifecycle_records_symbol", "symbol_lifecycle_records"
    )
    _drop_index_if_exists(
        "ix_symbol_lifecycle_records_raw_payload_id", "symbol_lifecycle_records"
    )
    _drop_index_if_exists(
        "ix_symbol_lifecycle_records_market", "symbol_lifecycle_records"
    )
    _drop_index_if_exists(
        "ix_symbol_lifecycle_records_event_type", "symbol_lifecycle_records"
    )
    _drop_index_if_exists(
        "ix_symbol_lifecycle_records_effective_date", "symbol_lifecycle_records"
    )
    _drop_index_if_exists(
        "ix_symbol_lifecycle_records_created_at", "symbol_lifecycle_records"
    )
    _drop_table_if_exists("symbol_lifecycle_records")

    _drop_index_if_exists("ix_recovery_drills_status", "recovery_drills")
    _drop_index_if_exists("ix_recovery_drills_replay_run_id", "recovery_drills")
    _drop_index_if_exists("ix_recovery_drills_raw_payload_id", "recovery_drills")
    _drop_index_if_exists("ix_recovery_drills_created_at", "recovery_drills")
    _drop_table_if_exists("recovery_drills")

    _drop_index_if_exists(
        "ix_normalized_replay_runs_symbol", "normalized_replay_runs"
    )
    _drop_index_if_exists(
        "ix_normalized_replay_runs_source_name", "normalized_replay_runs"
    )
    _drop_index_if_exists(
        "ix_normalized_replay_runs_restore_status", "normalized_replay_runs"
    )
    _drop_index_if_exists(
        "ix_normalized_replay_runs_raw_payload_id", "normalized_replay_runs"
    )
    _drop_index_if_exists(
        "ix_normalized_replay_runs_market", "normalized_replay_runs"
    )
    _drop_index_if_exists(
        "ix_normalized_replay_runs_created_at", "normalized_replay_runs"
    )
    _drop_table_if_exists("normalized_replay_runs")

    _drop_index_if_exists("ix_research_runs_market", "research_runs")
    _drop_index_if_exists("ix_research_runs_status", "research_runs")
    _drop_index_if_exists("ix_research_runs_runtime_mode", "research_runs")
    _drop_index_if_exists("ix_research_runs_request_id", "research_runs")
    _drop_index_if_exists("ix_research_runs_created_at", "research_runs")
    _drop_table_if_exists("research_runs")
