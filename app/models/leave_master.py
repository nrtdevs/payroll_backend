from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class LeaveMaster(Base):
    __tablename__ = "leave_masters"
    __table_args__ = (
        UniqueConstraint(
            "employment_type_id",
            "leave_type_id",
            name="uq_leave_masters_employment_leave_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employment_type_id: Mapped[int] = mapped_column(
        ForeignKey("employment_types.id"),
        nullable=False,
        index=True,
    )
    leave_type_id: Mapped[int] = mapped_column(
        ForeignKey("leave_types.id"),
        nullable=False,
        index=True,
    )
    total_leave_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    proof_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    employment_type = relationship("EmploymentType")
    leave_type = relationship("LeaveType")
