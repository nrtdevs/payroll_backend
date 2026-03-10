from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.role import RoleEnum
from app.models.user import User
from app.schemas.holiday import (
    HolidayCheckResponse,
    HolidayCreateRequest,
    HolidayResponse,
    HolidayTypeCreateRequest,
    HolidayTypeResponse,
    HolidayTypeUpdateRequest,
    HolidayUpdateRequest,
)
from app.services.holiday_service import HolidayService


router = APIRouter(tags=["Holidays"])


@router.post("/holiday-types", response_model=HolidayTypeResponse, status_code=status.HTTP_201_CREATED)
def create_holiday_type(
    payload: HolidayTypeCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> HolidayTypeResponse:
    service = HolidayService(db)
    return service.create_holiday_type(actor=current_user, payload=payload)


@router.get("/holiday-types", response_model=list[HolidayTypeResponse])
def list_holiday_types(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> list[HolidayTypeResponse]:
    service = HolidayService(db)
    return service.list_holiday_types(actor=current_user)


@router.put("/holiday-types/{holiday_type_id}", response_model=HolidayTypeResponse)
def update_holiday_type(
    holiday_type_id: int,
    payload: HolidayTypeUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> HolidayTypeResponse:
    service = HolidayService(db)
    return service.update_holiday_type(actor=current_user, holiday_type_id=holiday_type_id, payload=payload)


@router.delete("/holiday-types/{holiday_type_id}", status_code=status.HTTP_200_OK)
def delete_holiday_type(
    holiday_type_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> dict[str, str]:
    service = HolidayService(db)
    service.delete_holiday_type(actor=current_user, holiday_type_id=holiday_type_id)
    return {"detail": "Holiday type deleted successfully"}


@router.post("/holidays", response_model=HolidayResponse, status_code=status.HTTP_201_CREATED)
def create_holiday(
    payload: HolidayCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> HolidayResponse:
    service = HolidayService(db)
    return service.create_holiday(actor=current_user, payload=payload)


@router.get("/holidays", response_model=list[HolidayResponse])
def list_holidays(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
    session_id: int | None = Query(default=None, ge=1),
    branch_id: int | None = Query(default=None, ge=1),
    year: int | None = Query(default=None, ge=1900),
) -> list[HolidayResponse]:
    service = HolidayService(db)
    return service.list_holidays(actor=current_user, session_id=session_id, branch_id=branch_id, year=year)


@router.get("/holidays/check", response_model=HolidayCheckResponse)
def check_holiday(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
    date_value: date = Query(alias="date"),
    branch_id: int | None = Query(default=None, ge=1),
) -> HolidayCheckResponse:
    service = HolidayService(db)
    return service.check_holiday(actor=current_user, target_date=date_value, branch_id=branch_id)


@router.get("/holidays/{holiday_id}", response_model=HolidayResponse)
def get_holiday(
    holiday_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> HolidayResponse:
    service = HolidayService(db)
    return service.get_holiday(actor=current_user, holiday_id=holiday_id)


@router.put("/holidays/{holiday_id}", response_model=HolidayResponse)
def update_holiday(
    holiday_id: int,
    payload: HolidayUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> HolidayResponse:
    service = HolidayService(db)
    return service.update_holiday(actor=current_user, holiday_id=holiday_id, payload=payload)


@router.delete("/holidays/{holiday_id}", status_code=status.HTTP_200_OK)
def delete_holiday(
    holiday_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> dict[str, str]:
    service = HolidayService(db)
    service.delete_holiday(actor=current_user, holiday_id=holiday_id)
    return {"detail": "Holiday deleted successfully"}
