"""add users employment_type fk

Revision ID: 20260228_0019
Revises: 20260228_0018
Create Date: 2026-02-28 17:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260228_0019"
down_revision: str | None = "20260228_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("employment_type_id", sa.Integer(), nullable=True))
    op.create_index("ix_users_employment_type_id", "users", ["employment_type_id"], unique=False)
    op.create_foreign_key(
        "fk_users_employment_type_id_employment_types",
        "users",
        "employment_types",
        ["employment_type_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_employment_type_id_employment_types", "users", type_="foreignkey")
    op.drop_index("ix_users_employment_type_id", table_name="users")
    op.drop_column("users", "employment_type_id")
