from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.role import RoleEnum


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


class UserCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    branch_id: int
    role_id: int
    salary_type: str = Field(min_length=2, max_length=50)
    salary: Decimal = Field(gt=0)
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
    business_id: int | None = None


class UserUpdateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    branch_id: int
    role_id: int
    salary_type: str = Field(min_length=2, max_length=50)
    salary: Decimal = Field(gt=0)
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
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    items: list[UserResponse]
    page: int
    size: int
    total: int
    total_pages: int
