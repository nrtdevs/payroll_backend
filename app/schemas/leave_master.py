from datetime import datetime

from pydantic import BaseModel, Field


class LeaveMasterCreateItemRequest(BaseModel):
    leave_type_id: int = Field(ge=1)
    total_leave_days: int = Field(ge=0)


class LeaveMasterCreateRequest(BaseModel):
    employment_type_id: int = Field(ge=1)
    leaves: list[LeaveMasterCreateItemRequest] = Field(min_length=1)


class LeaveMasterUpdateRequest(BaseModel):
    total_leave_days: int = Field(ge=0)


class LeaveMasterResponse(BaseModel):
    id: int
    employment_type_id: int
    employment_type_name: str
    leave_type_id: int
    leave_type_name: str
    proof_required: bool
    total_leave_days: int
    created_at: datetime
    updated_at: datetime
