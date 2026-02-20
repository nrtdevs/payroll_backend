"""create permissions table

Revision ID: 20260219_0006
Revises: 20260219_0005
Create Date: 2026-02-19 15:10:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260219_0006"
down_revision: str | None = "20260219_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("permission_name", sa.String(length=150), nullable=False),
        sa.Column("group_name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_permissions_id", "permissions", ["id"], unique=False)
    op.create_index("ix_permissions_created_by", "permissions", ["created_by"], unique=False)
    op.create_index(
        "uq_permissions_name_group",
        "permissions",
        ["permission_name", "group_name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_permissions_name_group", table_name="permissions")
    op.drop_index("ix_permissions_created_by", table_name="permissions")
    op.drop_index("ix_permissions_id", table_name="permissions")
    op.drop_table("permissions")
