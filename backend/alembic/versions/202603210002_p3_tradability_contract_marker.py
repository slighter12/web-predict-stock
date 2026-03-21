"""add p3 tradability contract marker

Revision ID: 202603210002
Revises: 202603210001
"""

import sqlalchemy as sa
from alembic import op

revision = "202603210002"
down_revision = "202603210001"
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


def upgrade() -> None:
    # Compatibility backfill for environments that had already applied an
    # earlier 202603210001 variant before the marker column was folded into it.
    if not _has_column("research_runs", "tradability_contract_version"):
        op.add_column(
            "research_runs",
            sa.Column("tradability_contract_version", sa.String(), nullable=True),
        )


def downgrade() -> None:
    if _has_column("research_runs", "tradability_contract_version"):
        op.drop_column("research_runs", "tradability_contract_version")
