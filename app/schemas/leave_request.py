from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.leave_request import LeaveRequestStatus


class LeaveRequestApplyRequest(BaseModel):
    leave_type_id: int = Field(ge=1)
    start_date: date
    end_date: date
    reason: str = Field(min_length=2, max_length=2000)
    proof_file_path: str | None = None


class LeaveRequestRejectRequest(BaseModel):
    rejection_reason: str = Field(min_length=2, max_length=2000)


class LeaveRequestResponse(BaseModel):
    id: int
    user_id: int
    user_name: str | None
    leave_type_id: int
    leave_type_name: str
    start_date: date
    end_date: date
    total_days: int
    reason: str
    proof_file_path: str | None
    status: LeaveRequestStatus
    applied_at: datetime
    approved_by: int | None
    approved_by_name: str | None
    approved_at: datetime | None
    rejection_reason: str | None
