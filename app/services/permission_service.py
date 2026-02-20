from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException
from app.models.permission import Permission
from app.models.user import User
from app.repository.permission_repository import PermissionRepository
from app.schemas.permission import (
    CreatePermissionRequest,
    PermissionListResponse,
    UpdatePermissionRequest,
)


class PermissionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.permission_repository = PermissionRepository(db)

    def create_permission(self, actor: User, payload: CreatePermissionRequest) -> Permission:
        normalized_name = payload.permission_name.strip().upper()
        normalized_group = payload.group.strip().upper()
        existing = self.permission_repository.get_by_name_and_group(normalized_name, normalized_group)
        if existing is not None:
            raise ConflictException("Permission already exists in this group")

        permission = self.permission_repository.create(
            permission_name=normalized_name,
            group=normalized_group,
            description=payload.description.strip(),
            created_at=datetime.now().astimezone(),
            created_by=actor.id,
        )
        self.db.commit()
        self.db.refresh(permission)
        return permission

    def list_permissions(self, actor: User) -> list[Permission]:
        _ = actor
        return self.permission_repository.list_all()

    def list_permissions_paginated(
        self,
        actor: User,
        *,
        page: int,
        size: int,
        name: str | None = None,
        group: str | None = None,
    ) -> PermissionListResponse:
        _ = actor
        items, total = self.permission_repository.list_paginated(
            page=page,
            size=size,
            name=name,
            group=group,
        )
        total_pages = (total + size - 1) // size if total > 0 else 0
        return PermissionListResponse(
            items=items,
            page=page,
            size=size,
            total=total,
            total_pages=total_pages,
        )

    def get_permission(self, actor: User, permission_id: int) -> Permission:
        _ = actor
        permission = self.permission_repository.get_by_id(permission_id)
        if permission is None:
            raise NotFoundException("Permission not found")
        return permission

    def update_permission(
        self,
        actor: User,
        permission_id: int,
        payload: UpdatePermissionRequest,
    ) -> Permission:
        _ = actor
        permission = self.permission_repository.get_by_id(permission_id)
        if permission is None:
            raise NotFoundException("Permission not found")

        normalized_name = payload.permission_name.strip().upper()
        normalized_group = payload.group.strip().upper()
        existing = self.permission_repository.get_by_name_and_group(normalized_name, normalized_group)
        if existing is not None and existing.id != permission.id:
            raise ConflictException("Permission already exists in this group")

        permission.permission_name = normalized_name
        permission.group = normalized_group
        permission.description = payload.description.strip()

        updated = self.permission_repository.update(permission)
        self.db.commit()
        self.db.refresh(updated)
        return updated

    def delete_permission(self, actor: User, permission_id: int) -> None:
        _ = actor
        permission = self.permission_repository.get_by_id(permission_id)
        if permission is None:
            raise NotFoundException("Permission not found")

        self.permission_repository.delete(permission)
        self.db.commit()
