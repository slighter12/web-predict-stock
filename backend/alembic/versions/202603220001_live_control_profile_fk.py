"""add live control profiles and fk

Revision ID: 202603220001
Revises: 202603210004
"""

import sqlalchemy as sa
from alembic import op

revision = "202603220001"
down_revision = "202603210004"
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


def _has_foreign_key(table_name: str, fk_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(
        fk["name"] == fk_name
        for fk in sa.inspect(op.get_bind()).get_foreign_keys(table_name)
    )


def _create_index_if_missing(
    index_name: str, table_name: str, columns: list[str]
) -> None:
    if _has_table(table_name) and not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    if not _has_table("live_control_profiles"):
        op.create_table(
            "live_control_profiles",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("market", sa.String(), nullable=False),
            sa.Column("live_control_version", sa.String(), nullable=False),
            sa.Column("detail_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_live_control_profiles_market", ["market"]),
        ("ix_live_control_profiles_created_at", ["created_at"]),
    ):
        _create_index_if_missing(index_name, "live_control_profiles", columns)

    if _has_table("execution_orders") and _has_table("live_control_profiles"):
        op.execute(
            sa.text(
                """
                INSERT INTO live_control_profiles (id, market, live_control_version, detail_json)
                SELECT DISTINCT
                    execution_orders.live_control_profile_id,
                    execution_orders.market,
                    'live_stub_controls_v1',
                    '{}'
                FROM execution_orders
                WHERE execution_orders.live_control_profile_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1
                      FROM live_control_profiles
                      WHERE live_control_profiles.id = execution_orders.live_control_profile_id
                  )
                """
            )
        )

    fk_name = "fk_execution_orders_live_control_profile_id"
    if _has_table("execution_orders") and not _has_foreign_key("execution_orders", fk_name):
        op.create_foreign_key(
            fk_name,
            "execution_orders",
            "live_control_profiles",
            ["live_control_profile_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    fk_name = "fk_execution_orders_live_control_profile_id"
    if _has_foreign_key("execution_orders", fk_name):
        op.drop_constraint(fk_name, "execution_orders", type_="foreignkey")
    if _has_index("live_control_profiles", "ix_live_control_profiles_created_at"):
        op.drop_index(
            "ix_live_control_profiles_created_at", table_name="live_control_profiles"
        )
    if _has_index("live_control_profiles", "ix_live_control_profiles_market"):
        op.drop_index(
            "ix_live_control_profiles_market", table_name="live_control_profiles"
        )
    if _has_table("live_control_profiles"):
        op.drop_table("live_control_profiles")
