"""add dynamic base_type dependency for salary structure components

Revision ID: 20260311_0027
Revises: 20260310_0026
Create Date: 2026-03-11 11:15:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260311_0027"
down_revision: str | None = "20260310_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


base_type_enum = sa.Enum(
    "GROSS",
    "COMPONENT",
    name="salary_component_base_type_enum",
    native_enum=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("salary_structure_components"):
        return

    columns = {column["name"] for column in inspector.get_columns("salary_structure_components")}

    if "base_type" not in columns:
        op.add_column(
            "salary_structure_components",
            sa.Column("base_type", base_type_enum, nullable=True, server_default=sa.text("'GROSS'")),
        )

    if "base_component_id" not in columns:
        op.add_column(
            "salary_structure_components",
            sa.Column("base_component_id", sa.Integer(), nullable=True),
        )
        op.create_index(
            "ix_salary_structure_components_base_component_id",
            "salary_structure_components",
            ["base_component_id"],
            unique=False,
        )
        op.create_foreign_key(
            "fk_salary_structure_components_base_component_id_salary_components",
            "salary_structure_components",
            "salary_components",
            ["base_component_id"],
            ["id"],
        )

    # Backfill from legacy calculation_base field when present.
    if "calculation_base" in columns:
        op.execute("UPDATE salary_structure_components SET base_type = 'GROSS' WHERE base_type IS NULL")
        op.execute(
            "UPDATE salary_structure_components "
            "SET base_type = 'COMPONENT', "
            "base_component_id = ("
            " SELECT basic_map.component_id FROM ("
            "   SELECT s2.salary_structure_id, s2.component_id"
            "   FROM salary_structure_components s2"
            "   JOIN salary_components c2 ON c2.id = s2.component_id"
            "   WHERE LOWER(c2.name) = 'basic'"
            " ) AS basic_map"
            " WHERE basic_map.salary_structure_id = salary_structure_components.salary_structure_id"
            " LIMIT 1"
            ") "
            "WHERE calculation_base = 'BASIC'"
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("salary_structure_components"):
        return

    columns = {column["name"] for column in inspector.get_columns("salary_structure_components")}

    if "base_component_id" in columns:
        op.drop_constraint(
            "fk_salary_structure_components_base_component_id_salary_components",
            "salary_structure_components",
            type_="foreignkey",
        )
        op.drop_index("ix_salary_structure_components_base_component_id", table_name="salary_structure_components")
        op.drop_column("salary_structure_components", "base_component_id")

    if "base_type" in columns:
        op.drop_column("salary_structure_components", "base_type")
