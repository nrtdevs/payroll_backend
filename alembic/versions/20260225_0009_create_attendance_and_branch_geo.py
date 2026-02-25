"""create attendance table

Revision ID: 20260225_0009
Revises: 20260223_0008
Create Date: 2026-02-25 18:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260225_0009"
down_revision: str | None = "20260223_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


attendance_status_enum = sa.Enum(
    "PRESENT",
    "ABSENT",
    "HALF_DAY",
    "LEAVE",
    "HOLIDAY",
    name="attendance_status_enum",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "attendance",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("check_in", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_out", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_minutes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", attendance_status_enum, server_default="PRESENT", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "attendance_date", name="uq_attendance_user_date"),
    )
    op.create_index("ix_attendance_id", "attendance", ["id"], unique=False)
    op.create_index("ix_attendance_user_id", "attendance", ["user_id"], unique=False)
    op.create_index("ix_attendance_user_date", "attendance", ["user_id", "attendance_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_attendance_user_date", table_name="attendance")
    op.drop_index("ix_attendance_user_id", table_name="attendance")
    op.drop_index("ix_attendance_id", table_name="attendance")
    op.drop_table("attendance")
