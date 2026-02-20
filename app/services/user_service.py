from sqlalchemy.orm import Session

from app.core.dependencies import ensure_same_business_or_master
from app.core.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException
from app.core.security import hash_password
from app.models.role import RoleEnum
from app.models.user import User
from app.repository.branch_repository import BranchRepository
from app.repository.business_repository import BusinessRepository
from app.repository.role_repository import RoleRepository
from app.repository.user_repository import UserRepository
from app.schemas.user import UserCreateRequest, UserListResponse, UserUpdateRequest


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_repository = UserRepository(db)
        self.business_repository = BusinessRepository(db)
        self.branch_repository = BranchRepository(db)
        self.role_repository = RoleRepository(db)

    def get_me(self, current_user: User) -> User:
        return current_user

    def list_users(self, current_user: User) -> list[User]:
        return self.user_repository.list_for_actor(current_user)

    def list_users_paginated(
        self,
        current_user: User,
        *,
        page: int,
        size: int,
        first_name: str | None = None,
        mobile_number: str | None = None,
        branch_id: int | None = None,
    ) -> UserListResponse:
        items, total = self.user_repository.list_paginated_for_actor(
            current_user,
            page=page,
            size=size,
            first_name=first_name,
            mobile_number=mobile_number,
            branch_id=branch_id,
        )
        total_pages = (total + size - 1) // size if total > 0 else 0
        return UserListResponse(
            items=items,
            page=page,
            size=size,
            total=total,
            total_pages=total_pages,
        )

    def create_user(self, actor: User, payload: UserCreateRequest) -> User:
        target_business_id = self._resolve_actor_business_id(actor)
        self._ensure_business_exists(target_business_id)
        self._ensure_role_exists(payload.role_id)
        self._ensure_branch_exists(payload.branch_id)
        self._ensure_unique_identity_for_create(payload.email, payload.pan, payload.aadhaar, payload.mobile)

        user = User(
            username=payload.email.lower(),
            email=payload.email.lower(),
            first_name=payload.name,
            middle_name=None,
            last_name="",
            password_hash=hash_password(payload.password),
            role=RoleEnum.BUSINESS_EMPLOYEE,
            business_id=target_business_id,
            name=payload.name,
            branch_id=payload.branch_id,
            role_id=payload.role_id,
            salary_type=payload.salary_type,
            salary=payload.salary,
            leave_balance=payload.leave_balance,
            status=payload.status,
            current_address=payload.current_address,
            home_address=payload.home_address,
            pan=payload.pan.upper(),
            aadhaar=payload.aadhaar,
            mobile=payload.mobile,
            number=payload.number,
            father_name=payload.father_name,
            mother_name=payload.mother_name,
        )
        self.user_repository.create(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_user(self, actor: User, user_id: int) -> User:
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise NotFoundException("User not found")
        self._ensure_user_access(actor, user)
        return user

    def update_user(self, actor: User, user_id: int, payload: UserUpdateRequest) -> User:
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise NotFoundException("User not found")
        self._ensure_user_access(actor, user)

        target_business_id = self._resolve_target_business_id(actor, payload.business_id, fallback=user.business_id)
        self._ensure_business_exists(target_business_id)
        self._ensure_role_exists(payload.role_id)
        self._ensure_branch_exists(payload.branch_id)
        self._ensure_unique_identity_for_update(
            user,
            payload.email,
            payload.pan,
            payload.aadhaar,
            payload.mobile,
        )

        user.username = payload.email.lower()
        user.email = payload.email.lower()
        user.first_name = payload.name
        user.name = payload.name
        user.branch_id = payload.branch_id
        user.role_id = payload.role_id
        user.salary_type = payload.salary_type
        user.salary = payload.salary
        user.leave_balance = payload.leave_balance
        user.status = payload.status
        user.current_address = payload.current_address
        user.home_address = payload.home_address
        user.pan = payload.pan.upper()
        user.aadhaar = payload.aadhaar
        user.mobile = payload.mobile
        user.number = payload.number
        user.father_name = payload.father_name
        user.mother_name = payload.mother_name
        user.business_id = target_business_id

        updated_user = self.user_repository.update(user)
        self.db.commit()
        self.db.refresh(updated_user)
        return updated_user

    def delete_user(self, actor: User, user_id: int) -> None:
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise NotFoundException("User not found")
        self._ensure_user_access(actor, user)
        if user.role == RoleEnum.MASTER_ADMIN:
            raise ForbiddenException("Master admin user cannot be deleted")

        self.user_repository.delete(user)
        self.db.commit()

    def _resolve_actor_business_id(self, actor: User) -> int:
        if actor.business_id is None:
            raise BadRequestException("Creator user is not assigned to any business")
        return actor.business_id

    def _ensure_user_access(self, actor: User, target_user: User) -> None:
        if actor.role == RoleEnum.MASTER_ADMIN:
            return
        if actor.role not in {RoleEnum.BUSINESS_OWNER, RoleEnum.BUSINESS_ADMIN}:
            raise ForbiddenException("Not enough permissions")
        ensure_same_business_or_master(actor, target_user.business_id)

    def _resolve_target_business_id(
        self,
        actor: User,
        requested_business_id: int | None,
        fallback: int | None = None,
    ) -> int:
        if actor.role == RoleEnum.MASTER_ADMIN:
            business_id = requested_business_id if requested_business_id is not None else fallback
            if business_id is None:
                raise BadRequestException("business_id is required for master admin")
            return business_id

        if actor.business_id is None:
            raise ForbiddenException("User has no assigned business")

        if requested_business_id is not None and requested_business_id != actor.business_id:
            raise ForbiddenException("Cross-business access is forbidden")
        return actor.business_id

    def _ensure_business_exists(self, business_id: int) -> None:
        if self.business_repository.get_by_id(business_id) is None:
            raise NotFoundException("Business not found")

    def _ensure_role_exists(self, role_id: int) -> None:
        if self.role_repository.get_by_id(role_id) is None:
            raise NotFoundException("Role not found")

    def _ensure_branch_exists(self, branch_id: int) -> None:
        if self.branch_repository.get_by_id(branch_id) is None:
            raise NotFoundException("Branch not found")

    def _ensure_unique_identity_for_create(self, email: str, pan: str, aadhaar: str, mobile: str) -> None:
        if self.user_repository.get_by_email(email.lower()):
            raise ConflictException("Email already exists")
        if self.user_repository.get_by_username(email.lower()):
            raise ConflictException("Username already exists")
        if self.user_repository.get_by_pan(pan.upper()):
            raise ConflictException("PAN already exists")
        if self.user_repository.get_by_aadhaar(aadhaar):
            raise ConflictException("Aadhaar already exists")
        if self.user_repository.get_by_mobile(mobile):
            raise ConflictException("Mobile already exists")

    def _ensure_unique_identity_for_update(
        self,
        current_user: User,
        email: str,
        pan: str,
        aadhaar: str,
        mobile: str,
    ) -> None:
        existing_email = self.user_repository.get_by_email(email.lower())
        if existing_email is not None and existing_email.id != current_user.id:
            raise ConflictException("Email already exists")

        existing_username = self.user_repository.get_by_username(email.lower())
        if existing_username is not None and existing_username.id != current_user.id:
            raise ConflictException("Username already exists")

        existing_pan = self.user_repository.get_by_pan(pan.upper())
        if existing_pan is not None and existing_pan.id != current_user.id:
            raise ConflictException("PAN already exists")

        existing_aadhaar = self.user_repository.get_by_aadhaar(aadhaar)
        if existing_aadhaar is not None and existing_aadhaar.id != current_user.id:
            raise ConflictException("Aadhaar already exists")

        existing_mobile = self.user_repository.get_by_mobile(mobile)
        if existing_mobile is not None and existing_mobile.id != current_user.id:
            raise ConflictException("Mobile already exists")
