"""create leave requests and balances

Revision ID: 20260228_0021
Revises: 20260228_0020
Create Date: 2026-02-28 18:10:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260228_0021"
down_revision: str | None = "20260228_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


leave_request_status_enum = sa.Enum(
    "PENDING",
    "APPROVED",
    "REJECTED",
    name="leave_request_status_enum",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "employee_leave_balances",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("leave_type_id", sa.Integer(), nullable=False),
        sa.Column("allocated_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("used_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("remaining_days", sa.Integer(), nullable=False, server_default="0"),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["leave_type_id"], ["leave_types.id"]),
    )
    op.execute(
        "ALTER TABLE employee_leave_balances MODIFY updated_at TIMESTAMP NOT NULL "
        "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
    )
    op.create_index("ix_employee_leave_balances_id", "employee_leave_balances", ["id"], unique=False)
    op.create_index("ix_employee_leave_balances_user_id", "employee_leave_balances", ["user_id"], unique=False)
    op.create_index("ix_employee_leave_balances_leave_type_id", "employee_leave_balances", ["leave_type_id"], unique=False)
    op.create_index(
        "uq_employee_leave_balance_user_leave_type",
        "employee_leave_balances",
        ["user_id", "leave_type_id"],
        unique=True,
    )

    op.create_table(
        "leave_requests",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("leave_type_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("total_days", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("proof_file_path", sa.String(length=500), nullable=True),
        sa.Column("status", leave_request_status_enum, nullable=False, server_default="PENDING"),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["leave_type_id"], ["leave_types.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_leave_requests_id", "leave_requests", ["id"], unique=False)
    op.create_index("ix_leave_requests_user_id", "leave_requests", ["user_id"], unique=False)
    op.create_index("ix_leave_requests_leave_type_id", "leave_requests", ["leave_type_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_leave_requests_leave_type_id", table_name="leave_requests")
    op.drop_index("ix_leave_requests_user_id", table_name="leave_requests")
    op.drop_index("ix_leave_requests_id", table_name="leave_requests")
    op.drop_table("leave_requests")

    op.drop_index("uq_employee_leave_balance_user_leave_type", table_name="employee_leave_balances")
    op.drop_index("ix_employee_leave_balances_leave_type_id", table_name="employee_leave_balances")
    op.drop_index("ix_employee_leave_balances_user_id", table_name="employee_leave_balances")
    op.drop_index("ix_employee_leave_balances_id", table_name="employee_leave_balances")
    op.drop_table("employee_leave_balances")
