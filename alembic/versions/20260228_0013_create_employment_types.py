"""create employment types table

Revision ID: 20260228_0013
Revises: 20260226_0012
Create Date: 2026-02-28 13:10:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260228_0013"
down_revision: str | None = "20260226_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


employment_types_table = sa.table(
    "employment_types",
    sa.column("name", sa.String(length=100)),
)


def upgrade() -> None:
    op.create_table(
        "employment_types",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_employment_types_id", "employment_types", ["id"], unique=False)
    op.create_index("uq_employment_types_name", "employment_types", ["name"], unique=True)
    op.bulk_insert(
        employment_types_table,
        [
            {"name": "Full Time"},
            {"name": "Trainee"},
        ],
    )


def downgrade() -> None:
    op.drop_index("uq_employment_types_name", table_name="employment_types")
    op.drop_index("ix_employment_types_id", table_name="employment_types")
    op.drop_table("employment_types")
