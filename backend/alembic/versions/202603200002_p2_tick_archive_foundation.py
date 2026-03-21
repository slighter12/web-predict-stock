"""add p2 tick archive foundation

Revision ID: 202603200002
Revises: 202603200001
"""

import sqlalchemy as sa
from alembic import op

revision = "202603200002"
down_revision = "202603200001"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(
        index["name"] == index_name
        for index in sa.inspect(op.get_bind()).get_indexes(table_name)
    )


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(
        column["name"] == column_name
        for column in sa.inspect(op.get_bind()).get_columns(table_name)
    )


def _has_foreign_key(table_name: str, constraint_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(
        foreign_key["name"] == constraint_name
        for foreign_key in sa.inspect(op.get_bind()).get_foreign_keys(table_name)
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
    if not _has_table("tick_archive_runs"):
        op.create_table(
            "tick_archive_runs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("source_name", sa.String(), nullable=False),
            sa.Column("market", sa.String(), nullable=False),
            sa.Column("trading_date", sa.Date(), nullable=False),
            sa.Column("trigger_mode", sa.String(), nullable=False),
            sa.Column("scope", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("symbol_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "request_count", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "observation_count", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("abort_reason", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(
        "ix_tick_archive_runs_created_at", "tick_archive_runs", ["created_at"]
    )
    _create_index_if_missing(
        "ix_tick_archive_runs_market", "tick_archive_runs", ["market"]
    )
    _create_index_if_missing(
        "ix_tick_archive_runs_source_name", "tick_archive_runs", ["source_name"]
    )
    _create_index_if_missing(
        "ix_tick_archive_runs_status", "tick_archive_runs", ["status"]
    )
    _create_index_if_missing(
        "ix_tick_archive_runs_trading_date", "tick_archive_runs", ["trading_date"]
    )
    _create_index_if_missing(
        "ix_tick_archive_runs_trigger_mode", "tick_archive_runs", ["trigger_mode"]
    )

    if not _has_table("tick_archive_objects"):
        op.create_table(
            "tick_archive_objects",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("run_id", sa.Integer(), nullable=False),
            sa.Column("storage_backend", sa.String(), nullable=False),
            sa.Column("object_key", sa.String(), nullable=False),
            sa.Column("compression_codec", sa.String(), nullable=False),
            sa.Column("archive_layout_version", sa.String(), nullable=False),
            sa.Column(
                "compressed_bytes", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "uncompressed_bytes", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "compression_ratio", sa.Float(), nullable=False, server_default="0"
            ),
            sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "first_observation_ts", sa.DateTime(timezone=True), nullable=True
            ),
            sa.Column("last_observation_ts", sa.DateTime(timezone=True), nullable=True),
            sa.Column("checksum", sa.String(), nullable=False),
            sa.Column("retention_class", sa.String(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["run_id"],
                ["tick_archive_runs.id"],
                name="fk_tick_archive_objects_run",
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "object_key", name="uq_tick_archive_objects_object_key"
            ),
        )
    if (
        _has_table("tick_archive_objects")
        and _has_column("tick_archive_objects", "run_id")
        and not _has_foreign_key("tick_archive_objects", "fk_tick_archive_objects_run")
    ):
        op.create_foreign_key(
            "fk_tick_archive_objects_run",
            "tick_archive_objects",
            "tick_archive_runs",
            ["run_id"],
            ["id"],
            ondelete="CASCADE",
        )
    _create_index_if_missing(
        "ix_tick_archive_objects_created_at", "tick_archive_objects", ["created_at"]
    )
    _create_index_if_missing(
        "ix_tick_archive_objects_run_id", "tick_archive_objects", ["run_id"]
    )

    if not _has_table("tick_restore_runs"):
        op.create_table(
            "tick_restore_runs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("archive_object_id", sa.Integer(), nullable=False),
            sa.Column("benchmark_profile_id", sa.String(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("restore_status", sa.String(), nullable=False),
            sa.Column(
                "restored_row_count", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column("restore_started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "restore_completed_at", sa.DateTime(timezone=True), nullable=True
            ),
            sa.Column("elapsed_seconds", sa.Float(), nullable=True),
            sa.Column("throughput_gb_per_minute", sa.Float(), nullable=True),
            sa.Column("abort_reason", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["archive_object_id"],
                ["tick_archive_objects.id"],
                name="fk_tick_restore_runs_object",
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    if (
        _has_table("tick_restore_runs")
        and _has_column("tick_restore_runs", "archive_object_id")
        and not _has_foreign_key("tick_restore_runs", "fk_tick_restore_runs_object")
    ):
        op.create_foreign_key(
            "fk_tick_restore_runs_object",
            "tick_restore_runs",
            "tick_archive_objects",
            ["archive_object_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    _create_index_if_missing(
        "ix_tick_restore_runs_archive_object_id",
        "tick_restore_runs",
        ["archive_object_id"],
    )
    _create_index_if_missing(
        "ix_tick_restore_runs_created_at", "tick_restore_runs", ["created_at"]
    )
    _create_index_if_missing(
        "ix_tick_restore_runs_restore_status",
        "tick_restore_runs",
        ["restore_status"],
    )

    if not _has_table("tick_observations"):
        op.create_table(
            "tick_observations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("trading_date", sa.Date(), nullable=False),
            sa.Column("observation_ts", sa.DateTime(timezone=True), nullable=False),
            sa.Column("symbol", sa.String(), nullable=False),
            sa.Column("market", sa.String(), nullable=False),
            sa.Column("last_price", sa.Float(), nullable=True),
            sa.Column("last_size", sa.Integer(), nullable=True),
            sa.Column("cumulative_volume", sa.Integer(), nullable=True),
            sa.Column(
                "best_bid_prices_json", sa.Text(), nullable=False, server_default="[]"
            ),
            sa.Column(
                "best_bid_sizes_json", sa.Text(), nullable=False, server_default="[]"
            ),
            sa.Column(
                "best_ask_prices_json", sa.Text(), nullable=False, server_default="[]"
            ),
            sa.Column(
                "best_ask_sizes_json", sa.Text(), nullable=False, server_default="[]"
            ),
            sa.Column("source_name", sa.String(), nullable=False),
            sa.Column("archive_object_reference", sa.String(), nullable=False),
            sa.Column("parser_version", sa.String(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "archive_object_reference",
                "symbol",
                "observation_ts",
                name="uq_tick_observation_archive_symbol_ts",
            ),
        )
    _create_index_if_missing(
        "idx_tick_observations_symbol_ts",
        "tick_observations",
        ["symbol", "observation_ts"],
    )
    _create_index_if_missing(
        "ix_tick_observations_archive_object_reference",
        "tick_observations",
        ["archive_object_reference"],
    )
    _create_index_if_missing(
        "ix_tick_observations_created_at", "tick_observations", ["created_at"]
    )
    _create_index_if_missing(
        "ix_tick_observations_market", "tick_observations", ["market"]
    )
    _create_index_if_missing(
        "ix_tick_observations_observation_ts",
        "tick_observations",
        ["observation_ts"],
    )
    _create_index_if_missing(
        "ix_tick_observations_symbol", "tick_observations", ["symbol"]
    )
    _create_index_if_missing(
        "ix_tick_observations_trading_date", "tick_observations", ["trading_date"]
    )


def downgrade() -> None:
    _drop_index_if_exists("ix_tick_observations_trading_date", "tick_observations")
    _drop_index_if_exists("ix_tick_observations_symbol", "tick_observations")
    _drop_index_if_exists("ix_tick_observations_observation_ts", "tick_observations")
    _drop_index_if_exists("ix_tick_observations_market", "tick_observations")
    _drop_index_if_exists("ix_tick_observations_created_at", "tick_observations")
    _drop_index_if_exists(
        "ix_tick_observations_archive_object_reference", "tick_observations"
    )
    _drop_index_if_exists("idx_tick_observations_symbol_ts", "tick_observations")
    if _has_table("tick_observations"):
        op.drop_table("tick_observations")

    _drop_index_if_exists("ix_tick_restore_runs_restore_status", "tick_restore_runs")
    _drop_index_if_exists("ix_tick_restore_runs_created_at", "tick_restore_runs")
    _drop_index_if_exists("ix_tick_restore_runs_archive_object_id", "tick_restore_runs")
    if _has_table("tick_restore_runs"):
        op.drop_table("tick_restore_runs")

    _drop_index_if_exists("ix_tick_archive_objects_run_id", "tick_archive_objects")
    _drop_index_if_exists("ix_tick_archive_objects_created_at", "tick_archive_objects")
    if _has_table("tick_archive_objects"):
        op.drop_table("tick_archive_objects")

    _drop_index_if_exists("ix_tick_archive_runs_trigger_mode", "tick_archive_runs")
    _drop_index_if_exists("ix_tick_archive_runs_trading_date", "tick_archive_runs")
    _drop_index_if_exists("ix_tick_archive_runs_status", "tick_archive_runs")
    _drop_index_if_exists("ix_tick_archive_runs_source_name", "tick_archive_runs")
    _drop_index_if_exists("ix_tick_archive_runs_market", "tick_archive_runs")
    _drop_index_if_exists("ix_tick_archive_runs_created_at", "tick_archive_runs")
    if _has_table("tick_archive_runs"):
        op.drop_table("tick_archive_runs")
