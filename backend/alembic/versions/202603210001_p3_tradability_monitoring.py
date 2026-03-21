"""add p3 tradability monitoring

Revision ID: 202603210001
Revises: 202603200002
"""

import sqlalchemy as sa
from alembic import op

revision = "202603210001"
down_revision = "202603200002"
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
    new_columns = [
        ("investability_screening_active", sa.Boolean(), True),
        ("capacity_screening_active", sa.Boolean(), True),
        ("capacity_screening_version", sa.String(), True),
        ("adv_basis_version", sa.String(), True),
        ("missing_feature_policy_version", sa.String(), True),
        ("execution_cost_model_version", sa.String(), True),
        ("tradability_state", sa.String(), True),
        ("tradability_contract_version", sa.String(), True),
        ("missing_feature_policy_state", sa.String(), True),
        ("corporate_event_state", sa.String(), True),
        ("full_universe_count", sa.Integer(), True),
        ("execution_universe_count", sa.Integer(), True),
        ("execution_universe_ratio", sa.Float(), True),
        ("liquidity_bucket_schema_version", sa.String(), True),
        ("stale_mark_days_with_open_positions", sa.Integer(), True),
        ("stale_risk_share", sa.Float(), True),
        ("monitor_profile_id", sa.String(), True),
        ("monitor_observation_status", sa.String(), True),
    ]
    for column_name, column_type, nullable in new_columns:
        if not _has_column("research_runs", column_name):
            op.add_column(
                "research_runs",
                sa.Column(column_name, column_type, nullable=nullable),
            )

    _create_index_if_missing(
        "ix_research_runs_monitor_profile_id",
        "research_runs",
        ["monitor_profile_id"],
    )

    if not _has_table("research_run_liquidity_coverages"):
        op.create_table(
            "research_run_liquidity_coverages",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("run_id", sa.String(), nullable=False),
            sa.Column("bucket_key", sa.String(), nullable=False),
            sa.Column("bucket_label", sa.String(), nullable=False),
            sa.Column(
                "full_universe_count", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "execution_universe_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "full_universe_ratio", sa.Float(), nullable=False, server_default="0"
            ),
            sa.Column(
                "execution_coverage_ratio",
                sa.Float(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["run_id"],
                ["research_runs.run_id"],
                name="fk_research_run_liquidity_coverages_run",
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "run_id",
                "bucket_key",
                name="uq_research_run_liquidity_coverages_run_bucket",
            ),
        )
    _create_index_if_missing(
        "ix_research_run_liquidity_coverages_created_at",
        "research_run_liquidity_coverages",
        ["created_at"],
    )
    _create_index_if_missing(
        "ix_research_run_liquidity_coverages_run_id",
        "research_run_liquidity_coverages",
        ["run_id"],
    )

    if not _has_table("microstructure_observations"):
        op.create_table(
            "microstructure_observations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("run_id", sa.String(), nullable=False),
            sa.Column("monitor_profile_id", sa.String(), nullable=False),
            sa.Column("market", sa.String(), nullable=False),
            sa.Column("trading_date", sa.Date(), nullable=False),
            sa.Column(
                "full_universe_count", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "execution_universe_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "execution_universe_ratio",
                sa.Float(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "stale_mark_with_open_positions",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column("liquidity_bucket_schema_version", sa.String(), nullable=False),
            sa.Column(
                "bucket_coverages_json",
                sa.Text(),
                nullable=False,
                server_default="[]",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["run_id"],
                ["research_runs.run_id"],
                name="fk_microstructure_observations_run",
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "monitor_profile_id",
                "market",
                "trading_date",
                name="uq_microstructure_observations_profile_market_date",
            ),
        )
    _create_index_if_missing(
        "ix_microstructure_observations_created_at",
        "microstructure_observations",
        ["created_at"],
    )
    _create_index_if_missing(
        "ix_microstructure_observations_market",
        "microstructure_observations",
        ["market"],
    )
    _create_index_if_missing(
        "ix_microstructure_observations_monitor_profile_id",
        "microstructure_observations",
        ["monitor_profile_id"],
    )
    _create_index_if_missing(
        "ix_microstructure_observations_run_id",
        "microstructure_observations",
        ["run_id"],
    )
    _create_index_if_missing(
        "ix_microstructure_observations_trading_date",
        "microstructure_observations",
        ["trading_date"],
    )


def downgrade() -> None:
    _drop_index_if_exists(
        "ix_microstructure_observations_trading_date", "microstructure_observations"
    )
    _drop_index_if_exists(
        "ix_microstructure_observations_run_id", "microstructure_observations"
    )
    _drop_index_if_exists(
        "ix_microstructure_observations_monitor_profile_id",
        "microstructure_observations",
    )
    _drop_index_if_exists(
        "ix_microstructure_observations_market", "microstructure_observations"
    )
    _drop_index_if_exists(
        "ix_microstructure_observations_created_at", "microstructure_observations"
    )
    if _has_table("microstructure_observations"):
        op.drop_table("microstructure_observations")

    _drop_index_if_exists(
        "ix_research_run_liquidity_coverages_run_id",
        "research_run_liquidity_coverages",
    )
    _drop_index_if_exists(
        "ix_research_run_liquidity_coverages_created_at",
        "research_run_liquidity_coverages",
    )
    if _has_table("research_run_liquidity_coverages"):
        op.drop_table("research_run_liquidity_coverages")

    _drop_index_if_exists("ix_research_runs_monitor_profile_id", "research_runs")
    for column_name in [
        "monitor_observation_status",
        "monitor_profile_id",
        "stale_risk_share",
        "stale_mark_days_with_open_positions",
        "liquidity_bucket_schema_version",
        "execution_universe_ratio",
        "execution_universe_count",
        "full_universe_count",
        "corporate_event_state",
        "missing_feature_policy_state",
        "tradability_contract_version",
        "tradability_state",
        "execution_cost_model_version",
        "missing_feature_policy_version",
        "adv_basis_version",
        "capacity_screening_version",
        "capacity_screening_active",
        "investability_screening_active",
    ]:
        if _has_column("research_runs", column_name):
            op.drop_column("research_runs", column_name)
