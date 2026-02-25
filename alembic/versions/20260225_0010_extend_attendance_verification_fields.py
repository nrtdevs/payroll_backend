"""extend attendance verification fields

Revision ID: 20260225_0010
Revises: 20260225_0009
Create Date: 2026-02-25 18:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260225_0010"
down_revision: str | None = "20260225_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("branches", sa.Column("latitude", sa.Numeric(precision=10, scale=7), nullable=True))
    op.add_column("branches", sa.Column("longitude", sa.Numeric(precision=10, scale=7), nullable=True))

    op.add_column("attendance", sa.Column("check_in_latitude", sa.Numeric(precision=10, scale=7), nullable=True))
    op.add_column("attendance", sa.Column("check_in_longitude", sa.Numeric(precision=10, scale=7), nullable=True))
    op.add_column("attendance", sa.Column("check_in_ip", sa.String(length=45), nullable=True))
    op.add_column("attendance", sa.Column("check_in_selfie_path", sa.String(length=500), nullable=True))
    op.add_column("attendance", sa.Column("location_distance_meters", sa.Integer(), nullable=True))
    op.add_column("attendance", sa.Column("face_match_score", sa.Numeric(precision=5, scale=4), nullable=True))


def downgrade() -> None:
    op.drop_column("attendance", "face_match_score")
    op.drop_column("attendance", "location_distance_meters")
    op.drop_column("attendance", "check_in_selfie_path")
    op.drop_column("attendance", "check_in_ip")
    op.drop_column("attendance", "check_in_longitude")
    op.drop_column("attendance", "check_in_latitude")

    op.drop_column("branches", "longitude")
    op.drop_column("branches", "latitude")
