from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.permission import Permission
from app.models.role_entity import RoleEntity
from app.models.role_permission import RolePermission


class RolePermissionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def replace_role_permissions(self, role_id: int, permission_ids: list[int]) -> None:
        self.db.query(RolePermission).filter(RolePermission.role_id == role_id).delete(
            synchronize_session=False
        )
        if permission_ids:
            self.db.add_all(
                [
                    RolePermission(role_id=role_id, permission_id=permission_id)
                    for permission_id in permission_ids
                ]
            )
        self.db.flush()

    def list_permissions_for_role(
        self,
        role_id: int,
        *,
        page: int | None = None,
        size: int | None = None,
    ) -> tuple[list[Permission], int]:
        query = (
            self.db.query(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .filter(RolePermission.role_id == role_id)
        )
        total = query.count()
        if page is None and size is None:
            items = query.order_by(Permission.id.asc()).all()
            return items, total

        effective_page = page if page is not None else 1
        effective_size = size if size is not None else 10
        items = (
            query.order_by(Permission.id.asc())
            .offset((effective_page - 1) * effective_size)
            .limit(effective_size)
            .all()
        )
        return items, total

    def remove_permission_from_role(self, role_id: int, permission_id: int) -> bool:
        deleted = (
            self.db.query(RolePermission)
            .filter(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == permission_id,
            )
            .delete(synchronize_session=False)
        )
        self.db.flush()
        return deleted > 0

    def list_roles_with_permission_count(
        self,
        *,
        page: int,
        size: int,
        name: str | None = None,
    ) -> tuple[list[tuple[RoleEntity, int]], int]:
        total_query = self.db.query(RoleEntity)
        if name:
            total_query = total_query.filter(RoleEntity.name.ilike(f"%{name.strip()}%"))
        total = total_query.count()

        query = self.db.query(
            RoleEntity,
            func.count(RolePermission.permission_id).label("permission_count"),
        ).outerjoin(RolePermission, RolePermission.role_id == RoleEntity.id)

        if name:
            query = query.filter(RoleEntity.name.ilike(f"%{name.strip()}%"))

        items = (
            query.group_by(RoleEntity.id)
            .order_by(RoleEntity.id.asc())
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )
        return items, total

    def has_permission_for_role(self, *, role_id: int, permission_name: str) -> bool:
        return (
            self.db.query(RolePermission)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .filter(
                RolePermission.role_id == role_id,
                Permission.permission_name == permission_name,
            )
            .first()
            is not None
        )
