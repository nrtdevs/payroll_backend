from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission, require_roles
from app.models.role import RoleEnum
from app.models.user import User
from app.schemas.branch import (
    BranchCreateRequest,
    BranchListResponse,
    BranchResponse,
    BranchUpdateRequest,
)
from app.schemas.designation import (
    DesignationCreateRequest,
    DesignationResponse,
    DesignationUpdateRequest,
)
from app.schemas.employment_type import (
    EmploymentTypeCreateRequest,
    EmploymentTypeResponse,
    EmploymentTypeUpdateRequest,
)
from app.schemas.leave_type import (
    LeaveTypeCreateRequest,
    LeaveTypeResponse,
    LeaveTypeUpdateRequest,
)
from app.schemas.leave_master import (
    LeaveMasterBulkUpdateRequest,
    LeaveMasterCreateRequest,
    LeaveMasterGroupedResponse,
    LeaveMasterResponse,
    LeaveMasterUpdateRequest,
)
from app.schemas.permission import (
    CreatePermissionRequest,
    PermissionListResponse,
    PermissionResponse,
    UpdatePermissionRequest,
)
from app.schemas.role import CreateRoleRequest, RoleListResponse, RoleResponse
from app.schemas.role_permission import AssignRolePermissionsRequest, RolePermissionCountListResponse, RolePermissionsResponse
from app.schemas.user import CreateOwnerRequest, UserResponse
from app.services.branch_service import BranchService
from app.services.owner_service import OwnerService
from app.services.permission_service import PermissionService
from app.services.role_service import RoleService
from app.services.employment_type_service import EmploymentTypeService
from app.services.designation_service import DesignationService
from app.services.leave_type_service import LeaveTypeService
from app.services.leave_master_service import LeaveMasterService


router = APIRouter(tags=["Master Admin"])


