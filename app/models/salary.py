from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SalaryComponentType(StrEnum):
    EARNING = "EARNING"
    DEDUCTION = "DEDUCTION"


class SalaryCalculationBase(StrEnum):
    GROSS = "GROSS"
    BASIC = "BASIC"


class SalaryComponentBaseType(StrEnum):
    GROSS = "GROSS"
    COMPONENT = "COMPONENT"


class SalaryComponent(Base):
    __tablename__ = "salary_components"
    __table_args__ = (UniqueConstraint("name", name="uq_salary_components_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[SalaryComponentType] = mapped_column(
        Enum(SalaryComponentType, name="salary_component_type_enum", native_enum=False),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SalaryStructure(Base):
    __tablename__ = "salary_structures"
    __table_args__ = (UniqueConstraint("name", name="uq_salary_structures_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    components = relationship(
        "SalaryStructureComponent",
        back_populates="salary_structure",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SalaryStructureComponent(Base):
    __tablename__ = "salary_structure_components"
    __table_args__ = (
        UniqueConstraint(
            "salary_structure_id",
            "component_id",
            name="uq_salary_structure_components_structure_component",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    salary_structure_id: Mapped[int] = mapped_column(
        ForeignKey("salary_structures.id", ondelete="CASCADE"), nullable=False, index=True
    )
    component_id: Mapped[int] = mapped_column(ForeignKey("salary_components.id"), nullable=False, index=True)
    percentage: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    fixed_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    base_type: Mapped[SalaryComponentBaseType | None] = mapped_column(
        Enum(SalaryComponentBaseType, name="salary_component_base_type_enum", native_enum=False),
        nullable=True,
    )
    base_component_id: Mapped[int | None] = mapped_column(
        ForeignKey("salary_components.id"),
        nullable=True,
        index=True,
    )
    calculation_base: Mapped[SalaryCalculationBase] = mapped_column(
        Enum(SalaryCalculationBase, name="salary_calculation_base_enum", native_enum=False),
        nullable=False,
        default=SalaryCalculationBase.GROSS,
        server_default=SalaryCalculationBase.GROSS.value,
    )

    salary_structure = relationship("SalaryStructure", back_populates="components")
    component = relationship("SalaryComponent", foreign_keys=[component_id])
    base_component = relationship("SalaryComponent", foreign_keys=[base_component_id])


class EmployeeSalary(Base):
    __tablename__ = "employee_salaries"
    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "effective_from",
            name="uq_employee_salaries_employee_effective_from",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    salary_structure_id: Mapped[int] = mapped_column(ForeignKey("salary_structures.id"), nullable=False, index=True)
    annual_ctc: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    employee = relationship("User")
    salary_structure = relationship("SalaryStructure")


class PayrollRecord(Base):
    __tablename__ = "payroll_records"
    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "year",
            "month",
            name="uq_payroll_records_employee_year_month",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    salary_assignment_id: Mapped[int] = mapped_column(ForeignKey("employee_salaries.id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    gross_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    working_days: Mapped[int] = mapped_column(Integer, nullable=False)
    present_days: Mapped[int] = mapped_column(Integer, nullable=False)
    absent_days: Mapped[int] = mapped_column(Integer, nullable=False)
    leave_days: Mapped[int] = mapped_column(Integer, nullable=False)
    absent_deduction: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_component_deduction: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    pf_deduction: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    net_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    employee = relationship("User")
    salary_assignment = relationship("EmployeeSalary")
