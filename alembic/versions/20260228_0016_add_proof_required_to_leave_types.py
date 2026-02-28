"""add proof_required column to leave types

Revision ID: 20260228_0016
Revises: 20260228_0015
Create Date: 2026-02-28 15:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260228_0016"
down_revision: str | None = "20260228_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "leave_types",
        sa.Column("proof_required", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("leave_types", "proof_required")
