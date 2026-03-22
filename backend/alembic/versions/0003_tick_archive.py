"""tick archive schema

Revision ID: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

metadata = sa.MetaData()

tick_archive_runs = sa.Table(
    "tick_archive_runs",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("source_name", sa.String(), nullable=False),
    sa.Column("market", sa.String(), nullable=False),
    sa.Column("trading_date", sa.Date(), nullable=False),
    sa.Column("trigger_mode", sa.String(), nullable=False),
    sa.Column("scope", sa.String(), nullable=False),
    sa.Column("status", sa.String(), nullable=False),
    sa.Column("notes", sa.Text(), nullable=True),
    sa.Column("symbol_count", sa.Integer(), nullable=False),
    sa.Column("request_count", sa.Integer(), nullable=False),
    sa.Column("observation_count", sa.Integer(), nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("abort_reason", sa.Text(), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_tick_archive_runs_created_at", "created_at"),
    sa.Index("ix_tick_archive_runs_market", "market"),
    sa.Index("ix_tick_archive_runs_source_name", "source_name"),
    sa.Index("ix_tick_archive_runs_status", "status"),
    sa.Index("ix_tick_archive_runs_trading_date", "trading_date"),
    sa.Index("ix_tick_archive_runs_trigger_mode", "trigger_mode"),
)

tick_archive_objects = sa.Table(
    "tick_archive_objects",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column(
        "run_id",
        sa.Integer(),
        sa.ForeignKey("tick_archive_runs.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("storage_backend", sa.String(), nullable=False),
    sa.Column("object_key", sa.String(), nullable=False, unique=True),
    sa.Column("compression_codec", sa.String(), nullable=False),
    sa.Column("archive_layout_version", sa.String(), nullable=False),
    sa.Column("compressed_bytes", sa.Integer(), nullable=False),
    sa.Column("uncompressed_bytes", sa.Integer(), nullable=False),
    sa.Column("compression_ratio", sa.Float(), nullable=False),
    sa.Column("record_count", sa.Integer(), nullable=False),
    sa.Column("first_observation_ts", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_observation_ts", sa.DateTime(timezone=True), nullable=True),
    sa.Column("checksum", sa.String(), nullable=False),
    sa.Column("retention_class", sa.String(), nullable=False),
    sa.Column("backup_backend", sa.String(), nullable=True),
    sa.Column("backup_object_key", sa.String(), nullable=True),
    sa.Column("backup_status", sa.String(), nullable=True),
    sa.Column("backup_completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("backup_error", sa.Text(), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_tick_archive_objects_backup_status", "backup_status"),
    sa.Index("ix_tick_archive_objects_created_at", "created_at"),
    sa.Index("ix_tick_archive_objects_run_id", "run_id"),
)

tick_restore_runs = sa.Table(
    "tick_restore_runs",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column(
        "archive_object_id",
        sa.Integer(),
        sa.ForeignKey("tick_archive_objects.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("benchmark_profile_id", sa.String(), nullable=True),
    sa.Column("notes", sa.Text(), nullable=True),
    sa.Column("restore_status", sa.String(), nullable=False),
    sa.Column("restored_row_count", sa.Integer(), nullable=False),
    sa.Column("restore_started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("restore_completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("elapsed_seconds", sa.Float(), nullable=True),
    sa.Column("throughput_gb_per_minute", sa.Float(), nullable=True),
    sa.Column("abort_reason", sa.Text(), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_tick_restore_runs_archive_object_id", "archive_object_id"),
    sa.Index("ix_tick_restore_runs_created_at", "created_at"),
    sa.Index("ix_tick_restore_runs_restore_status", "restore_status"),
)

tick_observations = sa.Table(
    "tick_observations",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("trading_date", sa.Date(), nullable=False),
    sa.Column("observation_ts", sa.DateTime(timezone=True), nullable=False),
    sa.Column("symbol", sa.String(), nullable=False),
    sa.Column("market", sa.String(), nullable=False),
    sa.Column("last_price", sa.Float(), nullable=True),
    sa.Column("last_size", sa.Integer(), nullable=True),
    sa.Column("cumulative_volume", sa.Integer(), nullable=True),
    sa.Column("best_bid_prices_json", sa.Text(), nullable=False),
    sa.Column("best_bid_sizes_json", sa.Text(), nullable=False),
    sa.Column("best_ask_prices_json", sa.Text(), nullable=False),
    sa.Column("best_ask_sizes_json", sa.Text(), nullable=False),
    sa.Column("source_name", sa.String(), nullable=False),
    sa.Column("archive_object_reference", sa.String(), nullable=False),
    sa.Column("parser_version", sa.String(), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.UniqueConstraint(
        "archive_object_reference",
        "symbol",
        "observation_ts",
        name="uq_tick_observation_archive_symbol_ts",
    ),
    sa.Index("idx_tick_observations_symbol_ts", "symbol", "observation_ts"),
    sa.Index(
        "ix_tick_observations_archive_object_reference", "archive_object_reference"
    ),
    sa.Index("ix_tick_observations_created_at", "created_at"),
    sa.Index("ix_tick_observations_market", "market"),
    sa.Index("ix_tick_observations_observation_ts", "observation_ts"),
    sa.Index("ix_tick_observations_symbol", "symbol"),
    sa.Index("ix_tick_observations_trading_date", "trading_date"),
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in metadata.sorted_tables:
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(metadata.sorted_tables):
        table.drop(bind=bind, checkfirst=True)
