"""create salary module

Revision ID: 20260310_0024
Revises: 20260306_0023
Create Date: 2026-03-10 16:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260310_0024"
down_revision: str | None = "20260306_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


salary_component_type_enum = sa.Enum(
    "EARNING",
    "DEDUCTION",
    name="salary_component_type_enum",
    native_enum=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("salary_components"):
        op.create_table(
            "salary_components",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("type", salary_component_type_enum, nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
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
            sa.UniqueConstraint("name", name="uq_salary_components_name"),
        )
        op.execute(
            "ALTER TABLE salary_components MODIFY updated_at TIMESTAMP NOT NULL "
            "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
        )
        op.create_index("ix_salary_components_id", "salary_components", ["id"], unique=False)

    if not inspector.has_table("salary_structures"):
        op.create_table(
            "salary_structures",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("name", sa.String(length=150), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
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
            sa.UniqueConstraint("name", name="uq_salary_structures_name"),
        )
        op.execute(
            "ALTER TABLE salary_structures MODIFY updated_at TIMESTAMP NOT NULL "
            "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
        )
        op.create_index("ix_salary_structures_id", "salary_structures", ["id"], unique=False)

    if not inspector.has_table("salary_structure_components"):
        op.create_table(
            "salary_structure_components",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("salary_structure_id", sa.Integer(), nullable=False),
            sa.Column("component_id", sa.Integer(), nullable=False),
            sa.Column("percentage", sa.Numeric(7, 2), nullable=True),
            sa.Column("fixed_amount", sa.Numeric(12, 2), nullable=True),
            sa.ForeignKeyConstraint(["salary_structure_id"], ["salary_structures.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["component_id"], ["salary_components.id"]),
            sa.UniqueConstraint(
                "salary_structure_id",
                "component_id",
                name="uq_salary_structure_components_structure_component",
            ),
        )
        op.create_index("ix_salary_structure_components_id", "salary_structure_components", ["id"], unique=False)
        op.create_index(
            "ix_salary_structure_components_salary_structure_id",
            "salary_structure_components",
            ["salary_structure_id"],
            unique=False,
        )
        op.create_index(
            "ix_salary_structure_components_component_id",
            "salary_structure_components",
            ["component_id"],
            unique=False,
        )

    if not inspector.has_table("employee_salaries"):
        op.create_table(
            "employee_salaries",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("employee_id", sa.Integer(), nullable=False),
            sa.Column("salary_structure_id", sa.Integer(), nullable=False),
            sa.Column("annual_ctc", sa.Numeric(12, 2), nullable=False),
            sa.Column("effective_from", sa.Date(), nullable=False),
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
            sa.ForeignKeyConstraint(["employee_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["salary_structure_id"], ["salary_structures.id"]),
            sa.UniqueConstraint(
                "employee_id",
                "effective_from",
                name="uq_employee_salaries_employee_effective_from",
            ),
        )
        op.execute(
            "ALTER TABLE employee_salaries MODIFY updated_at TIMESTAMP NOT NULL "
            "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
        )
        op.create_index("ix_employee_salaries_id", "employee_salaries", ["id"], unique=False)
        op.create_index("ix_employee_salaries_employee_id", "employee_salaries", ["employee_id"], unique=False)
        op.create_index(
            "ix_employee_salaries_salary_structure_id",
            "employee_salaries",
            ["salary_structure_id"],
            unique=False,
        )
        op.create_index("ix_employee_salaries_effective_from", "employee_salaries", ["effective_from"], unique=False)

    if not inspector.has_table("payroll_records"):
        op.create_table(
            "payroll_records",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("employee_id", sa.Integer(), nullable=False),
            sa.Column("salary_assignment_id", sa.Integer(), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("month", sa.Integer(), nullable=False),
            sa.Column("gross_salary", sa.Numeric(12, 2), nullable=False),
            sa.Column("working_days", sa.Integer(), nullable=False),
            sa.Column("present_days", sa.Integer(), nullable=False),
            sa.Column("absent_days", sa.Integer(), nullable=False),
            sa.Column("leave_days", sa.Integer(), nullable=False),
            sa.Column("absent_deduction", sa.Numeric(12, 2), nullable=False),
            sa.Column("total_component_deduction", sa.Numeric(12, 2), nullable=False),
            sa.Column("pf_deduction", sa.Numeric(12, 2), nullable=False),
            sa.Column("net_salary", sa.Numeric(12, 2), nullable=False),
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
            sa.ForeignKeyConstraint(["employee_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["salary_assignment_id"], ["employee_salaries.id"]),
            sa.UniqueConstraint(
                "employee_id",
                "year",
                "month",
                name="uq_payroll_records_employee_year_month",
            ),
        )
        op.execute(
            "ALTER TABLE payroll_records MODIFY updated_at TIMESTAMP NOT NULL "
            "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
        )
        op.create_index("ix_payroll_records_id", "payroll_records", ["id"], unique=False)
        op.create_index("ix_payroll_records_employee_id", "payroll_records", ["employee_id"], unique=False)
        op.create_index(
            "ix_payroll_records_salary_assignment_id",
            "payroll_records",
            ["salary_assignment_id"],
            unique=False,
        )
        op.create_index("ix_payroll_records_year", "payroll_records", ["year"], unique=False)
        op.create_index("ix_payroll_records_month", "payroll_records", ["month"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_payroll_records_month", table_name="payroll_records")
    op.drop_index("ix_payroll_records_year", table_name="payroll_records")
    op.drop_index("ix_payroll_records_salary_assignment_id", table_name="payroll_records")
    op.drop_index("ix_payroll_records_employee_id", table_name="payroll_records")
    op.drop_index("ix_payroll_records_id", table_name="payroll_records")
    op.drop_table("payroll_records")

    op.drop_index("ix_employee_salaries_effective_from", table_name="employee_salaries")
    op.drop_index("ix_employee_salaries_salary_structure_id", table_name="employee_salaries")
    op.drop_index("ix_employee_salaries_employee_id", table_name="employee_salaries")
    op.drop_index("ix_employee_salaries_id", table_name="employee_salaries")
    op.drop_table("employee_salaries")

    op.drop_index("ix_salary_structure_components_component_id", table_name="salary_structure_components")
    op.drop_index("ix_salary_structure_components_salary_structure_id", table_name="salary_structure_components")
    op.drop_index("ix_salary_structure_components_id", table_name="salary_structure_components")
    op.drop_table("salary_structure_components")

    op.drop_index("ix_salary_structures_id", table_name="salary_structures")
    op.drop_table("salary_structures")

    op.drop_index("ix_salary_components_id", table_name="salary_components")
    op.drop_table("salary_components")
