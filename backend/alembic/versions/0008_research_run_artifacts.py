"""research run artifacts

Revision ID: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("research_runs") as batch_op:
        batch_op.add_column(sa.Column("equity_curve_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("signals_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("model_diagnostics_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("baselines_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("research_runs") as batch_op:
        batch_op.drop_column("baselines_json")
        batch_op.drop_column("model_diagnostics_json")
        batch_op.drop_column("signals_json")
        batch_op.drop_column("equity_curve_json")
