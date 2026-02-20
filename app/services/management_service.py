from sqlalchemy.orm import Session

from app.core.dependencies import ensure_same_business_or_master
from app.core.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException
from app.core.security import hash_password
from app.models.role import RoleEnum
from app.models.user import User
from app.repository.business_repository import BusinessRepository
from app.repository.user_repository import UserRepository
from app.schemas.user import CreateAdminRequest, CreateEmployeeRequest


class ManagementService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.business_repository = BusinessRepository(db)
        self.user_repository = UserRepository(db)

    def create_admin(self, actor: User, payload: CreateAdminRequest) -> User:
        if actor.role not in {RoleEnum.MASTER_ADMIN, RoleEnum.BUSINESS_OWNER}:
            raise ForbiddenException("Only master admin or business owner can create business admins")

        target_business_id = self._resolve_target_business_id(actor=actor, requested_business_id=payload.business_id)
        self._ensure_business_exists(target_business_id)
        self._ensure_unique_identity(payload.username, payload.email)

        user = User(
            username=payload.username,
            email=payload.email,
            first_name=payload.first_name,
            middle_name=payload.middle_name,
            last_name=payload.last_name,
            password_hash=hash_password(payload.password),
            role=RoleEnum.BUSINESS_ADMIN,
            business_id=target_business_id,
        )
        self.user_repository.create(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def create_employee(self, actor: User, payload: CreateEmployeeRequest) -> User:
        if actor.role not in {
            RoleEnum.MASTER_ADMIN,
            RoleEnum.BUSINESS_OWNER,
            RoleEnum.BUSINESS_ADMIN,
        }:
            raise ForbiddenException("Only master admin, business owner, or business admin can create employees")

        target_business_id = self._resolve_target_business_id(actor=actor, requested_business_id=payload.business_id)
        self._ensure_business_exists(target_business_id)
        self._ensure_unique_identity(payload.username, payload.email)

        user = User(
            username=payload.username,
            email=payload.email,
            first_name=payload.first_name,
            middle_name=payload.middle_name,
            last_name=payload.last_name,
            password_hash=hash_password(payload.password),
            role=RoleEnum.BUSINESS_EMPLOYEE,
            business_id=target_business_id,
        )
        self.user_repository.create(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def _resolve_target_business_id(self, actor: User, requested_business_id: int | None) -> int:
        if actor.role == RoleEnum.MASTER_ADMIN:
            if requested_business_id is None:
                raise BadRequestException("business_id is required for master admin")
            return requested_business_id

        if actor.business_id is None:
            raise ForbiddenException("User has no assigned business")
        ensure_same_business_or_master(actor, actor.business_id)
        return actor.business_id

    def _ensure_business_exists(self, business_id: int) -> None:
        if self.business_repository.get_by_id(business_id) is None:
            raise NotFoundException("Business not found")

    def _ensure_unique_identity(self, username: str, email: str) -> None:
        if self.user_repository.get_by_username(username):
            raise ConflictException("Username already exists")
        if self.user_repository.get_by_email(email):
            raise ConflictException("Email already exists")
