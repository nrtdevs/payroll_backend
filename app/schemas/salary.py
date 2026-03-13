from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.salary import SalaryComponentType


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


class SalaryStructureCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    components: list[int] = Field(min_length=1)


class SalaryStructureUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    is_active: bool | None = None
    components: list[int] | None = None


class SalaryStructureComponentResponse(BaseModel):
    id: int
    component_id: int
    component_name: str
    component_type: SalaryComponentType


class SalaryStructureResponse(BaseModel):
    id: int
    name: str
    is_active: bool
    components: list[SalaryStructureComponentResponse]
    created_at: datetime
    updated_at: datetime


class EmployeeSalaryComponentAmountRequest(BaseModel):
    component_id: int = Field(ge=1)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class EmployeeSalaryCreateRequest(BaseModel):
    employee_id: int = Field(ge=1)
    salary_structure_id: int | None = Field(default=None, ge=1)
    effective_from: date
    components: list[EmployeeSalaryComponentAmountRequest] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_components(self) -> "EmployeeSalaryCreateRequest":
        ids = [item.component_id for item in self.components]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate component_id in components")
        return self


class EmployeeSalaryUpdateRequest(BaseModel):
    salary_structure_id: int | None = Field(default=None, ge=1)
    effective_from: date | None = None
    components: list[EmployeeSalaryComponentAmountRequest] | None = None

    @model_validator(mode="after")
    def validate_unique_components(self) -> "EmployeeSalaryUpdateRequest":
        if self.components is None:
            return self
        ids = [item.component_id for item in self.components]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate component_id in components")
        return self


class EmployeeSalaryComponentAmountResponse(BaseModel):
    component_id: int
    component_name: str
    component_type: SalaryComponentType
    amount: Decimal


class EmployeeSalaryResponse(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    salary_structure_id: int | None
    salary_structure_name: str | None
    effective_from: date
    components: list[EmployeeSalaryComponentAmountResponse]
    gross_salary: Decimal
    total_deductions: Decimal
    net_salary: Decimal
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
    earnings: dict[str, Decimal]
    deductions: dict[str, Decimal]
    gross_salary: Decimal
    total_deductions: Decimal
    net_salary: Decimal


class PayrollRecordResponse(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    year: int
    month: int
    gross_salary: Decimal
    total_deductions: Decimal
    net_salary: Decimal
    created_at: datetime
    updated_at: datetime


class EmployeeSalaryBreakdownItemResponse(BaseModel):
    name: str
    amount: Decimal


class EmployeeSalaryBreakdownResponse(BaseModel):
    gross_salary: Decimal
    total_deductions: Decimal
    net_salary: Decimal
    components: list[EmployeeSalaryBreakdownItemResponse]


class SalarySlipResponse(BaseModel):
    employee: str
    month: str
    earnings: dict[str, Decimal]
    deductions: dict[str, Decimal]
    gross_salary: Decimal
    total_deductions: Decimal
    net_salary: Decimal
