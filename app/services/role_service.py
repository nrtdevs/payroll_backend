from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException
from app.models.role_entity import RoleEntity
from app.models.user import User
from app.repository.role_repository import RoleRepository
from app.schemas.role import CreateRoleRequest, RoleListResponse


class RoleService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.role_repository = RoleRepository(db)

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
