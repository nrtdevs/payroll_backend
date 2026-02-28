from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LeaveTypeCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    is_active: bool = True
    proof_required: bool = False


class LeaveTypeUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    is_active: bool = True
    proof_required: bool = False


class LeaveTypeResponse(BaseModel):
    id: int
    name: str
    description: str | None
    is_active: bool
    proof_required: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
