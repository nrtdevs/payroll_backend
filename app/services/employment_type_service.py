from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.models.employment_type import EmploymentType
from app.models.user import User
from app.repository.employment_type_repository import EmploymentTypeRepository
from app.schemas.employment_type import EmploymentTypeCreateRequest, EmploymentTypeUpdateRequest


class EmploymentTypeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.employment_type_repository = EmploymentTypeRepository(db)

    def create_employment_type(
        self,
        actor: User,
        payload: EmploymentTypeCreateRequest,
    ) -> EmploymentType:
        _ = actor
        normalized_name = self._normalize_name(payload.name)
        existing = self.employment_type_repository.get_by_name(normalized_name)
        if existing is not None:
            raise ConflictException("Employment type already exists")

        employment_type = self.employment_type_repository.create(name=normalized_name)
        self.db.commit()
        self.db.refresh(employment_type)
        return employment_type

    def list_employment_types(self, actor: User) -> list[EmploymentType]:
        _ = actor
        return self.employment_type_repository.list_all()

    def get_employment_type(self, actor: User, employment_type_id: int) -> EmploymentType:
        _ = actor
        employment_type = self.employment_type_repository.get_by_id(employment_type_id)
        if employment_type is None:
            raise NotFoundException("Employment type not found")
        return employment_type

    def update_employment_type(
        self,
        actor: User,
        employment_type_id: int,
        payload: EmploymentTypeUpdateRequest,
    ) -> EmploymentType:
        _ = actor
        employment_type = self.employment_type_repository.get_by_id(employment_type_id)
        if employment_type is None:
            raise NotFoundException("Employment type not found")

        normalized_name = self._normalize_name(payload.name)
        existing = self.employment_type_repository.get_by_name(normalized_name)
        if existing is not None and existing.id != employment_type.id:
            raise ConflictException("Employment type already exists")

        updated = self.employment_type_repository.update(employment_type, name=normalized_name)
        self.db.commit()
        self.db.refresh(updated)
        return updated

    def delete_employment_type(self, actor: User, employment_type_id: int) -> None:
        _ = actor
        employment_type = self.employment_type_repository.get_by_id(employment_type_id)
        if employment_type is None:
            raise NotFoundException("Employment type not found")

        self.employment_type_repository.delete(employment_type)
        self.db.commit()

    @staticmethod
    def _normalize_name(name: str) -> str:
        normalized = name.strip()
        if not normalized:
            raise BadRequestException("name cannot be empty")
        return normalized
