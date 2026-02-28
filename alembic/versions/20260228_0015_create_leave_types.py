"""create leave types table

Revision ID: 20260228_0015
Revises: 20260228_0014
Create Date: 2026-02-28 14:25:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260228_0015"
down_revision: str | None = "20260228_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "leave_types",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.execute(
        "ALTER TABLE leave_types MODIFY updated_at TIMESTAMP NOT NULL "
        "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
    )
    op.create_index("ix_leave_types_id", "leave_types", ["id"], unique=False)
    op.create_index("uq_leave_types_name", "leave_types", ["name"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_leave_types_name", table_name="leave_types")
    op.drop_index("ix_leave_types_id", table_name="leave_types")
    op.drop_table("leave_types")
