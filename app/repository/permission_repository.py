from datetime import datetime

from sqlalchemy.orm import Session

from app.models.permission import Permission


class PermissionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        permission_name: str,
        group: str,
        description: str,
        created_at: datetime,
        created_by: int,
    ) -> Permission:
        permission = Permission(
            permission_name=permission_name,
            group=group,
            description=description,
            created_at=created_at,
            created_by=created_by,
        )
        self.db.add(permission)
        self.db.flush()
        self.db.refresh(permission)
        return permission

    def get_by_id(self, permission_id: int) -> Permission | None:
        return self.db.query(Permission).filter(Permission.id == permission_id).first()

    def get_by_name_and_group(self, permission_name: str, group: str) -> Permission | None:
        return (
            self.db.query(Permission)
            .filter(Permission.permission_name == permission_name, Permission.group == group)
            .first()
        )

    def list_all(self) -> list[Permission]:
        return self.db.query(Permission).order_by(Permission.id.asc()).all()

    def list_paginated(
        self,
        *,
        page: int,
        size: int,
        name: str | None = None,
        group: str | None = None,
    ) -> tuple[list[Permission], int]:
        query = self.db.query(Permission)

        if name:
            query = query.filter(Permission.permission_name.ilike(f"%{name.strip()}%"))
        if group:
            query = query.filter(Permission.group.ilike(f"%{group.strip()}%"))

        total = query.count()
        items = (
            query.order_by(Permission.id.asc())
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )
        return items, total

    def update(self, permission: Permission) -> Permission:
        self.db.flush()
        self.db.refresh(permission)
        return permission

    def delete(self, permission: Permission) -> None:
        self.db.delete(permission)
        self.db.flush()
