"""pooled calibration matrices

Revision ID: 0009
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

metadata = sa.MetaData()

calibration_matrices = sa.Table(
    "calibration_matrices",
    metadata,
    sa.Column("matrix_id", sa.String(), primary_key=True),
    sa.Column("request_id", sa.String(), nullable=False),
    sa.Column("status", sa.String(), nullable=False),
    sa.Column("request_payload_json", sa.Text(), nullable=False),
    sa.Column("result_payload_json", sa.Text(), nullable=False),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=True,
        server_default=sa.func.now(),
    ),
    sa.Index("ix_calibration_matrices_created_at", "created_at"),
    sa.Index("ix_calibration_matrices_request_id", "request_id"),
    sa.Index("ix_calibration_matrices_status", "status"),
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in metadata.sorted_tables:
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Calibration Matrices are additive research evidence. Keep the table and
    # its records when the application revision is rolled back; deleting
    # evidence requires an explicit retention operation and backup review.
    pass
