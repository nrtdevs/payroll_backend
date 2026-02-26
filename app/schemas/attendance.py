from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.attendance import AttendanceStatus


class FaceEnrollRequest(BaseModel):
    image_base64: str


class FaceEnrollResponse(BaseModel):
    message: str


class AttendanceCheckInRequest(BaseModel):
    image_base64: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    ip_address: str | None = None


class AttendanceCheckInResponse(BaseModel):
    message: str
    confidence: float
    location_verified: bool


class AttendanceActionRequest(BaseModel):
    user_id: int | None = Field(default=None, ge=1)


class AttendanceResponse(BaseModel):
    id: int
    user_id: int
    branch_id: int | None
    attendance_date: date
    check_in: datetime | None
    check_out: datetime | None
    latitude: float | None
    longitude: float | None
    ip_address: str | None
    device_info: str | None
    face_confidence: float | None
    total_minutes: int
    status: AttendanceStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttendanceListResponse(BaseModel):
    items: list[AttendanceResponse]
    page: int
    size: int
    total: int
    total_pages: int


class AutoAbsenceRequest(BaseModel):
    attendance_date: date
    business_id: int | None = Field(default=None, ge=1)


class AutoAbsenceResponse(BaseModel):
    attendance_date: date
    created_count: int
    skipped_existing_count: int
