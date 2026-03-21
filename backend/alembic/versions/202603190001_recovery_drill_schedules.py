"""add recovery drill schedules and trigger metadata

Revision ID: 202603190001
Revises: 202603180001
"""

import sqlalchemy as sa
from alembic import op

revision = "202603190001"
down_revision = "202603180001"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    columns = sa.inspect(op.get_bind()).get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    indexes = sa.inspect(op.get_bind()).get_indexes(table_name)
    return any(index["name"] == index_name for index in indexes)


def _has_unique_constraint(table_name: str, constraint_name: str) -> bool:
    if not _has_table(table_name):
        return False
    constraints = sa.inspect(op.get_bind()).get_unique_constraints(table_name)
    return any(constraint["name"] == constraint_name for constraint in constraints)


def _has_foreign_key(table_name: str, constraint_name: str) -> bool:
    if not _has_table(table_name):
        return False
    foreign_keys = sa.inspect(op.get_bind()).get_foreign_keys(table_name)
    return any(foreign_key["name"] == constraint_name for foreign_key in foreign_keys)


def _create_index_if_missing(
    index_name: str, table_name: str, columns: list[str]
) -> None:
    if not _has_table(table_name):
        return
    if not all(_has_column(table_name, column_name) for column_name in columns):
        return
    if not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def _drop_index_if_exists(index_name: str, table_name: str) -> None:
    if _has_index(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def _assert_no_null_recovery_drill_raw_payload_ids() -> None:
    if not _has_table("recovery_drills") or not _has_column(
        "recovery_drills", "raw_payload_id"
    ):
        return
    null_count = (
        op.get_bind()
        .execute(
            sa.text("SELECT COUNT(*) FROM recovery_drills WHERE raw_payload_id IS NULL")
        )
        .scalar()
    )
    if int(null_count or 0) > 0:
        raise RuntimeError(
            "Cannot downgrade 202603190001: recovery_drills.raw_payload_id contains NULL values."
        )


def upgrade() -> None:
    if not _has_table("recovery_drill_schedules"):
        op.create_table(
            "recovery_drill_schedules",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("market", sa.String(), nullable=False),
            sa.Column("symbol", sa.String(), nullable=True),
            sa.Column("cadence", sa.String(), nullable=False),
            sa.Column("day_of_month", sa.Integer(), nullable=False),
            sa.Column("timezone", sa.String(), nullable=False),
            sa.Column("benchmark_profile_id", sa.String(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
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
        )
    _create_index_if_missing(
        "ix_recovery_drill_schedules_created_at",
        "recovery_drill_schedules",
        ["created_at"],
    )
    _create_index_if_missing(
        "ix_recovery_drill_schedules_is_active",
        "recovery_drill_schedules",
        ["is_active"],
    )
    _create_index_if_missing(
        "ix_recovery_drill_schedules_market",
        "recovery_drill_schedules",
        ["market"],
    )
    _create_index_if_missing(
        "ix_recovery_drill_schedules_symbol",
        "recovery_drill_schedules",
        ["symbol"],
    )

    if _has_table("recovery_drills"):
        if not _has_column("recovery_drills", "trigger_mode"):
            op.add_column(
                "recovery_drills",
                sa.Column(
                    "trigger_mode", sa.String(), nullable=True, server_default="manual"
                ),
            )
        if not _has_column("recovery_drills", "schedule_id"):
            op.add_column(
                "recovery_drills", sa.Column("schedule_id", sa.Integer(), nullable=True)
            )
        if not _has_column("recovery_drills", "scheduled_for_date"):
            op.add_column(
                "recovery_drills",
                sa.Column("scheduled_for_date", sa.Date(), nullable=True),
            )
        op.execute(
            sa.text(
                "UPDATE recovery_drills SET trigger_mode = 'manual' WHERE trigger_mode IS NULL"
            )
        )
        op.alter_column(
            "recovery_drills",
            "raw_payload_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
        op.alter_column(
            "recovery_drills",
            "trigger_mode",
            existing_type=sa.String(),
            nullable=False,
            server_default=None,
        )
        _create_index_if_missing(
            "ix_recovery_drills_schedule_id", "recovery_drills", ["schedule_id"]
        )
        _create_index_if_missing(
            "ix_recovery_drills_scheduled_for_date",
            "recovery_drills",
            ["scheduled_for_date"],
        )
        _create_index_if_missing(
            "ix_recovery_drills_trigger_mode", "recovery_drills", ["trigger_mode"]
        )
        if not _has_unique_constraint(
            "recovery_drills", "uq_recovery_drill_schedule_slot"
        ):
            op.create_unique_constraint(
                "uq_recovery_drill_schedule_slot",
                "recovery_drills",
                ["schedule_id", "scheduled_for_date"],
            )
        if not _has_foreign_key(
            "recovery_drills",
            "fk_recovery_drills_schedule_id__recovery_drill_schedules",
        ):
            op.create_foreign_key(
                "fk_recovery_drills_schedule_id__recovery_drill_schedules",
                "recovery_drills",
                "recovery_drill_schedules",
                ["schedule_id"],
                ["id"],
                ondelete="RESTRICT",
            )


def downgrade() -> None:
    if _has_table("recovery_drills"):
        if _has_foreign_key(
            "recovery_drills",
            "fk_recovery_drills_schedule_id__recovery_drill_schedules",
        ):
            op.drop_constraint(
                "fk_recovery_drills_schedule_id__recovery_drill_schedules",
                "recovery_drills",
                type_="foreignkey",
            )
        if _has_unique_constraint("recovery_drills", "uq_recovery_drill_schedule_slot"):
            op.drop_constraint(
                "uq_recovery_drill_schedule_slot",
                "recovery_drills",
                type_="unique",
            )
        _drop_index_if_exists("ix_recovery_drills_trigger_mode", "recovery_drills")
        _drop_index_if_exists(
            "ix_recovery_drills_scheduled_for_date", "recovery_drills"
        )
        _drop_index_if_exists("ix_recovery_drills_schedule_id", "recovery_drills")
        if _has_column("recovery_drills", "scheduled_for_date"):
            op.drop_column("recovery_drills", "scheduled_for_date")
        if _has_column("recovery_drills", "schedule_id"):
            op.drop_column("recovery_drills", "schedule_id")
        if _has_column("recovery_drills", "trigger_mode"):
            op.drop_column("recovery_drills", "trigger_mode")
        _assert_no_null_recovery_drill_raw_payload_ids()
        op.alter_column(
            "recovery_drills",
            "raw_payload_id",
            existing_type=sa.Integer(),
            nullable=False,
        )

    _drop_index_if_exists(
        "ix_recovery_drill_schedules_symbol", "recovery_drill_schedules"
    )
    _drop_index_if_exists(
        "ix_recovery_drill_schedules_market", "recovery_drill_schedules"
    )
    _drop_index_if_exists(
        "ix_recovery_drill_schedules_is_active", "recovery_drill_schedules"
    )
    _drop_index_if_exists(
        "ix_recovery_drill_schedules_created_at", "recovery_drill_schedules"
    )
    if _has_table("recovery_drill_schedules"):
        op.drop_table("recovery_drill_schedules")
