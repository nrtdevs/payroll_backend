"""create holiday module

Revision ID: 20260306_0023
Revises: 20260303_0022
Create Date: 2026-03-06 20:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260306_0023"
down_revision: str | None = "20260303_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("holiday_types"):
        op.create_table(
            "holiday_types",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.text("1")),
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
            sa.UniqueConstraint("name", name="uq_holiday_types_name"),
        )
        op.execute(
            "ALTER TABLE holiday_types MODIFY updated_at TIMESTAMP NOT NULL "
            "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
        )
        op.create_index("ix_holiday_types_id", "holiday_types", ["id"], unique=False)

    if not inspector.has_table("holidays"):
        op.create_table(
            "holidays",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("holiday_date", sa.Date(), nullable=False),
            sa.Column("holiday_type_id", sa.Integer(), nullable=False),
            sa.Column("branch_id", sa.Integer(), nullable=True),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_optional", sa.Boolean(), nullable=False, server_default=sa.text("0")),
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
            sa.ForeignKeyConstraint(["holiday_type_id"], ["holiday_types.id"]),
            sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
            sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        )
        op.execute(
            "ALTER TABLE holidays MODIFY updated_at TIMESTAMP NOT NULL "
            "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
        )
        op.create_index("ix_holidays_id", "holidays", ["id"], unique=False)
        op.create_index("ix_holidays_holiday_date", "holidays", ["holiday_date"], unique=False)
        op.create_index("ix_holidays_holiday_type_id", "holidays", ["holiday_type_id"], unique=False)
        op.create_index("ix_holidays_branch_id", "holidays", ["branch_id"], unique=False)
        op.create_index("ix_holidays_session_id", "holidays", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_holidays_session_id", table_name="holidays")
    op.drop_index("ix_holidays_branch_id", table_name="holidays")
    op.drop_index("ix_holidays_holiday_type_id", table_name="holidays")
    op.drop_index("ix_holidays_holiday_date", table_name="holidays")
    op.drop_index("ix_holidays_id", table_name="holidays")
    op.drop_table("holidays")

    op.drop_index("ix_holiday_types_id", table_name="holiday_types")
    op.drop_table("holiday_types")
