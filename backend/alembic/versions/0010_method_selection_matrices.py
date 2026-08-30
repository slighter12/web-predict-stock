"""nested method selection matrices

Revision ID: 0010
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

metadata = sa.MetaData()

method_selection_matrices = sa.Table(
    "method_selection_matrices",
    metadata,
    sa.Column("matrix_id", sa.String(), primary_key=True),
    sa.Column("request_id", sa.String(), nullable=False),
    sa.Column("status", sa.String(), nullable=False),
    sa.Column("request_payload_json", sa.Text(), nullable=False),
    sa.Column("result_payload_json", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
    sa.Index("ix_method_selection_matrices_created_at", "created_at"),
    sa.Index("ix_method_selection_matrices_request_id", "request_id"),
    sa.Index("ix_method_selection_matrices_status", "status"),
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in metadata.sorted_tables:
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Matrix records are additive research evidence and remain on rollback.
    pass
