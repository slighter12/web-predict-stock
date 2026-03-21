"""add p4-p6 governance and tw company foundations

Revision ID: 202603210003
Revises: 202603210002
"""

import sqlalchemy as sa
from alembic import op

revision = "202603210003"
down_revision = "202603210002"
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
        ("split_policy_version", sa.String(), True),
        ("bootstrap_policy_version", sa.String(), True),
        ("ic_overlap_policy_version", sa.String(), True),
        ("comparison_review_matrix_version", sa.String(), True),
        ("scheduled_review_cadence", sa.String(), True),
        ("model_family", sa.String(), True),
        ("training_output_contract_version", sa.String(), True),
        ("adoption_comparison_policy_version", sa.String(), True),
    ]
    for column_name, column_type, nullable in research_run_columns:
        if not _has_column("research_runs", column_name):
            op.add_column(
                "research_runs",
                sa.Column(column_name, column_type, nullable=nullable),
            )
    _create_index_if_missing(
        "ix_research_runs_model_family",
        "research_runs",
        ["model_family"],
    )

    tick_archive_columns = [
        ("backup_backend", sa.String(), True),
        ("backup_object_key", sa.String(), True),
        ("backup_status", sa.String(), True),
        ("backup_completed_at", sa.DateTime(timezone=True), True),
        ("backup_error", sa.Text(), True),
    ]
    for column_name, column_type, nullable in tick_archive_columns:
        if not _has_column("tick_archive_objects", column_name):
            op.add_column(
                "tick_archive_objects",
                sa.Column(column_name, column_type, nullable=nullable),
            )
    _create_index_if_missing(
        "ix_tick_archive_objects_backup_status",
        "tick_archive_objects",
        ["backup_status"],
    )

    if not _has_table("tw_company_profiles"):
        op.create_table(
            "tw_company_profiles",
            sa.Column("id", sa.Integer(), nullable=False),
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
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "symbol",
                "exchange",
                name="uq_tw_company_profiles_symbol_exchange",
            ),
        )
    _create_index_if_missing(
        "ix_tw_company_profiles_symbol",
        "tw_company_profiles",
        ["symbol"],
    )
    _create_index_if_missing(
        "ix_tw_company_profiles_market",
        "tw_company_profiles",
        ["market"],
    )
    _create_index_if_missing(
        "ix_tw_company_profiles_exchange",
        "tw_company_profiles",
        ["exchange"],
    )
    _create_index_if_missing(
        "ix_tw_company_profiles_board",
        "tw_company_profiles",
        ["board"],
    )
    _create_index_if_missing(
        "ix_tw_company_profiles_industry_category",
        "tw_company_profiles",
        ["industry_category"],
    )
    _create_index_if_missing(
        "ix_tw_company_profiles_listing_date",
        "tw_company_profiles",
        ["listing_date"],
    )
    _create_index_if_missing(
        "ix_tw_company_profiles_trading_status",
        "tw_company_profiles",
        ["trading_status"],
    )
    _create_index_if_missing(
        "ix_tw_company_profiles_raw_payload_id",
        "tw_company_profiles",
        ["raw_payload_id"],
    )
    _create_index_if_missing(
        "ix_tw_company_profiles_created_at",
        "tw_company_profiles",
        ["created_at"],
    )
    _create_index_if_missing(
        "ix_tw_company_profiles_updated_at",
        "tw_company_profiles",
        ["updated_at"],
    )


def downgrade() -> None:
    _drop_index_if_exists(
        "ix_tw_company_profiles_updated_at",
        "tw_company_profiles",
    )
    _drop_index_if_exists(
        "ix_tw_company_profiles_created_at",
        "tw_company_profiles",
    )
    _drop_index_if_exists(
        "ix_tw_company_profiles_raw_payload_id",
        "tw_company_profiles",
    )
    _drop_index_if_exists(
        "ix_tw_company_profiles_trading_status",
        "tw_company_profiles",
    )
    _drop_index_if_exists(
        "ix_tw_company_profiles_listing_date",
        "tw_company_profiles",
    )
    _drop_index_if_exists(
        "ix_tw_company_profiles_industry_category",
        "tw_company_profiles",
    )
    _drop_index_if_exists(
        "ix_tw_company_profiles_board",
        "tw_company_profiles",
    )
    _drop_index_if_exists(
        "ix_tw_company_profiles_exchange",
        "tw_company_profiles",
    )
    _drop_index_if_exists(
        "ix_tw_company_profiles_market",
        "tw_company_profiles",
    )
    _drop_index_if_exists(
        "ix_tw_company_profiles_symbol",
        "tw_company_profiles",
    )
    if _has_table("tw_company_profiles"):
        op.drop_table("tw_company_profiles")

    _drop_index_if_exists(
        "ix_tick_archive_objects_backup_status",
        "tick_archive_objects",
    )
    for column_name in (
        "backup_error",
        "backup_completed_at",
        "backup_status",
        "backup_object_key",
        "backup_backend",
    ):
        if _has_column("tick_archive_objects", column_name):
            op.drop_column("tick_archive_objects", column_name)

    _drop_index_if_exists(
        "ix_research_runs_model_family",
        "research_runs",
    )
    for column_name in (
        "adoption_comparison_policy_version",
        "training_output_contract_version",
        "model_family",
        "scheduled_review_cadence",
        "comparison_review_matrix_version",
        "ic_overlap_policy_version",
        "bootstrap_policy_version",
        "split_policy_version",
    ):
        if _has_column("research_runs", column_name):
            op.drop_column("research_runs", column_name)
