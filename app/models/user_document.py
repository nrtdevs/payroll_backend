from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class UserDocumentType(StrEnum):
    PROFILE_IMAGE = "PROFILE_IMAGE"
    AADHAAR_COPY = "AADHAAR_COPY"
    PAN_COPY = "PAN_COPY"
    BANK_PROOF = "BANK_PROOF"
    EDUCATION_MARKSHEET = "EDUCATION_MARKSHEET"
    EXPERIENCE_PROOF = "EXPERIENCE_PROOF"


class UserDocument(Base):
    __tablename__ = "user_documents"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "document_type",
            "checksum",
            name="uq_user_documents_user_type_checksum",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    education_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_educations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_previous_companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    document_type: Mapped[UserDocumentType] = mapped_column(
        Enum(UserDocumentType, name="user_document_type_enum", native_enum=False),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="documents")
    education = relationship("UserEducation", back_populates="documents")
    company = relationship("UserPreviousCompany", back_populates="documents")
