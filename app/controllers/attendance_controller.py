from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import BadRequestException
from app.models.user import User
from app.schemas.attendance import AttendanceActionRequest, AttendanceListResponse, AttendanceResponse, AutoAbsenceRequest, AutoAbsenceResponse
from app.services.attendance_service import AttendanceService


router = APIRouter(tags=["Attendance"])


@router.post("/attendance/check-in", response_model=AttendanceResponse, status_code=status.HTTP_201_CREATED)
def check_in(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
    selfie: UploadFile = File(...),
    latitude: float = Form(..., ge=-90, le=90),
    longitude: float = Form(..., ge=-180, le=180),
    ip_address: str | None = Form(default=None),
    user_id: int | None = Form(default=None, ge=1),
) -> AttendanceResponse:
    service = AttendanceService(db)
    forwarded_ip = request.headers.get("x-forwarded-for")
    resolved_ip = (ip_address or (forwarded_ip.split(",")[0].strip() if forwarded_ip else None))
    if resolved_ip is None and request.client is not None:
        resolved_ip = request.client.host
    return service.check_in(
        actor=current_user,
        selfie=selfie,
        latitude=latitude,
        longitude=longitude,
        ip_address=resolved_ip,
        user_id=user_id,
    )


@router.post("/attendance/check-out", response_model=AttendanceResponse)
def check_out(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    payload: AttendanceActionRequest,
) -> AttendanceResponse:
    service = AttendanceService(db)
    return service.check_out(actor=current_user, user_id=payload.user_id)


@router.get("/attendance", response_model=AttendanceListResponse)
def list_attendance(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    user_id: int | None = Query(default=None, ge=1),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
) -> AttendanceListResponse:
    if start_date is not None and end_date is not None and end_date < start_date:
        raise BadRequestException("end_date must be greater than or equal to start_date")
    service = AttendanceService(db)
    items = service.list_attendance(
        actor=current_user,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )
    return AttendanceListResponse(items=items)


@router.post("/attendance/auto-absence", response_model=AutoAbsenceResponse)
def auto_absence(
    payload: AutoAbsenceRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AutoAbsenceResponse:
    service = AttendanceService(db)
    return service.mark_auto_absence(
        actor=current_user,
        attendance_date=payload.attendance_date,
        business_id=payload.business_id,
    )
