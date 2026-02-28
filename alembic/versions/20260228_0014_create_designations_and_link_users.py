"""create designations and link users

Revision ID: 20260228_0014
Revises: 20260228_0013
Create Date: 2026-02-28 14:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260228_0014"
down_revision: str | None = "20260228_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "designations",
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
        "ALTER TABLE designations MODIFY updated_at TIMESTAMP NOT NULL "
        "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
    )
    op.create_index("ix_designations_id", "designations", ["id"], unique=False)
    op.create_index("uq_designations_name", "designations", ["name"], unique=True)

    op.add_column("users", sa.Column("designation_id", sa.Integer(), nullable=True))
    op.create_index("ix_users_designation_id", "users", ["designation_id"], unique=False)
    op.create_foreign_key(
        "fk_users_designation_id_designations",
        "users",
        "designations",
        ["designation_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_designation_id_designations", "users", type_="foreignkey")
    op.drop_index("ix_users_designation_id", table_name="users")
    op.drop_column("users", "designation_id")

    op.drop_index("uq_designations_name", table_name="designations")
    op.drop_index("ix_designations_id", table_name="designations")
    op.drop_table("designations")
