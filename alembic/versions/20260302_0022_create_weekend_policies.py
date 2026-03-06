"""placeholder for missing weekend policies revision

Revision ID: 20260302_0022
Revises: 20260228_0021
Create Date: 2026-03-02 10:00:00
"""

from collections.abc import Sequence


# revision identifiers, used by Alembic.
revision: str = "20260302_0022"
down_revision: str | None = "20260228_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Kept intentionally empty to restore migration graph continuity.
    pass


def downgrade() -> None:
    pass
