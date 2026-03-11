"""add calculation_base to salary structure components

Revision ID: 20260310_0026
Revises: 20260310_0025
Create Date: 2026-03-10 19:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260310_0026"
down_revision: str | None = "20260310_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


calculation_base_enum = sa.Enum(
    "GROSS",
    "BASIC",
    name="salary_calculation_base_enum",
    native_enum=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("salary_structure_components"):
        return

    columns = {column["name"] for column in inspector.get_columns("salary_structure_components")}
    if "calculation_base" not in columns:
        op.add_column(
            "salary_structure_components",
            sa.Column(
                "calculation_base",
                calculation_base_enum,
                nullable=False,
                server_default=sa.text("'GROSS'"),
            ),
        )

    op.execute(
        "UPDATE salary_structure_components "
        "SET calculation_base = 'BASIC' "
        "WHERE component_id IN (SELECT id FROM salary_components WHERE LOWER(name) = 'pf')"
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("salary_structure_components"):
        return

    columns = {column["name"] for column in inspector.get_columns("salary_structure_components")}
    if "calculation_base" in columns:
        op.drop_column("salary_structure_components", "calculation_base")
