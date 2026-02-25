from datetime import datetime

from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.role import RoleEnum


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[RoleEnum] = mapped_column(
        Enum(RoleEnum, name="role_enum", native_enum=False), nullable=False
    )
    business_id: Mapped[int | None] = mapped_column(ForeignKey("businesses.id"), nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"), nullable=True, index=True)
    salary_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    leave_balance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    home_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pan: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    aadhaar: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    mobile: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    father_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    mother_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    business = relationship("Business", back_populates="users")
    educations = relationship(
        "UserEducation",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    previous_companies = relationship(
        "UserPreviousCompany",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    bank_account = relationship(
        "UserBankAccount",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    documents = relationship(
        "UserDocument",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    attendances = relationship(
        "Attendance",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
