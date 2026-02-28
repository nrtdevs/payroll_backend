from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.models.leave_type import LeaveType
from app.models.user import User
from app.repository.leave_type_repository import LeaveTypeRepository
from app.schemas.leave_type import LeaveTypeCreateRequest, LeaveTypeUpdateRequest


class LeaveTypeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.leave_type_repository = LeaveTypeRepository(db)

    def create_leave_type(self, actor: User, payload: LeaveTypeCreateRequest) -> LeaveType:
        _ = actor
        normalized_name = self._normalize_name(payload.name)
        existing = self.leave_type_repository.get_by_name(normalized_name)
        if existing is not None:
            raise ConflictException("Leave type already exists")

        leave_type = self.leave_type_repository.create(
            name=normalized_name,
            description=self._normalize_description(payload.description),
            is_active=payload.is_active,
            proof_required=payload.proof_required,
        )
        self.db.commit()
        self.db.refresh(leave_type)
        return leave_type

    def list_leave_types(self, actor: User) -> list[LeaveType]:
        _ = actor
        return self.leave_type_repository.list_all()

    def get_leave_type(self, actor: User, leave_type_id: int) -> LeaveType:
        _ = actor
        leave_type = self.leave_type_repository.get_by_id(leave_type_id)
        if leave_type is None:
            raise NotFoundException("Leave type not found")
        return leave_type

    def update_leave_type(
        self,
        actor: User,
        leave_type_id: int,
        payload: LeaveTypeUpdateRequest,
    ) -> LeaveType:
        _ = actor
        leave_type = self.leave_type_repository.get_by_id(leave_type_id)
        if leave_type is None:
            raise NotFoundException("Leave type not found")

        normalized_name = self._normalize_name(payload.name)
        existing = self.leave_type_repository.get_by_name(normalized_name)
        if existing is not None and existing.id != leave_type.id:
            raise ConflictException("Leave type already exists")

        updated = self.leave_type_repository.update(
            leave_type,
            name=normalized_name,
            description=self._normalize_description(payload.description),
            is_active=payload.is_active,
            proof_required=payload.proof_required,
        )
        self.db.commit()
        self.db.refresh(updated)
        return updated

    def delete_leave_type(self, actor: User, leave_type_id: int) -> None:
        _ = actor
        leave_type = self.leave_type_repository.get_by_id(leave_type_id)
        if leave_type is None:
            raise NotFoundException("Leave type not found")

        self.leave_type_repository.delete(leave_type)
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
