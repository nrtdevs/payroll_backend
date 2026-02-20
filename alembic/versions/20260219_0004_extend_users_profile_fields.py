"""extend users table with profile fields

Revision ID: 20260219_0004
Revises: 20260219_0003
Create Date: 2026-02-19 13:20:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260219_0004"
down_revision: str | None = "20260219_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("name", sa.String(length=150), nullable=True))
    op.add_column("users", sa.Column("branch_id", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("role_id", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("salary_type", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("salary", sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column("users", sa.Column("leave_balance", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("status", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("current_address", sa.String(length=500), nullable=True))
    op.add_column("users", sa.Column("home_address", sa.String(length=500), nullable=True))
    op.add_column("users", sa.Column("pan", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("aadhaar", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("mobile", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("number", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("father_name", sa.String(length=150), nullable=True))
    op.add_column("users", sa.Column("mother_name", sa.String(length=150), nullable=True))

    op.create_foreign_key("fk_users_branch_id", "users", "branches", ["branch_id"], ["id"])
    op.create_foreign_key("fk_users_role_id", "users", "roles", ["role_id"], ["id"])

    op.create_index("ix_users_branch_id", "users", ["branch_id"], unique=False)
    op.create_index("ix_users_role_id", "users", ["role_id"], unique=False)
    op.create_index("ix_users_pan", "users", ["pan"], unique=True)
    op.create_index("ix_users_aadhaar", "users", ["aadhaar"], unique=True)
    op.create_index("ix_users_mobile", "users", ["mobile"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_mobile", table_name="users")
    op.drop_index("ix_users_aadhaar", table_name="users")
    op.drop_index("ix_users_pan", table_name="users")
    op.drop_index("ix_users_role_id", table_name="users")
    op.drop_index("ix_users_branch_id", table_name="users")

    op.drop_constraint("fk_users_role_id", "users", type_="foreignkey")
    op.drop_constraint("fk_users_branch_id", "users", type_="foreignkey")

    op.drop_column("users", "mother_name")
    op.drop_column("users", "father_name")
    op.drop_column("users", "number")
    op.drop_column("users", "mobile")
    op.drop_column("users", "aadhaar")
    op.drop_column("users", "pan")
    op.drop_column("users", "home_address")
    op.drop_column("users", "current_address")
    op.drop_column("users", "status")
    op.drop_column("users", "leave_balance")
    op.drop_column("users", "salary")
    op.drop_column("users", "salary_type")
    op.drop_column("users", "role_id")
    op.drop_column("users", "branch_id")
    op.drop_column("users", "name")
