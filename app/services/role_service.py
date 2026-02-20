from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException
from app.models.permission import Permission
from app.models.role_entity import RoleEntity
from app.models.user import User
from app.repository.permission_repository import PermissionRepository
from app.repository.role_repository import RoleRepository
from app.repository.role_permission_repository import RolePermissionRepository
from app.schemas.role_permission import (
    AssignRolePermissionsRequest,
    RolePermissionCountItemResponse,
    RolePermissionCountListResponse,
    RolePermissionItemResponse,
    RolePermissionsResponse,
)
from app.schemas.role import CreateRoleRequest, RoleListResponse


class RoleService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.role_repository = RoleRepository(db)
        self.permission_repository = PermissionRepository(db)
        self.role_permission_repository = RolePermissionRepository(db)

    def create_role(self, actor: User, payload: CreateRoleRequest) -> RoleEntity:
        normalized_name = payload.name.strip().upper()
        if self.role_repository.get_by_name(normalized_name):
            raise ConflictException("Role already exists")

        role = self.role_repository.create(normalized_name)
        self.db.commit()
        self.db.refresh(role)
        return role

    def list_roles(self, actor: User) -> list[RoleEntity]:
        return self.role_repository.list_all()

    def list_roles_paginated(
        self,
        actor: User,
        *,
        page: int,
        size: int,
        name: str | None = None,
    ) -> RoleListResponse:
        _ = actor
        items, total = self.role_repository.list_paginated(page=page, size=size, name=name)
        total_pages = (total + size - 1) // size if total > 0 else 0
        return RoleListResponse(
            items=items,
            page=page,
            size=size,
            total=total,
            total_pages=total_pages,
        )

    def get_role(self, actor: User, role_id: int) -> RoleEntity:
        role = self.role_repository.get_by_id(role_id)
        if role is None:
            raise NotFoundException("Role not found")
        return role

    def delete_role(self, actor: User, role_id: int) -> None:
        role = self.role_repository.get_by_id(role_id)
        if role is None:
            raise NotFoundException("Role not found")
        self.role_repository.delete(role)
        self.db.commit()

    def assign_permissions(
        self,
        actor: User,
        role_id: int,
        payload: AssignRolePermissionsRequest,
    ) -> RolePermissionsResponse:
        _ = actor
        role = self.role_repository.get_by_id(role_id)
        if role is None:
            raise NotFoundException("Role not found")

        permission_ids = list(dict.fromkeys(payload.permission_ids))
        permissions = self._validate_permission_ids(permission_ids)

        try:
            self.role_permission_repository.replace_role_permissions(role_id, permission_ids)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        mapped_permissions = self._to_permission_items(permissions)
        total = len(mapped_permissions)
        return RolePermissionsResponse(
            role_id=role.id,
            role_name=role.name,
            permissions=mapped_permissions,
            page=1,
            size=total if total > 0 else 1,
            total=total,
            total_pages=1 if total > 0 else 0,
        )

    def get_role_permissions(
        self,
        actor: User,
        role_id: int,
        *,
        page: int | None = None,
        size: int | None = None,
    ) -> RolePermissionsResponse:
        _ = actor
        role = self.role_repository.get_by_id(role_id)
        if role is None:
            raise NotFoundException("Role not found")

        permissions, total = self.role_permission_repository.list_permissions_for_role(
            role_id,
            page=page,
            size=size,
        )
        if page is None and size is None:
            response_page = 1
            response_size = total
            total_pages = 1 if total > 0 else 0
        else:
            response_page = page if page is not None else 1
            response_size = size if size is not None else 10
            total_pages = (total + response_size - 1) // response_size if total > 0 else 0

        return RolePermissionsResponse(
            role_id=role.id,
            role_name=role.name,
            permissions=self._to_permission_items(permissions),
            page=response_page,
            size=response_size,
            total=total,
            total_pages=total_pages,
        )

    def remove_permission(
        self,
        actor: User,
        role_id: int,
        permission_id: int,
    ) -> None:
        _ = actor
        role = self.role_repository.get_by_id(role_id)
        if role is None:
            raise NotFoundException("Role not found")

        permission = self.permission_repository.get_by_id(permission_id)
        if permission is None:
            raise NotFoundException("Permission not found")

        deleted = self.role_permission_repository.remove_permission_from_role(role_id, permission_id)
        if not deleted:
            raise NotFoundException("Permission is not assigned to this role")

        self.db.commit()

    def list_roles_with_permission_count(
        self,
        actor: User,
        *,
        page: int,
        size: int,
        name: str | None = None,
    ) -> RolePermissionCountListResponse:
        _ = actor
        items, total = self.role_permission_repository.list_roles_with_permission_count(
            page=page,
            size=size,
            name=name,
        )
        total_pages = (total + size - 1) // size if total > 0 else 0
        return RolePermissionCountListResponse(
            items=[
                RolePermissionCountItemResponse(
                    id=role.id,
                    name=role.name,
                    created_at=role.created_at,
                    permission_count=permission_count,
                )
                for role, permission_count in items
            ],
            page=page,
            size=size,
            total=total,
            total_pages=total_pages,
        )

    def _validate_permission_ids(self, permission_ids: list[int]) -> list[Permission]:
        if not permission_ids:
            return []

        permissions = self.permission_repository.list_by_ids(permission_ids)
        found_ids = {permission.id for permission in permissions}
        missing_ids = [permission_id for permission_id in permission_ids if permission_id not in found_ids]
        if missing_ids:
            raise NotFoundException(f"Permissions not found: {missing_ids}")
        return permissions

    def _to_permission_items(
        self,
        permissions: list[Permission],
    ) -> list[RolePermissionItemResponse]:
        return [
            RolePermissionItemResponse(
                id=permission.id,
                name=permission.permission_name,
                group=permission.group,
            )
            for permission in permissions
        ]
