"""switch salary module to manual component amounts

Revision ID: 20260312_0029
Revises: 20260311_0028
Create Date: 2026-03-12 11:40:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260312_0029"
down_revision: str | None = "20260311_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("employee_salaries"):
        columns = {column["name"] for column in inspector.get_columns("employee_salaries")}
        if "salary_structure_id" in columns:
            op.alter_column(
                "employee_salaries",
                "salary_structure_id",
                existing_type=sa.Integer(),
                nullable=True,
            )
        if "annual_ctc" in columns:
            op.alter_column(
                "employee_salaries",
                "annual_ctc",
                existing_type=sa.Numeric(12, 2),
                nullable=True,
            )

    if not inspector.has_table("employee_salary_components"):
        op.create_table(
            "employee_salary_components",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("employee_salary_id", sa.Integer(), nullable=False),
            sa.Column("component_id", sa.Integer(), nullable=False),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(["employee_salary_id"], ["employee_salaries.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["component_id"], ["salary_components.id"]),
            sa.UniqueConstraint(
                "employee_salary_id",
                "component_id",
                name="uq_employee_salary_components_salary_component",
            ),
        )
        op.execute(
            "ALTER TABLE employee_salary_components MODIFY updated_at TIMESTAMP NOT NULL "
            "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
        )
        op.create_index("ix_employee_salary_components_id", "employee_salary_components", ["id"], unique=False)
        op.create_index(
            "ix_employee_salary_components_employee_salary_id",
            "employee_salary_components",
            ["employee_salary_id"],
            unique=False,
        )
        op.create_index(
            "ix_employee_salary_components_component_id",
            "employee_salary_components",
            ["component_id"],
            unique=False,
        )

    if inspector.has_table("salary_structure_components"):
        columns = {column["name"] for column in inspector.get_columns("salary_structure_components")}

        if "base_component_id" in columns:
            fk_names = {fk.get("name") for fk in inspector.get_foreign_keys("salary_structure_components")}
            fk_name = "fk_salary_structure_components_base_component_id_salary_components"
            if fk_name in fk_names:
                op.drop_constraint(fk_name, "salary_structure_components", type_="foreignkey")

            index_names = {index["name"] for index in inspector.get_indexes("salary_structure_components")}
            if "ix_salary_structure_components_base_component_id" in index_names:
                op.drop_index("ix_salary_structure_components_base_component_id", table_name="salary_structure_components")

            op.drop_column("salary_structure_components", "base_component_id")

        if "base_type" in columns:
            op.drop_column("salary_structure_components", "base_type")

        if "calculation_base" in columns:
            op.drop_column("salary_structure_components", "calculation_base")

        if "fixed_amount" in columns:
            op.drop_column("salary_structure_components", "fixed_amount")

        if "percentage" in columns:
            op.drop_column("salary_structure_components", "percentage")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("salary_structure_components"):
        columns = {column["name"] for column in inspector.get_columns("salary_structure_components")}

        if "percentage" not in columns:
            op.add_column("salary_structure_components", sa.Column("percentage", sa.Numeric(7, 2), nullable=True))

        if "fixed_amount" not in columns:
            op.add_column("salary_structure_components", sa.Column("fixed_amount", sa.Numeric(12, 2), nullable=True))

        if "calculation_base" not in columns:
            op.add_column(
                "salary_structure_components",
                sa.Column(
                    "calculation_base",
                    sa.Enum("GROSS", "BASIC", name="salary_calculation_base_enum", native_enum=False),
                    nullable=False,
                    server_default=sa.text("'GROSS'"),
                ),
            )

        if "base_type" not in columns:
            op.add_column(
                "salary_structure_components",
                sa.Column(
                    "base_type",
                    sa.Enum("GROSS", "COMPONENT", name="salary_component_base_type_enum", native_enum=False),
                    nullable=True,
                ),
            )

        if "base_component_id" not in columns:
            op.add_column("salary_structure_components", sa.Column("base_component_id", sa.Integer(), nullable=True))
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

    if inspector.has_table("employee_salary_components"):
        op.drop_index("ix_employee_salary_components_component_id", table_name="employee_salary_components")
        op.drop_index("ix_employee_salary_components_employee_salary_id", table_name="employee_salary_components")
        op.drop_index("ix_employee_salary_components_id", table_name="employee_salary_components")
        op.drop_table("employee_salary_components")

    if inspector.has_table("employee_salaries"):
        columns = {column["name"] for column in inspector.get_columns("employee_salaries")}
        if "annual_ctc" in columns:
            op.alter_column(
                "employee_salaries",
                "annual_ctc",
                existing_type=sa.Numeric(12, 2),
                nullable=False,
            )
        if "salary_structure_id" in columns:
            op.alter_column(
                "employee_salaries",
                "salary_structure_id",
                existing_type=sa.Integer(),
                nullable=False,
            )
