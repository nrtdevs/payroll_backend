"""create user profile normalized tables

Revision ID: 20260223_0008
Revises: 20260220_0007
Create Date: 2026-02-23 10:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260223_0008"
down_revision: str | None = "20260220_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


user_document_type_enum = sa.Enum(
    "PROFILE_IMAGE",
    "AADHAAR_COPY",
    "PAN_COPY",
    "BANK_PROOF",
    "EDUCATION_MARKSHEET",
    "EXPERIENCE_PROOF",
    name="user_document_type_enum",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "user_educations",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("degree", sa.String(length=150), nullable=False),
        sa.Column("institution", sa.String(length=255), nullable=False),
        sa.Column("year_of_passing", sa.Integer(), nullable=False),
        sa.Column("percentage", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_user_educations_id", "user_educations", ["id"], unique=False)
    op.create_index("ix_user_educations_user_id", "user_educations", ["user_id"], unique=False)

    op.create_table(
        "user_previous_companies",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("designation", sa.String(length=150), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_user_previous_companies_id", "user_previous_companies", ["id"], unique=False)
    op.create_index(
        "ix_user_previous_companies_user_id",
        "user_previous_companies",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "user_bank_accounts",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("account_holder_name", sa.String(length=150), nullable=False),
        sa.Column("account_number", sa.String(length=50), nullable=False),
        sa.Column("ifsc_code", sa.String(length=20), nullable=False),
        sa.Column("bank_name", sa.String(length=150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_user_bank_accounts_user_id"),
    )
    op.create_index("ix_user_bank_accounts_id", "user_bank_accounts", ["id"], unique=False)
    op.create_index("ix_user_bank_accounts_user_id", "user_bank_accounts", ["user_id"], unique=False)

    op.create_table(
        "user_documents",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("education_id", sa.Integer(), nullable=True),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("document_type", user_document_type_enum, nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["user_previous_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["education_id"], ["user_educations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("stored_filename", name="uq_user_documents_stored_filename"),
        sa.UniqueConstraint(
            "user_id",
            "document_type",
            "checksum",
            name="uq_user_documents_user_type_checksum",
        ),
    )
    op.create_index("ix_user_documents_id", "user_documents", ["id"], unique=False)
    op.create_index("ix_user_documents_user_id", "user_documents", ["user_id"], unique=False)
    op.create_index("ix_user_documents_education_id", "user_documents", ["education_id"], unique=False)
    op.create_index("ix_user_documents_company_id", "user_documents", ["company_id"], unique=False)
    op.create_index("ix_user_documents_document_type", "user_documents", ["document_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_documents_document_type", table_name="user_documents")
    op.drop_index("ix_user_documents_company_id", table_name="user_documents")
    op.drop_index("ix_user_documents_education_id", table_name="user_documents")
    op.drop_index("ix_user_documents_user_id", table_name="user_documents")
    op.drop_index("ix_user_documents_id", table_name="user_documents")
    op.drop_table("user_documents")

    op.drop_index("ix_user_bank_accounts_user_id", table_name="user_bank_accounts")
    op.drop_index("ix_user_bank_accounts_id", table_name="user_bank_accounts")
    op.drop_table("user_bank_accounts")

    op.drop_index("ix_user_previous_companies_user_id", table_name="user_previous_companies")
    op.drop_index("ix_user_previous_companies_id", table_name="user_previous_companies")
    op.drop_table("user_previous_companies")

    op.drop_index("ix_user_educations_user_id", table_name="user_educations")
    op.drop_index("ix_user_educations_id", table_name="user_educations")
    op.drop_table("user_educations")
