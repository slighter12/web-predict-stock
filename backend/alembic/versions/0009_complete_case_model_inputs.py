"""Align persisted runs with the complete-case model-input policy.

Revision ID: 0009
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

_LEGACY_VERSION = "xgboost_native_missing_v1"
_COMPLETE_CASE_VERSION = "complete_case_model_inputs_v1"
_COMPLETE_CASE_STATE = "complete_case_applied"

_research_runs = sa.table(
    "research_runs",
    sa.column("missing_feature_policy_version", sa.String()),
    sa.column("missing_feature_policy_state", sa.String()),
)


def upgrade() -> None:
    op.execute(
        _research_runs.update()
        .where(_research_runs.c.missing_feature_policy_version == _LEGACY_VERSION)
        .values(
            missing_feature_policy_version=_COMPLETE_CASE_VERSION,
            missing_feature_policy_state=_COMPLETE_CASE_STATE,
        )
    )


def downgrade() -> None:
    raise RuntimeError(
        "Migration 0009 cannot safely restore legacy missing-feature labels: "
        "the upgrade intentionally merges multiple legacy states without "
        "retaining row-level provenance."
    )
