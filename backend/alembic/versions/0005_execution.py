"""execution schema

Revision ID: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

metadata = sa.MetaData()
_existing_table_names = {"research_runs"}

sa.Table(
    "research_runs",
    metadata,
    sa.Column("run_id", sa.String(), primary_key=True),
)

simulation_profiles = sa.Table(
    "simulation_profiles",
    metadata,
    sa.Column("id", sa.String(), primary_key=True),
    sa.Column("market", sa.String(), nullable=False),
    sa.Column("ack_latency_seconds", sa.Float(), nullable=False),
    sa.Column("fill_latency_seconds", sa.Float(), nullable=False),
    sa.Column("slippage_bps", sa.Float(), nullable=False),
    sa.Column("notes", sa.Text(), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_simulation_profiles_created_at", "created_at"),
    sa.Index("ix_simulation_profiles_market", "market"),
)

live_control_profiles = sa.Table(
    "live_control_profiles",
    metadata,
    sa.Column("id", sa.String(), primary_key=True),
    sa.Column("market", sa.String(), nullable=False),
    sa.Column("live_control_version", sa.String(), nullable=False),
    sa.Column("detail_json", sa.Text(), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_live_control_profiles_created_at", "created_at"),
    sa.Index("ix_live_control_profiles_market", "market"),
)

execution_failure_taxonomies = sa.Table(
    "execution_failure_taxonomies",
    metadata,
    sa.Column("code", sa.String(), primary_key=True),
    sa.Column("route", sa.String(), nullable=False),
    sa.Column("category", sa.String(), nullable=False),
    sa.Column("description", sa.Text(), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_execution_failure_taxonomies_created_at", "created_at"),
    sa.Index("ix_execution_failure_taxonomies_route", "route"),
)

execution_orders = sa.Table(
    "execution_orders",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column(
        "run_id",
        sa.String(),
        sa.ForeignKey("research_runs.run_id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("route", sa.String(), nullable=False),
    sa.Column("market", sa.String(), nullable=False),
    sa.Column("symbol", sa.String(), nullable=False),
    sa.Column("side", sa.String(), nullable=False),
    sa.Column("quantity", sa.Float(), nullable=False),
    sa.Column("requested_price", sa.Float(), nullable=True),
    sa.Column("status", sa.String(), nullable=False),
    sa.Column(
        "simulation_profile_id",
        sa.String(),
        sa.ForeignKey("simulation_profiles.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column(
        "live_control_profile_id",
        sa.String(),
        sa.ForeignKey("live_control_profiles.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("failure_code", sa.String(), nullable=True),
    sa.Column("manual_confirmation", sa.Boolean(), nullable=False),
    sa.Column("rejection_reason", sa.Text(), nullable=True),
    sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_execution_orders_created_at", "created_at"),
    sa.Index("ix_execution_orders_failure_code", "failure_code"),
    sa.Index("ix_execution_orders_live_control_profile_id", "live_control_profile_id"),
    sa.Index("ix_execution_orders_market", "market"),
    sa.Index("ix_execution_orders_route", "route"),
    sa.Index("ix_execution_orders_run_id", "run_id"),
    sa.Index("ix_execution_orders_simulation_profile_id", "simulation_profile_id"),
    sa.Index("ix_execution_orders_status", "status"),
    sa.Index("ix_execution_orders_symbol", "symbol"),
)

execution_order_events = sa.Table(
    "execution_order_events",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column(
        "order_id",
        sa.Integer(),
        sa.ForeignKey("execution_orders.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("event_type", sa.String(), nullable=False),
    sa.Column("event_ts", sa.DateTime(timezone=True), nullable=False),
    sa.Column("detail_json", sa.Text(), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_execution_order_events_created_at", "created_at"),
    sa.Index("ix_execution_order_events_event_ts", "event_ts"),
    sa.Index("ix_execution_order_events_event_type", "event_type"),
    sa.Index("ix_execution_order_events_order_id", "order_id"),
)

execution_fill_events = sa.Table(
    "execution_fill_events",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column(
        "order_id",
        sa.Integer(),
        sa.ForeignKey("execution_orders.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("fill_ts", sa.DateTime(timezone=True), nullable=False),
    sa.Column("fill_price", sa.Float(), nullable=False),
    sa.Column("quantity", sa.Float(), nullable=False),
    sa.Column("slippage_bps", sa.Float(), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_execution_fill_events_created_at", "created_at"),
    sa.Index("ix_execution_fill_events_fill_ts", "fill_ts"),
    sa.Index("ix_execution_fill_events_order_id", "order_id"),
)

execution_position_snapshots = sa.Table(
    "execution_position_snapshots",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column(
        "order_id",
        sa.Integer(),
        sa.ForeignKey("execution_orders.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column(
        "run_id",
        sa.String(),
        sa.ForeignKey("research_runs.run_id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("route", sa.String(), nullable=False),
    sa.Column("market", sa.String(), nullable=False),
    sa.Column("symbol", sa.String(), nullable=False),
    sa.Column("quantity", sa.Float(), nullable=False),
    sa.Column("avg_price", sa.Float(), nullable=False),
    sa.Column("snapshot_ts", sa.DateTime(timezone=True), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_execution_position_snapshots_created_at", "created_at"),
    sa.Index("ix_execution_position_snapshots_market", "market"),
    sa.Index("ix_execution_position_snapshots_order_id", "order_id"),
    sa.Index("ix_execution_position_snapshots_route", "route"),
    sa.Index("ix_execution_position_snapshots_run_id", "run_id"),
    sa.Index("ix_execution_position_snapshots_snapshot_ts", "snapshot_ts"),
    sa.Index("ix_execution_position_snapshots_symbol", "symbol"),
)

live_risk_checks = sa.Table(
    "live_risk_checks",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column(
        "order_id",
        sa.Integer(),
        sa.ForeignKey("execution_orders.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("status", sa.String(), nullable=False),
    sa.Column("detail_json", sa.Text(), nullable=False),
    sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_live_risk_checks_checked_at", "checked_at"),
    sa.Index("ix_live_risk_checks_created_at", "created_at"),
    sa.Index("ix_live_risk_checks_order_id", "order_id"),
    sa.Index("ix_live_risk_checks_status", "status"),
)

kill_switch_events = sa.Table(
    "kill_switch_events",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("scope_type", sa.String(), nullable=False),
    sa.Column("market", sa.String(), nullable=True),
    sa.Column("is_enabled", sa.Boolean(), nullable=False),
    sa.Column("reason", sa.Text(), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_kill_switch_events_created_at", "created_at"),
    sa.Index("ix_kill_switch_events_market", "market"),
    sa.Index("ix_kill_switch_events_scope_type", "scope_type"),
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in metadata.sorted_tables:
        if table.name in _existing_table_names:
            continue
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(metadata.sorted_tables):
        if table.name in _existing_table_names:
            continue
        table.drop(bind=bind, checkfirst=True)
