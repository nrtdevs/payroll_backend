from datetime import date, datetime

from pydantic import BaseModel, Field


class HolidayTypeCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    is_paid: bool = True


class HolidayTypeUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    is_paid: bool | None = None
    is_active: bool | None = None


class HolidayTypeResponse(BaseModel):
    id: int
    name: str
    description: str | None
    is_paid: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class HolidayCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    holiday_date: date
    holiday_type_id: int = Field(ge=1)
    branch_id: int | None = Field(default=None, ge=1)
    session_id: int = Field(ge=1)
    description: str | None = Field(default=None, max_length=1000)
    is_optional: bool = False


class HolidayUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    holiday_date: date | None = None
    holiday_type_id: int | None = Field(default=None, ge=1)
    branch_id: int | None = Field(default=None, ge=1)
    session_id: int | None = Field(default=None, ge=1)
    description: str | None = Field(default=None, max_length=1000)
    is_optional: bool | None = None
    is_active: bool | None = None


class HolidayResponse(BaseModel):
    id: int
    name: str
    holiday_date: date
    holiday_type_id: int
    holiday_type_name: str
    branch_id: int | None
    session_id: int
    session_name: str
    description: str | None
    is_optional: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class HolidayCheckResponse(BaseModel):
    is_holiday: bool
    holiday_name: str | None
    holiday_id: int | None
