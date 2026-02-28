"""create leave masters table

Revision ID: 20260228_0017
Revises: 20260228_0016
Create Date: 2026-02-28 15:35:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260228_0017"
down_revision: str | None = "20260228_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "leave_masters",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("employment_type_id", sa.Integer(), nullable=False),
        sa.Column("leave_type_id", sa.Integer(), nullable=False),
        sa.Column("total_leave_days", sa.Integer(), nullable=False, server_default="0"),
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
        sa.ForeignKeyConstraint(["employment_type_id"], ["employment_types.id"]),
        sa.ForeignKeyConstraint(["leave_type_id"], ["leave_types.id"]),
    )
    op.execute(
        "ALTER TABLE leave_masters MODIFY updated_at TIMESTAMP NOT NULL "
        "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
    )
    op.create_index("ix_leave_masters_id", "leave_masters", ["id"], unique=False)
    op.create_index("ix_leave_masters_employment_type_id", "leave_masters", ["employment_type_id"], unique=False)
    op.create_index("ix_leave_masters_leave_type_id", "leave_masters", ["leave_type_id"], unique=False)
    op.create_index(
        "uq_leave_masters_employment_leave_type",
        "leave_masters",
        ["employment_type_id", "leave_type_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_leave_masters_employment_leave_type", table_name="leave_masters")
    op.drop_index("ix_leave_masters_leave_type_id", table_name="leave_masters")
    op.drop_index("ix_leave_masters_employment_type_id", table_name="leave_masters")
    op.drop_index("ix_leave_masters_id", table_name="leave_masters")
    op.drop_table("leave_masters")
