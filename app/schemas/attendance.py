from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.attendance import AttendanceStatus


class AttendanceActionRequest(BaseModel):
    user_id: int | None = Field(default=None, ge=1)


class AttendanceResponse(BaseModel):
    id: int
    user_id: int
    attendance_date: date
    check_in: datetime | None
    check_out: datetime | None
    check_in_latitude: float | None
    check_in_longitude: float | None
    check_in_ip: str | None
    check_in_selfie_path: str | None
    location_distance_meters: int | None
    face_match_score: float | None
    total_minutes: int
    status: AttendanceStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttendanceListResponse(BaseModel):
    items: list[AttendanceResponse]


class AutoAbsenceRequest(BaseModel):
    attendance_date: date
    business_id: int | None = Field(default=None, ge=1)


class AutoAbsenceResponse(BaseModel):
    attendance_date: date
    created_count: int
    skipped_existing_count: int
