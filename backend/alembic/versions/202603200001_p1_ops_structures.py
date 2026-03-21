"""add p1 ops structures

Revision ID: 202603200001
Revises: 202603190001
"""

import sqlalchemy as sa
from alembic import op

revision = "202603200001"
down_revision = "202603190001"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    indexes = sa.inspect(op.get_bind()).get_indexes(table_name)
    return any(index["name"] == index_name for index in indexes)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    columns = sa.inspect(op.get_bind()).get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def _has_foreign_key(table_name: str, constraint_name: str) -> bool:
    if not _has_table(table_name):
        return False
    foreign_keys = sa.inspect(op.get_bind()).get_foreign_keys(table_name)
    return any(foreign_key["name"] == constraint_name for foreign_key in foreign_keys)


def _create_index_if_missing(
    index_name: str, table_name: str, columns: list[str]
) -> None:
    if _has_table(table_name) and not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def _drop_index_if_exists(index_name: str, table_name: str) -> None:
    if _has_index(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    if not _has_table("benchmark_profiles"):
        op.create_table(
            "benchmark_profiles",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("cpu_class", sa.String(), nullable=False),
            sa.Column("memory_size", sa.String(), nullable=False),
            sa.Column("storage_type", sa.String(), nullable=False),
            sa.Column("compression_settings", sa.String(), nullable=False),
            sa.Column("archive_layout_version", sa.String(), nullable=False),
            sa.Column("network_class", sa.String(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(
        "ix_benchmark_profiles_created_at", "benchmark_profiles", ["created_at"]
    )

    if not _has_table("ingestion_watchlist"):
        op.create_table(
            "ingestion_watchlist",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("symbol", sa.String(), nullable=False),
            sa.Column("market", sa.String(), nullable=False),
            sa.Column("years", sa.Integer(), nullable=False, server_default="5"),
            sa.Column(
                "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
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
                name="uq_ingestion_watchlist_symbol_market",
            ),
        )
    _create_index_if_missing(
        "ix_ingestion_watchlist_created_at", "ingestion_watchlist", ["created_at"]
    )
    _create_index_if_missing(
        "ix_ingestion_watchlist_is_active", "ingestion_watchlist", ["is_active"]
    )
    _create_index_if_missing(
        "ix_ingestion_watchlist_market", "ingestion_watchlist", ["market"]
    )
    _create_index_if_missing(
        "ix_ingestion_watchlist_symbol", "ingestion_watchlist", ["symbol"]
    )

    if not _has_table("scheduled_ingestion_runs"):
        op.create_table(
            "scheduled_ingestion_runs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("watchlist_id", sa.Integer(), nullable=False),
            sa.Column("symbol", sa.String(), nullable=False),
            sa.Column("market", sa.String(), nullable=False),
            sa.Column("scheduled_for_date", sa.Date(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column(
                "attempt_count", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column("last_error_message", sa.Text(), nullable=True),
            sa.Column("first_attempt_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["watchlist_id"],
                ["ingestion_watchlist.id"],
                name="fk_sched_ing_runs_watchlist",
                ondelete="RESTRICT",
            ),
            sa.UniqueConstraint(
                "watchlist_id",
                "scheduled_for_date",
                name="uq_scheduled_ingestion_watchlist_slot",
            ),
        )
    if (
        _has_table("scheduled_ingestion_runs")
        and _has_column("scheduled_ingestion_runs", "watchlist_id")
        and not _has_foreign_key(
            "scheduled_ingestion_runs",
            "fk_sched_ing_runs_watchlist",
        )
    ):
        op.create_foreign_key(
            "fk_sched_ing_runs_watchlist",
            "scheduled_ingestion_runs",
            "ingestion_watchlist",
            ["watchlist_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    _create_index_if_missing(
        "ix_scheduled_ingestion_runs_created_at",
        "scheduled_ingestion_runs",
        ["created_at"],
    )
    _create_index_if_missing(
        "ix_scheduled_ingestion_runs_market", "scheduled_ingestion_runs", ["market"]
    )
    _create_index_if_missing(
        "ix_scheduled_ingestion_runs_scheduled_for_date",
        "scheduled_ingestion_runs",
        ["scheduled_for_date"],
    )
    _create_index_if_missing(
        "ix_scheduled_ingestion_runs_status", "scheduled_ingestion_runs", ["status"]
    )
    _create_index_if_missing(
        "ix_scheduled_ingestion_runs_symbol", "scheduled_ingestion_runs", ["symbol"]
    )
    _create_index_if_missing(
        "ix_scheduled_ingestion_runs_watchlist_id",
        "scheduled_ingestion_runs",
        ["watchlist_id"],
    )

    if not _has_table("scheduled_ingestion_attempts"):
        op.create_table(
            "scheduled_ingestion_attempts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("run_id", sa.Integer(), nullable=False),
            sa.Column("attempt_number", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("raw_payload_id", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["run_id"],
                ["scheduled_ingestion_runs.id"],
                name="fk_sched_ing_attempts_run",
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint(
                "run_id",
                "attempt_number",
                name="uq_scheduled_ingestion_attempt_run_number",
            ),
        )
    if (
        _has_table("scheduled_ingestion_attempts")
        and _has_column("scheduled_ingestion_attempts", "run_id")
        and not _has_foreign_key(
            "scheduled_ingestion_attempts",
            "fk_sched_ing_attempts_run",
        )
    ):
        op.create_foreign_key(
            "fk_sched_ing_attempts_run",
            "scheduled_ingestion_attempts",
            "scheduled_ingestion_runs",
            ["run_id"],
            ["id"],
            ondelete="CASCADE",
        )
    _create_index_if_missing(
        "ix_scheduled_ingestion_attempts_created_at",
        "scheduled_ingestion_attempts",
        ["created_at"],
    )
    _create_index_if_missing(
        "ix_scheduled_ingestion_attempts_raw_payload_id",
        "scheduled_ingestion_attempts",
        ["raw_payload_id"],
    )
    _create_index_if_missing(
        "ix_scheduled_ingestion_attempts_run_id",
        "scheduled_ingestion_attempts",
        ["run_id"],
    )
    _create_index_if_missing(
        "ix_scheduled_ingestion_attempts_status",
        "scheduled_ingestion_attempts",
        ["status"],
    )


def downgrade() -> None:
    _drop_index_if_exists(
        "ix_scheduled_ingestion_attempts_status", "scheduled_ingestion_attempts"
    )
    _drop_index_if_exists(
        "ix_scheduled_ingestion_attempts_run_id", "scheduled_ingestion_attempts"
    )
    _drop_index_if_exists(
        "ix_scheduled_ingestion_attempts_raw_payload_id",
        "scheduled_ingestion_attempts",
    )
    _drop_index_if_exists(
        "ix_scheduled_ingestion_attempts_created_at",
        "scheduled_ingestion_attempts",
    )
    if _has_table("scheduled_ingestion_attempts"):
        op.drop_table("scheduled_ingestion_attempts")

    _drop_index_if_exists(
        "ix_scheduled_ingestion_runs_watchlist_id", "scheduled_ingestion_runs"
    )
    _drop_index_if_exists(
        "ix_scheduled_ingestion_runs_symbol", "scheduled_ingestion_runs"
    )
    _drop_index_if_exists(
        "ix_scheduled_ingestion_runs_status", "scheduled_ingestion_runs"
    )
    _drop_index_if_exists(
        "ix_scheduled_ingestion_runs_scheduled_for_date",
        "scheduled_ingestion_runs",
    )
    _drop_index_if_exists(
        "ix_scheduled_ingestion_runs_market", "scheduled_ingestion_runs"
    )
    _drop_index_if_exists(
        "ix_scheduled_ingestion_runs_created_at", "scheduled_ingestion_runs"
    )
    if _has_table("scheduled_ingestion_runs"):
        op.drop_table("scheduled_ingestion_runs")

    _drop_index_if_exists("ix_ingestion_watchlist_symbol", "ingestion_watchlist")
    _drop_index_if_exists("ix_ingestion_watchlist_market", "ingestion_watchlist")
    _drop_index_if_exists("ix_ingestion_watchlist_is_active", "ingestion_watchlist")
    _drop_index_if_exists("ix_ingestion_watchlist_created_at", "ingestion_watchlist")
    if _has_table("ingestion_watchlist"):
        op.drop_table("ingestion_watchlist")

    _drop_index_if_exists("ix_benchmark_profiles_created_at", "benchmark_profiles")
    if _has_table("benchmark_profiles"):
        op.drop_table("benchmark_profiles")
