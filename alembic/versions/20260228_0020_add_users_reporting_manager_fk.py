"""add users reporting_manager fk

Revision ID: 20260228_0020
Revises: 20260228_0019
Create Date: 2026-02-28 17:20:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260228_0020"
down_revision: str | None = "20260228_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("reporting_manager_id", sa.Integer(), nullable=True))
    op.create_index("ix_users_reporting_manager_id", "users", ["reporting_manager_id"], unique=False)
    op.create_foreign_key(
        "fk_users_reporting_manager_id_users",
        "users",
        "users",
        ["reporting_manager_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_reporting_manager_id_users", "users", type_="foreignkey")
    op.drop_index("ix_users_reporting_manager_id", table_name="users")
    op.drop_column("users", "reporting_manager_id")
