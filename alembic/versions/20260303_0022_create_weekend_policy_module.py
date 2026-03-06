"""create weekend policy module

Revision ID: 20260303_0022
Revises: 20260228_0021
Create Date: 2026-03-03 12:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision: str = "20260303_0022"
down_revision: str | None = "20260302_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("sessions"):
        op.create_table(
            "sessions",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("name", sa.String(length=150), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=False),
            sa.Column("branch_id", sa.Integer(), nullable=True),
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
            sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        )
        op.execute(
            "ALTER TABLE sessions MODIFY updated_at TIMESTAMP NOT NULL "
            "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
        )
        op.create_index("ix_sessions_id", "sessions", ["id"], unique=False)
        op.create_index("ix_sessions_branch_id", "sessions", ["branch_id"], unique=False)

    if inspector.has_table("weekend_policies"):
        existing_columns = {column["name"] for column in inspector.get_columns("weekend_policies")}
        expected_columns = {
            "id",
            "session_id",
            "name",
            "branch_id",
            "effective_from",
            "effective_to",
            "is_active",
            "created_at",
            "updated_at",
        }
        if not expected_columns.issubset(existing_columns):
            row_count = bind.execute(text("SELECT COUNT(*) FROM weekend_policies")).scalar() or 0
            if int(row_count) > 0:
                raise RuntimeError(
                    "Existing weekend_policies data found in legacy schema. "
                    "Please migrate data manually before upgrading."
                )

            if inspector.has_table("weekend_policy_dates"):
                legacy_dates_count = bind.execute(text("SELECT COUNT(*) FROM weekend_policy_dates")).scalar() or 0
                if int(legacy_dates_count) > 0:
                    raise RuntimeError(
                        "Legacy weekend_policy_dates has data. Please migrate data manually before upgrading."
                    )
                op.drop_table("weekend_policy_dates")

            if inspector.has_table("weekend_policy_sessions"):
                legacy_sessions_count = bind.execute(text("SELECT COUNT(*) FROM weekend_policy_sessions")).scalar() or 0
                if int(legacy_sessions_count) > 0:
                    raise RuntimeError(
                        "Legacy weekend_policy_sessions has data. Please migrate data manually before upgrading."
                    )
                op.drop_table("weekend_policy_sessions")

            op.drop_table("weekend_policies")

    if not inspector.has_table("weekend_policies"):
        op.create_table(
            "weekend_policies",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("branch_id", sa.Integer(), nullable=True),
            sa.Column("effective_from", sa.Date(), nullable=False),
            sa.Column("effective_to", sa.Date(), nullable=True),
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
            sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
            sa.ForeignKeyConstraint(["branch_id"], ["branches.id"]),
        )
        op.execute(
            "ALTER TABLE weekend_policies MODIFY updated_at TIMESTAMP NOT NULL "
            "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
        )
        op.create_index("ix_weekend_policies_id", "weekend_policies", ["id"], unique=False)
        op.create_index("ix_weekend_policies_session_id", "weekend_policies", ["session_id"], unique=False)
        op.create_index("ix_weekend_policies_branch_id", "weekend_policies", ["branch_id"], unique=False)

    if not inspector.has_table("weekend_policy_rules"):
        op.create_table(
            "weekend_policy_rules",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("weekend_policy_id", sa.Integer(), nullable=False),
            sa.Column("day_of_week", sa.Integer(), nullable=False),
            sa.Column("week_number", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["weekend_policy_id"], ["weekend_policies.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_weekend_policy_rules_id", "weekend_policy_rules", ["id"], unique=False)
        op.create_index(
            "ix_weekend_policy_rules_weekend_policy_id",
            "weekend_policy_rules",
            ["weekend_policy_id"],
            unique=False,
        )
        op.create_index(
            "uq_weekend_rule_tuple",
            "weekend_policy_rules",
            ["weekend_policy_id", "day_of_week", "week_number"],
            unique=True,
        )


def downgrade() -> None:
    op.drop_index("uq_weekend_rule_tuple", table_name="weekend_policy_rules")
    op.drop_index("ix_weekend_policy_rules_weekend_policy_id", table_name="weekend_policy_rules")
    op.drop_index("ix_weekend_policy_rules_id", table_name="weekend_policy_rules")
    op.drop_table("weekend_policy_rules")

    op.drop_index("ix_weekend_policies_branch_id", table_name="weekend_policies")
    op.drop_index("ix_weekend_policies_session_id", table_name="weekend_policies")
    op.drop_index("ix_weekend_policies_id", table_name="weekend_policies")
    op.drop_table("weekend_policies")

    op.drop_index("ix_sessions_branch_id", table_name="sessions")
    op.drop_index("ix_sessions_id", table_name="sessions")
    op.drop_table("sessions")
