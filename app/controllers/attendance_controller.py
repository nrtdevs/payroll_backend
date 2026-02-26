from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import BadRequestException
from app.models.user import User
from app.schemas.attendance import (
    AttendanceActionRequest,
    AttendanceCheckInRequest,
    AttendanceCheckInResponse,
    AttendanceListResponse,
    AttendanceResponse,
    AutoAbsenceRequest,
    AutoAbsenceResponse,
    FaceEnrollRequest,
    FaceEnrollResponse,
)
from app.services.attendance_service import AttendanceService


router = APIRouter(tags=["Attendance"])


def _extract_image_from_form(form) -> bytes:
    for key in ("image", "file", "selfie"):
        value = form.get(key)
        if value is None:
            continue
        read_fn = getattr(value, "read", None)
        if callable(read_fn):
            return value
    raise BadRequestException("image file is required (use multipart field: image)")


@router.post("/face/enroll", response_model=FaceEnrollResponse, status_code=status.HTTP_200_OK)
async def enroll_face(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FaceEnrollResponse:
    service = AttendanceService(db)
    content_type = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" in content_type:
        form = await request.form()
        image = _extract_image_from_form(form)
        image_bytes = await image.read()
        return service.enroll_face(actor=current_user, image_bytes=image_bytes)

    payload = FaceEnrollRequest.model_validate(await request.json())
    return service.enroll_face(actor=current_user, image_base64=payload.image_base64)


@router.post("/attendance/check-in", response_model=AttendanceCheckInResponse, status_code=status.HTTP_201_CREATED)
async def check_in(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    request: Request,
) -> AttendanceCheckInResponse:
    service = AttendanceService(db)
    content_type = (request.headers.get("content-type") or "").lower()
    image_base64: str | None = None
    image_bytes: bytes | None = None
    latitude: float
    longitude: float
    ip_address: str | None = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        image = _extract_image_from_form(form)
        image_bytes = await image.read()
        try:
            latitude = float(form.get("latitude"))
            longitude = float(form.get("longitude"))
        except (TypeError, ValueError) as exc:
            raise BadRequestException("latitude and longitude are required") from exc
        ip_address = form.get("ip_address")
    else:
        payload = AttendanceCheckInRequest.model_validate(await request.json())
        image_base64 = payload.image_base64
        latitude = payload.latitude
        longitude = payload.longitude
        ip_address = payload.ip_address

    forwarded_ip = request.headers.get("x-forwarded-for")
    resolved_ip = ip_address or (forwarded_ip.split(",")[0].strip() if forwarded_ip else None)
    if resolved_ip is None and request.client is not None:
        resolved_ip = request.client.host
    return service.check_in(
        actor=current_user,
        image_base64=image_base64,
        image_bytes=image_bytes,
        latitude=latitude,
        longitude=longitude,
        ip_address=resolved_ip,
        device_info=request.headers.get("user-agent"),
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
    branch_id: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
) -> AttendanceListResponse:
    if start_date is not None and end_date is not None and end_date < start_date:
        raise BadRequestException("end_date must be greater than or equal to start_date")
    service = AttendanceService(db)
    return service.list_attendance(
        actor=current_user,
        user_id=user_id,
        branch_id=branch_id,
        status=status,
        search=search,
        start_date=start_date,
        end_date=end_date,
        page=page,
        size=size,
    )


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
