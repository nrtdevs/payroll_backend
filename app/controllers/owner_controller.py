from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.role import RoleEnum
from app.models.user import User
from app.schemas.user import CreateAdminRequest, CreateEmployeeRequest, UserResponse
from app.services.management_service import ManagementService


router = APIRouter(tags=["Management"])


@router.post("/admins", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_admin(
    payload: CreateAdminRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User, Depends(require_roles(RoleEnum.MASTER_ADMIN, RoleEnum.BUSINESS_OWNER))
    ],
) -> UserResponse:
    service = ManagementService(db)
    return service.create_admin(actor=current_user, payload=payload)


@router.post("/employees", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_employee(
    payload: CreateEmployeeRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_roles(RoleEnum.MASTER_ADMIN, RoleEnum.BUSINESS_OWNER, RoleEnum.BUSINESS_ADMIN)),
    ],
) -> UserResponse:
    service = ManagementService(db)
    return service.create_employee(actor=current_user, payload=payload)
