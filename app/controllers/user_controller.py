from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.role import RoleEnum
from app.models.user import User
from app.schemas.user import UserCreateRequest, UserListResponse, UserResponse, UserUpdateRequest
from app.services.user_service import UserService


router = APIRouter(tags=["Users"])


@router.get("/users/me", response_model=UserResponse)
def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return current_user


@router.get("/users", response_model=list[UserResponse])
def list_users(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[UserResponse]:
    service = UserService(db)
    return service.list_users(current_user=current_user)


@router.get("/users/paginated", response_model=UserListResponse)
def list_users_paginated(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    first_name: str | None = Query(default=None),
    mobile_number: str | None = Query(default=None),
    branch_id: int | None = Query(default=None, ge=1),
) -> UserListResponse:
    service = UserService(db)
    return service.list_users_paginated(
        current_user=current_user,
        page=page,
        size=size,
        first_name=first_name,
        mobile_number=mobile_number,
        branch_id=branch_id,
    )


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_roles(RoleEnum.MASTER_ADMIN, RoleEnum.BUSINESS_OWNER, RoleEnum.BUSINESS_ADMIN)),
    ],
) -> UserResponse:
    service = UserService(db)
    return service.create_user(actor=current_user, payload=payload)


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_roles(RoleEnum.MASTER_ADMIN, RoleEnum.BUSINESS_OWNER, RoleEnum.BUSINESS_ADMIN)),
    ],
) -> UserResponse:
    service = UserService(db)
    return service.get_user(actor=current_user, user_id=user_id)


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_roles(RoleEnum.MASTER_ADMIN, RoleEnum.BUSINESS_OWNER, RoleEnum.BUSINESS_ADMIN)),
    ],
) -> UserResponse:
    service = UserService(db)
    return service.update_user(actor=current_user, user_id=user_id, payload=payload)


@router.delete("/users/{user_id}", status_code=status.HTTP_200_OK)
def delete_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_roles(RoleEnum.MASTER_ADMIN, RoleEnum.BUSINESS_OWNER, RoleEnum.BUSINESS_ADMIN)),
    ],
) -> dict[str, str]:
    service = UserService(db)
    service.delete_user(actor=current_user, user_id=user_id)
    return {"detail": "User successfully deleted"}
