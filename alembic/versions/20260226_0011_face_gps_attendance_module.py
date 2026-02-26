"""face and gps attendance module fields

Revision ID: 20260226_0011
Revises: 20260225_0010
Create Date: 2026-02-26 10:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260226_0011"
down_revision: str | None = "20260225_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("face_encoding", sa.Text(), nullable=True))

    op.add_column(
        "branches",
        sa.Column("radius_meters", sa.Integer(), nullable=False, server_default="200"),
    )

    op.add_column("attendance", sa.Column("branch_id", sa.Integer(), nullable=True))
    op.add_column("attendance", sa.Column("latitude", sa.Numeric(precision=10, scale=7), nullable=True))
    op.add_column("attendance", sa.Column("longitude", sa.Numeric(precision=10, scale=7), nullable=True))
    op.add_column("attendance", sa.Column("ip_address", sa.String(length=45), nullable=True))
    op.add_column("attendance", sa.Column("device_info", sa.String(length=255), nullable=True))
    op.add_column("attendance", sa.Column("face_confidence", sa.Numeric(precision=5, scale=4), nullable=True))
    op.create_index("ix_attendance_branch_id", "attendance", ["branch_id"], unique=False)
    op.create_foreign_key(
        "fk_attendance_branch_id_branches",
        "attendance",
        "branches",
        ["branch_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_attendance_branch_id_branches", "attendance", type_="foreignkey")
    op.drop_index("ix_attendance_branch_id", table_name="attendance")
    op.drop_column("attendance", "face_confidence")
    op.drop_column("attendance", "device_info")
    op.drop_column("attendance", "ip_address")
    op.drop_column("attendance", "longitude")
    op.drop_column("attendance", "latitude")
    op.drop_column("attendance", "branch_id")

    op.drop_column("branches", "radius_meters")
    op.drop_column("users", "face_encoding")
