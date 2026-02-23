from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.exceptions import BadRequestException
from app.models.role import RoleEnum
from app.models.user import User
from app.schemas.user import UserCreateRequest, UserListResponse, UserResponse, UserUpdateRequest
from app.services.user_service import UserFilePayload, UserService


router = APIRouter(tags=["Users"])


def _parse_mapping(mapping_json: str, *, field_name: str) -> dict[str, list[int]]:
    try:
        raw = json.loads(mapping_json)
    except json.JSONDecodeError as exc:
        raise BadRequestException(f"{field_name} must be valid JSON") from exc
    if not isinstance(raw, dict):
        raise BadRequestException(f"{field_name} must be a JSON object")

    parsed: dict[str, list[int]] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            raise BadRequestException(f"{field_name} keys must be strings")
        if not isinstance(value, list) or not all(isinstance(item, int) for item in value):
            raise BadRequestException(f"{field_name} values must be integer arrays")
        parsed[key] = value
    return parsed


def _build_files_payload(
    *,
    profile_image: UploadFile | None,
    aadhaar_copy: UploadFile | None,
    pan_copy: UploadFile | None,
    bank_proof: UploadFile | None,
    education_marksheets: list[UploadFile] | None,
    education_file_map: str,
    experience_proofs: list[UploadFile] | None,
    company_file_map: str,
) -> UserFilePayload:
    return UserFilePayload(
        profile_image=profile_image,
        aadhaar_copy=aadhaar_copy,
        pan_copy=pan_copy,
        bank_proof=bank_proof,
        education_marksheets=education_marksheets or [],
        education_file_map=_parse_mapping(education_file_map, field_name="education_file_map"),
        experience_proofs=experience_proofs or [],
        company_file_map=_parse_mapping(company_file_map, field_name="company_file_map"),
    )


def _parse_payload(payload: str, *, is_update: bool) -> UserCreateRequest | UserUpdateRequest:
    try:
        if is_update:
            return UserUpdateRequest.model_validate_json(payload)
        return UserCreateRequest.model_validate_json(payload)
    except ValidationError as exc:
        raise BadRequestException(f"Invalid payload: {exc}") from exc


@router.get("/users/me", response_model=UserResponse)
def get_me(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    service = UserService(db)
    return service.get_me(current_user=current_user)


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
    payload: Annotated[str, Form(...)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_roles(RoleEnum.MASTER_ADMIN, RoleEnum.BUSINESS_OWNER, RoleEnum.BUSINESS_ADMIN)),
    ],
    education_file_map: Annotated[str, Form()] = "{}",
    company_file_map: Annotated[str, Form()] = "{}",
    profile_image: Annotated[UploadFile | None, File()] = None,
    aadhaar_copy: Annotated[UploadFile | None, File()] = None,
    pan_copy: Annotated[UploadFile | None, File()] = None,
    bank_proof: Annotated[UploadFile | None, File()] = None,
    education_marksheets: Annotated[list[UploadFile] | None, File()] = None,
    experience_proofs: Annotated[list[UploadFile] | None, File()] = None,
) -> UserResponse:
    create_payload = _parse_payload(payload, is_update=False)
    files_payload = _build_files_payload(
        profile_image=profile_image,
        aadhaar_copy=aadhaar_copy,
        pan_copy=pan_copy,
        bank_proof=bank_proof,
        education_marksheets=education_marksheets,
        education_file_map=education_file_map,
        experience_proofs=experience_proofs,
        company_file_map=company_file_map,
    )
    service = UserService(db)
    return service.create_user(actor=current_user, payload=create_payload, files=files_payload)


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


@router.get("/users/{user_id}/documents/{document_id}")
def preview_user_document(
    user_id: int,
    document_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    service = UserService(db)
    return service.get_document_preview(actor=current_user, user_id=user_id, document_id=document_id)


@router.get("/users/{user_id}/documents/{document_id}/{filename}")
def preview_user_document_by_name(
    user_id: int,
    document_id: int,
    filename: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    _ = filename
    service = UserService(db)
    return service.get_document_preview(actor=current_user, user_id=user_id, document_id=document_id)


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: Annotated[str, Form(...)],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_roles(RoleEnum.MASTER_ADMIN, RoleEnum.BUSINESS_OWNER, RoleEnum.BUSINESS_ADMIN)),
    ],
    education_file_map: Annotated[str, Form()] = "{}",
    company_file_map: Annotated[str, Form()] = "{}",
    profile_image: Annotated[UploadFile | None, File()] = None,
    aadhaar_copy: Annotated[UploadFile | None, File()] = None,
    pan_copy: Annotated[UploadFile | None, File()] = None,
    bank_proof: Annotated[UploadFile | None, File()] = None,
    education_marksheets: Annotated[list[UploadFile] | None, File()] = None,
    experience_proofs: Annotated[list[UploadFile] | None, File()] = None,
) -> UserResponse:
    update_payload = _parse_payload(payload, is_update=True)
    files_payload = _build_files_payload(
        profile_image=profile_image,
        aadhaar_copy=aadhaar_copy,
        pan_copy=pan_copy,
        bank_proof=bank_proof,
        education_marksheets=education_marksheets,
        education_file_map=education_file_map,
        experience_proofs=experience_proofs,
        company_file_map=company_file_map,
    )
    service = UserService(db)
    return service.update_user(actor=current_user, user_id=user_id, payload=update_payload, files=files_payload)


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
