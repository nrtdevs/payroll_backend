from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.models.designation import Designation
from app.models.user import User
from app.repository.designation_repository import DesignationRepository
from app.repository.user_repository import UserRepository
from app.schemas.designation import DesignationCreateRequest, DesignationUpdateRequest


class DesignationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.designation_repository = DesignationRepository(db)
        self.user_repository = UserRepository(db)

    def create_designation(self, actor: User, payload: DesignationCreateRequest) -> Designation:
        _ = actor
        normalized_name = self._normalize_name(payload.name)
        existing = self.designation_repository.get_by_name(normalized_name)
        if existing is not None:
            raise ConflictException("Designation already exists")

        designation = self.designation_repository.create(
            name=normalized_name,
            description=self._normalize_description(payload.description),
            is_active=payload.is_active,
        )
        self.db.commit()
        self.db.refresh(designation)
        return designation

    def list_designations(self, actor: User) -> list[Designation]:
        _ = actor
        return self.designation_repository.list_all()

    def get_designation(self, actor: User, designation_id: int) -> Designation:
        _ = actor
        designation = self.designation_repository.get_by_id(designation_id)
        if designation is None:
            raise NotFoundException("Designation not found")
        return designation

    def update_designation(
        self,
        actor: User,
        designation_id: int,
        payload: DesignationUpdateRequest,
    ) -> Designation:
        _ = actor
        designation = self.designation_repository.get_by_id(designation_id)
        if designation is None:
            raise NotFoundException("Designation not found")

        normalized_name = self._normalize_name(payload.name)
        existing = self.designation_repository.get_by_name(normalized_name)
        if existing is not None and existing.id != designation.id:
            raise ConflictException("Designation already exists")

        updated = self.designation_repository.update(
            designation,
            name=normalized_name,
            description=self._normalize_description(payload.description),
            is_active=payload.is_active,
        )
        self.db.commit()
        self.db.refresh(updated)
        return updated

    def delete_designation(self, actor: User, designation_id: int) -> None:
        _ = actor
        designation = self.designation_repository.get_by_id(designation_id)
        if designation is None:
            raise NotFoundException("Designation not found")

        assigned_user_count = self.user_repository.count_by_designation_id(designation_id)
        if assigned_user_count > 0:
            raise ConflictException("Cannot delete designation because it is assigned to users")

        self.designation_repository.delete(designation)
        self.db.commit()

    @staticmethod
    def _normalize_name(name: str) -> str:
        normalized = name.strip()
        if not normalized:
            raise BadRequestException("name cannot be empty")
        return normalized

    @staticmethod
    def _normalize_description(description: str | None) -> str | None:
        if description is None:
            return None
        normalized = description.strip()
        return normalized or None
