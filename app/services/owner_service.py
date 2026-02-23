from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException
from app.core.security import hash_password
from app.models.role import RoleEnum
from app.models.user import User
from app.repository.business_repository import BusinessRepository
from app.repository.user_repository import UserRepository
from app.schemas.user import CreateOwnerRequest


class OwnerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.business_repository = BusinessRepository(db)
        self.user_repository = UserRepository(db)

    def create_owner_with_business(self, actor: User, payload: CreateOwnerRequest) -> User:
        if self.user_repository.get_by_username(payload.username):
            raise ConflictException("Username already exists")
        if self.user_repository.get_by_email(payload.email):
            raise ConflictException("Email already exists")

        business = self.business_repository.create(name=payload.business_name)

        owner = User(
            username=payload.username,
            email=payload.email,
            first_name=payload.first_name,
            middle_name=payload.middle_name,
            last_name=payload.last_name,
            password_hash=hash_password(payload.password),
            role=RoleEnum.BUSINESS_OWNER,
            business_id=business.id,
        )
        self.user_repository.create(owner)
        self.db.commit()
        self.db.refresh(owner)
        return owner
