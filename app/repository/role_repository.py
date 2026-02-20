from sqlalchemy.orm import Session

from app.models.role_entity import RoleEntity


class RoleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, name: str) -> RoleEntity:
        role = RoleEntity(name=name)
        self.db.add(role)
        self.db.flush()
        self.db.refresh(role)
        return role

    def get_by_id(self, role_id: int) -> RoleEntity | None:
        return self.db.query(RoleEntity).filter(RoleEntity.id == role_id).first()

    def get_by_name(self, name: str) -> RoleEntity | None:
        return self.db.query(RoleEntity).filter(RoleEntity.name == name).first()

    def list_all(self) -> list[RoleEntity]:
        return self.db.query(RoleEntity).order_by(RoleEntity.id.asc()).all()

    def list_paginated(
        self,
        *,
        page: int,
        size: int,
        name: str | None = None,
    ) -> tuple[list[RoleEntity], int]:
        query = self.db.query(RoleEntity)

        if name:
            query = query.filter(RoleEntity.name.ilike(f"%{name.strip()}%"))

        total = query.count()
        items = (
            query.order_by(RoleEntity.id.asc())
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )
        return items, total

    def delete(self, role: RoleEntity) -> None:
        self.db.delete(role)
        self.db.flush()
