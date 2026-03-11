"""switch employee salary from monthly gross to annual ctc

Revision ID: 20260310_0025
Revises: 20260310_0024
Create Date: 2026-03-10 18:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260310_0025"
down_revision: str | None = "20260310_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("employee_salaries"):
        return

    columns = {column["name"] for column in inspector.get_columns("employee_salaries")}

    if "annual_ctc" not in columns:
        op.add_column("employee_salaries", sa.Column("annual_ctc", sa.Numeric(12, 2), nullable=True))
        columns.add("annual_ctc")

    if "gross_salary" in columns:
        op.execute("UPDATE employee_salaries SET annual_ctc = gross_salary * 12 WHERE annual_ctc IS NULL")
        op.drop_column("employee_salaries", "gross_salary")

    op.alter_column(
        "employee_salaries",
        "annual_ctc",
        existing_type=sa.Numeric(12, 2),
        nullable=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("employee_salaries"):
        return

    columns = {column["name"] for column in inspector.get_columns("employee_salaries")}

    if "gross_salary" not in columns:
        op.add_column("employee_salaries", sa.Column("gross_salary", sa.Numeric(12, 2), nullable=True))

    if "annual_ctc" in columns:
        op.execute("UPDATE employee_salaries SET gross_salary = annual_ctc / 12 WHERE gross_salary IS NULL")
        op.drop_column("employee_salaries", "annual_ctc")

    op.alter_column(
        "employee_salaries",
        "gross_salary",
        existing_type=sa.Numeric(12, 2),
        nullable=False,
    )
