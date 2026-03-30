"""minute ohlcv schema

Revision ID: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

metadata = sa.MetaData()

minute_ohlcv = sa.Table(
    "minute_ohlcv",
    metadata,
    sa.Column("market", sa.String(), primary_key=True),
    sa.Column("symbol", sa.String(), primary_key=True),
    sa.Column("bar_ts", sa.DateTime(timezone=True), primary_key=True),
    sa.Column("trading_date", sa.Date(), nullable=False),
    sa.Column("source", sa.String(), nullable=False),
    sa.Column("open", sa.Float(), nullable=False),
    sa.Column("high", sa.Float(), nullable=False),
    sa.Column("low", sa.Float(), nullable=False),
    sa.Column("close", sa.Float(), nullable=False),
    sa.Column("volume", sa.Integer(), nullable=False),
    sa.Column("raw_payload_id", sa.Integer(), nullable=True),
    sa.Column("parser_version", sa.String(), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("idx_minute_ohlcv_symbol_bar_ts", "symbol", "bar_ts"),
    sa.Index(
        "idx_minute_ohlcv_market_symbol_trading_date",
        "market",
        "symbol",
        "trading_date",
    ),
    sa.Index("ix_minute_ohlcv_market", "market"),
    sa.Index("ix_minute_ohlcv_trading_date", "trading_date"),
    sa.Index("ix_minute_ohlcv_source", "source"),
    sa.Index("ix_minute_ohlcv_raw_payload_id", "raw_payload_id"),
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in metadata.sorted_tables:
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(metadata.sorted_tables):
        table.drop(bind=bind, checkfirst=True)
