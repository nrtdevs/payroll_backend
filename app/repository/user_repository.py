from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.models.role import RoleEnum
from app.models.user_education import UserEducation
from app.models.user_previous_company import UserPreviousCompany
from app.models.user import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _default_load_options() -> list[Any]:
        return [
            selectinload(User.educations).selectinload(UserEducation.documents),
            selectinload(User.previous_companies).selectinload(UserPreviousCompany.documents),
            selectinload(User.bank_account),
            selectinload(User.documents),
        ]

    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def get_by_id(self, user_id: int) -> User | None:
        return (
            self.db.query(User)
            .options(*self._default_load_options())
            .filter(User.id == user_id)
            .first()
        )

    def get_by_username(self, username: str) -> User | None:
        return self.db.query(User).filter(User.username == username).first()

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def get_by_pan(self, pan: str) -> User | None:
        return self.db.query(User).filter(User.pan == pan).first()

    def get_by_aadhaar(self, aadhaar: str) -> User | None:
        return self.db.query(User).filter(User.aadhaar == aadhaar).first()

    def get_by_mobile(self, mobile: str) -> User | None:
        return self.db.query(User).filter(User.mobile == mobile).first()

    def get_by_username_or_email(self, login: str) -> User | None:
        return self.db.query(User).filter(or_(User.username == login, User.email == login)).first()

    def list_for_actor(self, actor: User) -> list[User]:
        query = self.db.query(User).options(*self._default_load_options())
        if actor.role == RoleEnum.MASTER_ADMIN:
            return query.order_by(User.id.asc()).all()

        if actor.role in {RoleEnum.BUSINESS_OWNER, RoleEnum.BUSINESS_ADMIN}:
            return (
                query.filter(User.business_id == actor.business_id)
                .order_by(User.id.asc())
                .all()
            )

        return query.filter(User.id == actor.id).order_by(User.id.asc()).all()

    def list_paginated_for_actor(
        self,
        actor: User,
        *,
        page: int,
        size: int,
        first_name: str | None = None,
        mobile_number: str | None = None,
        branch_id: int | None = None,
    ) -> tuple[list[User], int]:
        query = self.db.query(User).options(*self._default_load_options())

        if actor.role == RoleEnum.BUSINESS_OWNER or actor.role == RoleEnum.BUSINESS_ADMIN:
            query = query.filter(User.business_id == actor.business_id)
        elif actor.role != RoleEnum.MASTER_ADMIN:
            query = query.filter(User.id == actor.id)

        if first_name:
            query = query.filter(User.first_name.ilike(f"%{first_name.strip()}%"))
        if mobile_number:
            query = query.filter(User.mobile.ilike(f"%{mobile_number.strip()}%"))
        if branch_id is not None:
            query = query.filter(User.branch_id == branch_id)

        total = query.count()
        items = (
            query.order_by(User.id.asc())
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )
        return items, total

    def update(self, user: User) -> User:
        self.db.flush()
        self.db.refresh(user)
        return user

    def delete(self, user: User) -> None:
        self.db.delete(user)
        self.db.flush()
