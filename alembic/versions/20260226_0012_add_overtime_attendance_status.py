"""add overtime attendance status

Revision ID: 20260226_0012
Revises: 20260226_0011
Create Date: 2026-02-26 17:20:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260226_0012"
down_revision: str | None = "20260226_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OLD_STATUS_ENUM = sa.Enum(
    "PRESENT",
    "ABSENT",
    "HALF_DAY",
    "LEAVE",
    "HOLIDAY",
    name="attendance_status_enum",
    native_enum=False,
)

NEW_STATUS_ENUM = sa.Enum(
    "PRESENT",
    "ABSENT",
    "HALF_DAY",
    "OVERTIME",
    "LEAVE",
    "HOLIDAY",
    name="attendance_status_enum",
    native_enum=False,
)


def upgrade() -> None:
    op.alter_column(
        "attendance",
        "status",
        existing_type=OLD_STATUS_ENUM,
        type_=NEW_STATUS_ENUM,
        existing_nullable=False,
        existing_server_default="PRESENT",
    )


def downgrade() -> None:
    op.execute("UPDATE attendance SET status = 'PRESENT' WHERE status = 'OVERTIME'")
    op.alter_column(
        "attendance",
        "status",
        existing_type=NEW_STATUS_ENUM,
        type_=OLD_STATUS_ENUM,
        existing_nullable=False,
        existing_server_default="PRESENT",
    )
