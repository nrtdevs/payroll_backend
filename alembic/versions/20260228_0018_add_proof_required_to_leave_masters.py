"""add proof_required to leave masters

Revision ID: 20260228_0018
Revises: 20260228_0017
Create Date: 2026-02-28 16:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260228_0018"
down_revision: str | None = "20260228_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "leave_masters",
        sa.Column("proof_required", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        "UPDATE leave_masters lm "
        "JOIN leave_types lt ON lt.id = lm.leave_type_id "
        "SET lm.proof_required = lt.proof_required"
    )


def downgrade() -> None:
    op.drop_column("leave_masters", "proof_required")
