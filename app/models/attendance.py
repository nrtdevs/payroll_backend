from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AttendanceStatus(StrEnum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    HALF_DAY = "HALF_DAY"
    LEAVE = "LEAVE"
    HOLIDAY = "HOLIDAY"


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("user_id", "attendance_date", name="uq_attendance_user_date"),
        Index("ix_attendance_user_date", "user_id", "attendance_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False)
    check_in: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_in_latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    check_in_longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    check_in_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    check_in_selfie_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location_distance_meters: Mapped[int | None] = mapped_column(Integer, nullable=True)
    face_match_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    total_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, name="attendance_status_enum", native_enum=False),
        nullable=False,
        default=AttendanceStatus.PRESENT,
        server_default=AttendanceStatus.PRESENT.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="attendances")
