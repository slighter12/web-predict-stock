"""adaptive schema

Revision ID: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

metadata = sa.MetaData()
_existing_table_names = {"research_runs"}

sa.Table(
    "research_runs",
    metadata,
    sa.Column("run_id", sa.String(), primary_key=True),
)

adaptive_profiles = sa.Table(
    "adaptive_profiles",
    metadata,
    sa.Column("id", sa.String(), primary_key=True),
    sa.Column("market", sa.String(), nullable=False),
    sa.Column("reward_definition_version", sa.String(), nullable=False),
    sa.Column("state_definition_version", sa.String(), nullable=False),
    sa.Column("notes", sa.Text(), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_adaptive_profiles_created_at", "created_at"),
    sa.Index("ix_adaptive_profiles_market", "market"),
)

adaptive_rollout_controls = sa.Table(
    "adaptive_rollout_controls",
    metadata,
    sa.Column("id", sa.String(), primary_key=True),
    sa.Column(
        "profile_id",
        sa.String(),
        sa.ForeignKey("adaptive_profiles.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("rollout_control_version", sa.String(), nullable=False),
    sa.Column("mode", sa.String(), nullable=False),
    sa.Column("detail_json", sa.Text(), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_adaptive_rollout_controls_created_at", "created_at"),
    sa.Index("ix_adaptive_rollout_controls_profile_id", "profile_id"),
)

adaptive_training_runs = sa.Table(
    "adaptive_training_runs",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column(
        "profile_id",
        sa.String(),
        sa.ForeignKey("adaptive_profiles.id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column(
        "run_id",
        sa.String(),
        sa.ForeignKey("research_runs.run_id", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column("market", sa.String(), nullable=False),
    sa.Column("adaptive_mode", sa.String(), nullable=False),
    sa.Column("reward_definition_version", sa.String(), nullable=False),
    sa.Column("state_definition_version", sa.String(), nullable=False),
    sa.Column("rollout_control_version", sa.String(), nullable=False),
    sa.Column("status", sa.String(), nullable=False),
    sa.Column("dataset_summary_json", sa.Text(), nullable=False),
    sa.Column("artifact_registry_json", sa.Text(), nullable=False),
    sa.Column("validation_error", sa.Text(), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_adaptive_training_runs_adaptive_mode", "adaptive_mode"),
    sa.Index("ix_adaptive_training_runs_created_at", "created_at"),
    sa.Index("ix_adaptive_training_runs_market", "market"),
    sa.Index("ix_adaptive_training_runs_profile_id", "profile_id"),
    sa.Index("ix_adaptive_training_runs_run_id", "run_id"),
    sa.Index("ix_adaptive_training_runs_status", "status"),
)

adaptive_surface_exclusions = sa.Table(
    "adaptive_surface_exclusions",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column(
        "run_id",
        sa.String(),
        sa.ForeignKey("research_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    ),
    sa.Column("exclusion_surface", sa.String(), nullable=False),
    sa.Column("reason", sa.Text(), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_adaptive_surface_exclusions_created_at", "created_at"),
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
