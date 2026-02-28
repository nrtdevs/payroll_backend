from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.role import RoleEnum
from app.models.user_document import UserDocumentType


class UserCreateBase(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)


class CreateOwnerRequest(UserCreateBase):
    business_name: str = Field(min_length=2, max_length=255)


class CreateAdminRequest(UserCreateBase):
    business_id: int | None = None


class CreateEmployeeRequest(UserCreateBase):
    business_id: int | None = None


class EducationDetailsRequest(BaseModel):
    record_key: str = Field(min_length=1, max_length=100)
    degree: str = Field(min_length=2, max_length=150)
    institution: str = Field(min_length=2, max_length=255)
    year_of_passing: int = Field(ge=1950, le=2200)
    percentage: Decimal = Field(ge=0, le=100)


class PreviousCompanyDetailsRequest(BaseModel):
    record_key: str = Field(min_length=1, max_length=100)
    company_name: str = Field(min_length=2, max_length=255)
    designation: str = Field(min_length=2, max_length=150)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_dates(self) -> "PreviousCompanyDetailsRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date")
        return self


class BankAccountDetailsRequest(BaseModel):
    account_holder_name: str = Field(min_length=2, max_length=150)
    account_number: str = Field(min_length=6, max_length=50)
    ifsc_code: str = Field(min_length=4, max_length=20)
    bank_name: str = Field(min_length=2, max_length=150)


class UserCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    branch_id: int
    employment_type_id: int
    designation_id: int
    role_id: int
    salary_type: str = Field(min_length=2, max_length=50)
    salary: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    leave_balance: int = Field(ge=0)
    status: str = Field(min_length=2, max_length=50)
    current_address: str = Field(min_length=3, max_length=500)
    home_address: str = Field(min_length=3, max_length=500)
    pan: str = Field(min_length=5, max_length=20)
    aadhaar: str = Field(min_length=8, max_length=20)
    mobile: str = Field(min_length=10, max_length=20)
    number: str = Field(min_length=10, max_length=20)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    father_name: str = Field(min_length=2, max_length=150)
    mother_name: str = Field(min_length=2, max_length=150)
    educations: list[EducationDetailsRequest] = Field(default_factory=list)
    previous_companies: list[PreviousCompanyDetailsRequest] = Field(default_factory=list)
    bank_account: BankAccountDetailsRequest


class UserUpdateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    branch_id: int
    employment_type_id: int
    designation_id: int
    role_id: int
    salary_type: str = Field(min_length=2, max_length=50)
    salary: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    leave_balance: int = Field(ge=0)
    status: str = Field(min_length=2, max_length=50)
    current_address: str = Field(min_length=3, max_length=500)
    home_address: str = Field(min_length=3, max_length=500)
    pan: str = Field(min_length=5, max_length=20)
    aadhaar: str = Field(min_length=8, max_length=20)
    mobile: str = Field(min_length=10, max_length=20)
    number: str = Field(min_length=10, max_length=20)
    email: EmailStr
    father_name: str = Field(min_length=2, max_length=150)
    mother_name: str = Field(min_length=2, max_length=150)
    business_id: int | None = None
    educations: list[EducationDetailsRequest] = Field(default_factory=list)
    previous_companies: list[PreviousCompanyDetailsRequest] = Field(default_factory=list)
    bank_account: BankAccountDetailsRequest


class FileIndexMapRequest(BaseModel):
    mapping: dict[str, list[int]] = Field(default_factory=dict)


class UserDocumentResponse(BaseModel):
    id: int
    document_type: UserDocumentType
    original_filename: str
    content_type: str
    file_size: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserEducationResponse(BaseModel):
    id: int
    degree: str
    institution: str
    year_of_passing: int
    percentage: Decimal
    documents: list[UserDocumentResponse]

    model_config = ConfigDict(from_attributes=True)


class UserPreviousCompanyResponse(BaseModel):
    id: int
    company_name: str
    designation: str
    start_date: date
    end_date: date
    documents: list[UserDocumentResponse]

    model_config = ConfigDict(from_attributes=True)


class UserBankAccountResponse(BaseModel):
    account_holder_name: str
    account_number: str
    ifsc_code: str
    bank_name: str

    model_config = ConfigDict(from_attributes=True)


class UserLeavePolicyResponse(BaseModel):
    leave_master_id: int
    leave_type_id: int
    leave_type_name: str
    proof_required: bool
    total_leave_days: int


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    first_name: str
    middle_name: str | None
    last_name: str
    role: RoleEnum
    business_id: int | None
    name: str | None
    branch_id: int | None
    employment_type_id: int | None
    designation_id: int | None
    role_id: int | None
    salary_type: str | None
    salary: Decimal | None
    leave_balance: int | None
    status: str | None
    current_address: str | None
    home_address: str | None
    pan: str | None
    aadhaar: str | None
    mobile: str | None
    number: str | None
    father_name: str | None
    mother_name: str | None
    bank_account: UserBankAccountResponse | None
    educations: list[UserEducationResponse]
    previous_companies: list[UserPreviousCompanyResponse]
    documents: list[UserDocumentResponse]
    leave_policies: list[UserLeavePolicyResponse] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    items: list[UserResponse]
    page: int
    size: int
    total: int
    total_pages: int
