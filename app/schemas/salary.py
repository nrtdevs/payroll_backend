from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.salary import SalaryCalculationBase, SalaryComponentBaseType, SalaryComponentType


class SalaryComponentCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    type: SalaryComponentType


class SalaryComponentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    type: SalaryComponentType | None = None
    is_active: bool | None = None


class SalaryComponentResponse(BaseModel):
    id: int
    name: str
    type: SalaryComponentType
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SalaryStructureComponentItemRequest(BaseModel):
    component_id: int = Field(ge=1)
    percentage: Decimal | None = Field(default=None, gt=0, max_digits=7, decimal_places=2)
    fixed_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    base_type: SalaryComponentBaseType | None = None
    base_component_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_value_source(self) -> "SalaryStructureComponentItemRequest":
        if self.percentage is None and self.fixed_amount is None:
            raise ValueError("Either percentage or fixed_amount is required")
        if self.percentage is not None and self.fixed_amount is not None:
            raise ValueError("Provide only one of percentage or fixed_amount")
        if self.percentage is not None and self.base_type is None:
            raise ValueError("base_type is required when percentage is used")
        if self.fixed_amount is not None and (self.base_type is not None or self.base_component_id is not None):
            raise ValueError("base_type/base_component_id must be omitted when fixed_amount is used")
        if self.base_type == SalaryComponentBaseType.GROSS and self.base_component_id is not None:
            raise ValueError("base_component_id is not allowed when base_type is GROSS")
        if self.base_type == SalaryComponentBaseType.COMPONENT and self.base_component_id is None:
            raise ValueError("base_component_id is required when base_type is COMPONENT")
        return self


class SalaryStructureCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    components: list[SalaryStructureComponentItemRequest] = Field(min_length=1)


class SalaryStructureUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    is_active: bool | None = None
    components: list[SalaryStructureComponentItemRequest] | None = None


class SalaryStructureComponentResponse(BaseModel):
    id: int
    component_id: int
    component_name: str
    component_type: SalaryComponentType
    percentage: Decimal | None
    fixed_amount: Decimal | None
    base_type: SalaryComponentBaseType | None
    base_component_id: int | None


class SalaryStructureResponse(BaseModel):
    id: int
    name: str
    is_active: bool
    components: list[SalaryStructureComponentResponse]
    created_at: datetime
    updated_at: datetime


class EmployeeSalaryCreateRequest(BaseModel):
    employee_id: int = Field(ge=1)
    salary_structure_id: int = Field(ge=1)
    annual_ctc: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    effective_from: date


class EmployeeSalaryUpdateRequest(BaseModel):
    salary_structure_id: int | None = Field(default=None, ge=1)
    annual_ctc: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    effective_from: date | None = None


class EmployeeSalaryResponse(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    salary_structure_id: int
    salary_structure_name: str
    annual_ctc: Decimal
    effective_from: date
    created_at: datetime
    updated_at: datetime


class PayrollGenerateRequest(BaseModel):
    employee_id: int = Field(ge=1)
    year: int = Field(ge=1900, le=3000)
    month: int = Field(ge=1, le=12)


class PayrollGenerateResponse(BaseModel):
    employee_id: int
    year: int
    month: int
    gross_salary: Decimal
    working_days: int
    present_days: int
    absent_days: int
    leave_days: int
    absent_deduction: Decimal
    component_deductions: dict[str, Decimal]
    pf_deduction: Decimal
    net_salary: Decimal


class PayrollRecordResponse(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    year: int
    month: int
    gross_salary: Decimal
    working_days: int
    present_days: int
    absent_days: int
    leave_days: int
    absent_deduction: Decimal
    total_component_deduction: Decimal
    pf_deduction: Decimal
    net_salary: Decimal
    created_at: datetime
    updated_at: datetime


class EmployeeSalaryBreakdownItemResponse(BaseModel):
    name: str
    amount: Decimal


class EmployeeSalaryBreakdownResponse(BaseModel):
    gross_salary: Decimal
    components: list[EmployeeSalaryBreakdownItemResponse]


class SalarySlipResponse(BaseModel):
    employee: str
    month: str
    earnings: dict[str, Decimal]
    deductions: dict[str, Decimal]
    gross_salary: Decimal
    net_salary: Decimal
