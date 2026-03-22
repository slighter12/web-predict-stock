"""market ops schema

Revision ID: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

metadata = sa.MetaData()

ingestion_watchlist = sa.Table(
    "ingestion_watchlist",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("symbol", sa.String(), nullable=False),
    sa.Column("market", sa.String(), nullable=False),
    sa.Column("years", sa.Integer(), nullable=False),
    sa.Column("is_active", sa.Boolean(), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.UniqueConstraint(
        "symbol", "market", name="uq_ingestion_watchlist_symbol_market"
    ),
    sa.Index("idx_ingestion_watchlist_active_created_at", "is_active", "created_at"),
    sa.Index("ix_ingestion_watchlist_created_at", "created_at"),
    sa.Index("ix_ingestion_watchlist_market", "market"),
    sa.Index("ix_ingestion_watchlist_symbol", "symbol"),
)

scheduled_ingestion_runs = sa.Table(
    "scheduled_ingestion_runs",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column(
        "watchlist_id",
        sa.Integer(),
        sa.ForeignKey("ingestion_watchlist.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("symbol", sa.String(), nullable=False),
    sa.Column("market", sa.String(), nullable=False),
    sa.Column("scheduled_for_date", sa.Date(), nullable=False),
    sa.Column("status", sa.String(), nullable=False),
    sa.Column("attempt_count", sa.Integer(), nullable=False),
    sa.Column("last_error_message", sa.Text(), nullable=True),
    sa.Column("first_attempt_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.UniqueConstraint(
        "watchlist_id",
        "scheduled_for_date",
        name="uq_scheduled_ingestion_watchlist_slot",
    ),
    sa.Index("ix_scheduled_ingestion_runs_created_at", "created_at"),
    sa.Index("ix_scheduled_ingestion_runs_market", "market"),
    sa.Index("ix_scheduled_ingestion_runs_scheduled_for_date", "scheduled_for_date"),
    sa.Index("ix_scheduled_ingestion_runs_status", "status"),
    sa.Index("ix_scheduled_ingestion_runs_symbol", "symbol"),
    sa.Index("ix_scheduled_ingestion_runs_watchlist_id", "watchlist_id"),
)

scheduled_ingestion_attempts = sa.Table(
    "scheduled_ingestion_attempts",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column(
        "run_id",
        sa.Integer(),
        sa.ForeignKey("scheduled_ingestion_runs.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("attempt_number", sa.Integer(), nullable=False),
    sa.Column("status", sa.String(), nullable=False),
    sa.Column("raw_payload_id", sa.Integer(), nullable=True),
    sa.Column("error_message", sa.Text(), nullable=True),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.UniqueConstraint(
        "run_id",
        "attempt_number",
        name="uq_scheduled_ingestion_attempt_run_number",
    ),
    sa.Index("ix_scheduled_ingestion_attempts_created_at", "created_at"),
    sa.Index("ix_scheduled_ingestion_attempts_raw_payload_id", "raw_payload_id"),
    sa.Index("ix_scheduled_ingestion_attempts_run_id", "run_id"),
    sa.Index("ix_scheduled_ingestion_attempts_status", "status"),
)

symbol_lifecycle_records = sa.Table(
    "symbol_lifecycle_records",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
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
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.UniqueConstraint(
        "symbol",
        "market",
        "event_type",
        "effective_date",
        name="uq_symbol_lifecycle_record",
    ),
    sa.Index("ix_symbol_lifecycle_records_created_at", "created_at"),
    sa.Index("ix_symbol_lifecycle_records_effective_date", "effective_date"),
    sa.Index("ix_symbol_lifecycle_records_event_type", "event_type"),
    sa.Index("ix_symbol_lifecycle_records_market", "market"),
    sa.Index("ix_symbol_lifecycle_records_raw_payload_id", "raw_payload_id"),
    sa.Index("ix_symbol_lifecycle_records_symbol", "symbol"),
)

important_events = sa.Table(
    "important_events",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
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
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.UniqueConstraint(
        "symbol",
        "market",
        "event_type",
        "event_publication_ts",
        name="uq_important_event",
    ),
    sa.Index("ix_important_events_created_at", "created_at"),
    sa.Index("ix_important_events_effective_date", "effective_date"),
    sa.Index("ix_important_events_event_publication_ts", "event_publication_ts"),
    sa.Index("ix_important_events_event_type", "event_type"),
    sa.Index("ix_important_events_market", "market"),
    sa.Index("ix_important_events_raw_payload_id", "raw_payload_id"),
    sa.Index("ix_important_events_symbol", "symbol"),
)

tw_company_profiles = sa.Table(
    "tw_company_profiles",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("symbol", sa.String(), nullable=False),
    sa.Column("market", sa.String(), nullable=False),
    sa.Column("exchange", sa.String(), nullable=False),
    sa.Column("board", sa.String(), nullable=False),
    sa.Column("company_name", sa.String(), nullable=False),
    sa.Column("isin_code", sa.String(), nullable=True),
    sa.Column("industry_category", sa.String(), nullable=True),
    sa.Column("listing_date", sa.Date(), nullable=True),
    sa.Column("trading_status", sa.String(), nullable=False),
    sa.Column("source_name", sa.String(), nullable=False),
    sa.Column("raw_payload_id", sa.Integer(), nullable=True),
    sa.Column("archive_object_reference", sa.String(), nullable=True),
    sa.Column("notes", sa.Text(), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.UniqueConstraint(
        "symbol", "exchange", name="uq_tw_company_profiles_symbol_exchange"
    ),
    sa.Index("ix_tw_company_profiles_board", "board"),
    sa.Index("ix_tw_company_profiles_created_at", "created_at"),
    sa.Index("ix_tw_company_profiles_exchange", "exchange"),
    sa.Index("ix_tw_company_profiles_industry_category", "industry_category"),
    sa.Index("ix_tw_company_profiles_listing_date", "listing_date"),
    sa.Index("ix_tw_company_profiles_market", "market"),
    sa.Index("ix_tw_company_profiles_raw_payload_id", "raw_payload_id"),
    sa.Index("ix_tw_company_profiles_symbol", "symbol"),
    sa.Index("ix_tw_company_profiles_trading_status", "trading_status"),
    sa.Index("ix_tw_company_profiles_updated_at", "updated_at"),
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in metadata.sorted_tables:
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(metadata.sorted_tables):
        table.drop(bind=bind, checkfirst=True)
