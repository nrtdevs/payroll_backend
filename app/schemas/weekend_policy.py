from datetime import date, datetime

from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    start_date: date
    end_date: date
    branch_id: int | None = Field(default=None, ge=1)
    is_active: bool = True


class SessionResponse(BaseModel):
    id: int
    name: str
    start_date: date
    end_date: date
    branch_id: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SessionUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool | None = None


class WeekendPolicyRuleRequest(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    week_number: int | None = Field(default=None, ge=1, le=5)


class WeekendPolicyCreateRequest(BaseModel):
    session_id: int = Field(ge=1)
    name: str = Field(min_length=2, max_length=255)
    branch_id: int | None = Field(default=None, ge=1)
    rules: list[WeekendPolicyRuleRequest] = Field(min_length=1)


class WeekendPolicyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    branch_id: int | None = Field(default=None, ge=1)
    is_active: bool | None = None
    rules: list[WeekendPolicyRuleRequest] | None = None


class WeekendPolicyRuleResponse(BaseModel):
    id: int
    day_of_week: int
    week_number: int | None


class WeekendPolicyResponse(BaseModel):
    id: int
    session_id: int
    session_name: str
    name: str
    branch_id: int | None
    effective_from: date
    effective_to: date | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    rules: list[WeekendPolicyRuleResponse]


class WeekendCheckResponse(BaseModel):
    is_weekend: bool
    session_id: int | None
    policy_id: int | None