@router.post("/owners", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_owner(
    payload: CreateOwnerRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> UserResponse:
    service = OwnerService(db)
    return service.create_owner_with_business(actor=current_user, payload=payload)


@router.post("/branches", response_model=BranchResponse, status_code=status.HTTP_201_CREATED)
def create_branch(
    payload: BranchCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> BranchResponse:
    service = BranchService(db)
    return service.create_branch(actor=current_user, payload=payload)


@router.get("/branches", response_model=list[BranchResponse])
def list_branches(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> list[BranchResponse]:
    service = BranchService(db)
    return service.list_branches(actor=current_user)


@router.get("/branches/paginated", response_model=BranchListResponse)
def list_branches_paginated(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    name: str | None = Query(default=None),
    city: str | None = Query(default=None),
    state: str | None = Query(default=None),
    country: str | None = Query(default=None),
) -> BranchListResponse:
    service = BranchService(db)
    return service.list_branches_paginated(
        actor=current_user,
        page=page,
        size=size,
        name=name,
        city=city,
        state=state,
        country=country,
    )


@router.get("/branches/{branch_id}", response_model=BranchResponse)
def get_branch(
    branch_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> BranchResponse:
    service = BranchService(db)
    return service.get_branch(actor=current_user, branch_id=branch_id)


@router.put("/branches/{branch_id}", response_model=BranchResponse)
def update_branch(
    branch_id: int,
    payload: BranchUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> BranchResponse:
    service = BranchService(db)
    return service.update_branch(actor=current_user, branch_id=branch_id, payload=payload)


@router.delete("/branches/{branch_id}", status_code=status.HTTP_200_OK)
def delete_branch(
    branch_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> dict[str, str]:
    service = BranchService(db)
    service.delete_branch(actor=current_user, branch_id=branch_id)
    return {"detail": "Branch successfully deleted"}


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: CreateRoleRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> RoleResponse:
    service = RoleService(db)
    return service.create_role(actor=current_user, payload=payload)


@router.get("/roles", response_model=list[RoleResponse] | RolePermissionCountListResponse)
def list_roles(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
    include_permission_count: bool = Query(default=False, alias="includePermissionCount"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    name: str | None = Query(default=None),
) -> list[RoleResponse] | RolePermissionCountListResponse:
    service = RoleService(db)
    if include_permission_count:
        return service.list_roles_with_permission_count(
            actor=current_user,
            page=page,
            size=size,
            name=name,
        )
    return service.list_roles(actor=current_user)


@router.get(
    "/roles/permission-count",
    response_model=RolePermissionCountListResponse,
)
def list_roles_with_permission_count(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    name: str | None = Query(default=None),
) -> RolePermissionCountListResponse:
    service = RoleService(db)
    return service.list_roles_with_permission_count(
        actor=current_user,
        page=page,
        size=size,
        name=name,
    )


@router.get("/roles/paginated", response_model=RoleListResponse)
def list_roles_paginated(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    name: str | None = Query(default=None),
) -> RoleListResponse:
    service = RoleService(db)
    return service.list_roles_paginated(
        actor=current_user,
        page=page,
        size=size,
        name=name,
    )


@router.get("/roles/{role_id}", response_model=RoleResponse)
def get_role(
    role_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> RoleResponse:
    service = RoleService(db)
    return service.get_role(actor=current_user, role_id=role_id)


@router.post("/roles/{role_id}/permissions", response_model=RolePermissionsResponse)
def assign_permissions_to_role(
    role_id: int,
    payload: AssignRolePermissionsRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> RolePermissionsResponse:
    service = RoleService(db)
    return service.assign_permissions(actor=current_user, role_id=role_id, payload=payload)


@router.get("/roles/{role_id}/permissions", response_model=RolePermissionsResponse)
def get_role_permissions(
    role_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
    page: int | None = Query(default=None, ge=1),
    size: int | None = Query(default=None, ge=1, le=100),
) -> RolePermissionsResponse:
    service = RoleService(db)
    return service.get_role_permissions(actor=current_user, role_id=role_id, page=page, size=size)


@router.delete("/roles/{role_id}/permissions/{permission_id}", status_code=status.HTTP_200_OK)
def remove_permission_from_role(
    role_id: int,
    permission_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> dict[str, str]:
    service = RoleService(db)
    service.remove_permission(actor=current_user, role_id=role_id, permission_id=permission_id)
    return {"detail": "Permission removed from role successfully"}


@router.delete("/roles/{role_id}", status_code=status.HTTP_200_OK)
def delete_role(
    role_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> dict[str, str]:
    service = RoleService(db)
    service.delete_role(actor=current_user, role_id=role_id)
    return {"detail": "Role successfully deleted"}


@router.post("/permissions", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
def create_permission(
    payload: CreatePermissionRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> PermissionResponse:
    service = PermissionService(db)
    return service.create_permission(actor=current_user, payload=payload)


@router.get("/permissions", response_model=list[PermissionResponse])
def list_permissions(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> list[PermissionResponse]:
    service = PermissionService(db)
    return service.list_permissions(actor=current_user)


@router.get("/permissions/paginated", response_model=PermissionListResponse)
def list_permissions_paginated(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    name: str | None = Query(default=None),
    group: str | None = Query(default=None),
) -> PermissionListResponse:
    service = PermissionService(db)
    return service.list_permissions_paginated(
        actor=current_user,
        page=page,
        size=size,
        name=name,
        group=group,
    )


@router.get("/permissions/{permission_id}", response_model=PermissionResponse)
def get_permission(
    permission_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> PermissionResponse:
    service = PermissionService(db)
    return service.get_permission(actor=current_user, permission_id=permission_id)


@router.put("/permissions/{permission_id}", response_model=PermissionResponse)
def update_permission(
    permission_id: int,
    payload: UpdatePermissionRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> PermissionResponse:
    service = PermissionService(db)
    return service.update_permission(actor=current_user, permission_id=permission_id, payload=payload)


@router.delete("/permissions/{permission_id}", status_code=status.HTTP_200_OK)
def delete_permission(
    permission_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> dict[str, str]:
    service = PermissionService(db)
    service.delete_permission(actor=current_user, permission_id=permission_id)
    return {"detail": "Permission successfully deleted"}


@router.post(
    "/employment-types",
    response_model=EmploymentTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_employment_type(
    payload: EmploymentTypeCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission("EMPLOYMENT_TYPE_CREATE"))],
) -> EmploymentTypeResponse:
    service = EmploymentTypeService(db)
    return service.create_employment_type(actor=current_user, payload=payload)


@router.get("/employment-types", response_model=list[EmploymentTypeResponse])
def list_employment_types(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> list[EmploymentTypeResponse]:
    service = EmploymentTypeService(db)
    return service.list_employment_types(actor=current_user)


@router.get("/employment-types/{employment_type_id}", response_model=EmploymentTypeResponse)
def get_employment_type(
    employment_type_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> EmploymentTypeResponse:
    service = EmploymentTypeService(db)
    return service.get_employment_type(actor=current_user, employment_type_id=employment_type_id)


@router.put("/employment-types/{employment_type_id}", response_model=EmploymentTypeResponse)
def update_employment_type(
    employment_type_id: int,
    payload: EmploymentTypeUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission("EMPLOYMENT_TYPE_UPDATE"))],
) -> EmploymentTypeResponse:
    service = EmploymentTypeService(db)
    return service.update_employment_type(
        actor=current_user,
        employment_type_id=employment_type_id,
        payload=payload,
    )


@router.delete("/employment-types/{employment_type_id}", status_code=status.HTTP_200_OK)
def delete_employment_type(
    employment_type_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission("EMPLOYMENT_TYPE_DELETE"))],
) -> dict[str, str]:
    service = EmploymentTypeService(db)
    service.delete_employment_type(actor=current_user, employment_type_id=employment_type_id)
    return {"detail": "Employment type successfully deleted"}


@router.post("/designations", response_model=DesignationResponse, status_code=status.HTTP_201_CREATED)
def create_designation(
    payload: DesignationCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission("DESIGNATION_CREATE"))],
) -> DesignationResponse:
    service = DesignationService(db)
    return service.create_designation(actor=current_user, payload=payload)


@router.get("/designations", response_model=list[DesignationResponse])
def list_designations(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> list[DesignationResponse]:
    service = DesignationService(db)
    return service.list_designations(actor=current_user)


@router.get("/designations/{designation_id}", response_model=DesignationResponse)
def get_designation(
    designation_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> DesignationResponse:
    service = DesignationService(db)
    return service.get_designation(actor=current_user, designation_id=designation_id)


@router.put("/designations/{designation_id}", response_model=DesignationResponse)
def update_designation(
    designation_id: int,
    payload: DesignationUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission("DESIGNATION_UPDATE"))],
) -> DesignationResponse:
    service = DesignationService(db)
    return service.update_designation(
        actor=current_user,
        designation_id=designation_id,
        payload=payload,
    )


@router.delete("/designations/{designation_id}", status_code=status.HTTP_200_OK)
def delete_designation(
    designation_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permission("DESIGNATION_DELETE"))],
) -> dict[str, str]:
    service = DesignationService(db)
    service.delete_designation(actor=current_user, designation_id=designation_id)
    return {"detail": "Designation successfully deleted"}


@router.post("/leave-types", response_model=LeaveTypeResponse, status_code=status.HTTP_201_CREATED)
def create_leave_type(
    payload: LeaveTypeCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> LeaveTypeResponse:
    service = LeaveTypeService(db)
    return service.create_leave_type(actor=current_user, payload=payload)


@router.get("/leave-types", response_model=list[LeaveTypeResponse])
def list_leave_types(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> list[LeaveTypeResponse]:
    service = LeaveTypeService(db)
    return service.list_leave_types(actor=current_user)


@router.get("/leave-types/{leave_type_id}", response_model=LeaveTypeResponse)
def get_leave_type(
    leave_type_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> LeaveTypeResponse:
    service = LeaveTypeService(db)
    return service.get_leave_type(actor=current_user, leave_type_id=leave_type_id)


@router.put("/leave-types/{leave_type_id}", response_model=LeaveTypeResponse)
def update_leave_type(
    leave_type_id: int,
    payload: LeaveTypeUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> LeaveTypeResponse:
    service = LeaveTypeService(db)
    return service.update_leave_type(
        actor=current_user,
        leave_type_id=leave_type_id,
        payload=payload,
    )


@router.delete("/leave-types/{leave_type_id}", status_code=status.HTTP_200_OK)
def delete_leave_type(
    leave_type_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> dict[str, str]:
    service = LeaveTypeService(db)
    service.delete_leave_type(actor=current_user, leave_type_id=leave_type_id)
    return {"detail": "Leave type successfully deleted"}


@router.post("/leave-masters", response_model=LeaveMasterGroupedResponse, status_code=status.HTTP_201_CREATED)
def create_leave_master(
    payload: LeaveMasterCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> LeaveMasterGroupedResponse:
    service = LeaveMasterService(db)
    return service.create_leave_master(actor=current_user, payload=payload)


@router.get("/leave-masters", response_model=list[LeaveMasterGroupedResponse])
def list_leave_masters(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> list[LeaveMasterGroupedResponse]:
    service = LeaveMasterService(db)
    return service.list_leave_masters(actor=current_user)


@router.get("/leave-masters/{leave_master_id}", response_model=LeaveMasterResponse)
def get_leave_master(
    leave_master_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> LeaveMasterResponse:
    service = LeaveMasterService(db)
    return service.get_leave_master(actor=current_user, leave_master_id=leave_master_id)


@router.put("/leave-masters/{leave_master_id}", response_model=LeaveMasterGroupedResponse)
def update_leave_master(
    leave_master_id: int,
    payload: LeaveMasterUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> LeaveMasterGroupedResponse:
    service = LeaveMasterService(db)
    return service.update_leave_master(
        actor=current_user,
        leave_master_id=leave_master_id,
        payload=payload,
    )


@router.put("/leave-masters", response_model=LeaveMasterGroupedResponse)
def update_leave_masters_bulk(
    payload: LeaveMasterBulkUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> LeaveMasterGroupedResponse:
    service = LeaveMasterService(db)
    return service.update_leave_masters_bulk(actor=current_user, payload=payload)


@router.delete("/leave-masters/{leave_master_id}", response_model=LeaveMasterGroupedResponse, status_code=status.HTTP_200_OK)
def delete_leave_master(
    leave_master_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(RoleEnum.MASTER_ADMIN))],
) -> LeaveMasterGroupedResponse:
    service = LeaveMasterService(db)
    return service.delete_leave_master(actor=current_user, leave_master_id=leave_master_id)
