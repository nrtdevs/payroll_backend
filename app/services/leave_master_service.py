from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.models.leave_type import LeaveType
from app.models.leave_master import LeaveMaster
from app.models.user import User
from app.repository.employment_type_repository import EmploymentTypeRepository
from app.repository.leave_master_repository import LeaveMasterRepository
from app.repository.leave_type_repository import LeaveTypeRepository
from app.schemas.leave_master import (
    LeaveMasterBulkUpdateRequest,
    LeaveMasterCreateRequest,
    LeaveMasterGroupedLeaveItemResponse,
    LeaveMasterGroupedResponse,
    LeaveMasterResponse,
    LeaveMasterUpdateRequest,
)


class LeaveMasterService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.leave_master_repository = LeaveMasterRepository(db)
        self.employment_type_repository = EmploymentTypeRepository(db)
        self.leave_type_repository = LeaveTypeRepository(db)

    def create_leave_master(self, actor: User, payload: LeaveMasterCreateRequest) -> LeaveMasterGroupedResponse:
        _ = actor
        self._ensure_employment_type_exists(payload.employment_type_id)
        seen_leave_type_ids: set[int] = set()
        resolved_leave_types: dict[int, LeaveType] = {}

        for item in payload.leaves:
            self._validate_total_leave_days(item.total_leave_days)
            if item.leave_type_id in seen_leave_type_ids:
                raise ConflictException(
                    f"Duplicate leave_type_id in request: {item.leave_type_id}"
                )
            seen_leave_type_ids.add(item.leave_type_id)
            leave_type = self._ensure_leave_type_exists(item.leave_type_id)
            resolved_leave_types[item.leave_type_id] = leave_type
            self._ensure_unique_combination(payload.employment_type_id, item.leave_type_id)

        created_ids: list[int] = []
        for item in payload.leaves:
            leave_master = self.leave_master_repository.create(
                employment_type_id=payload.employment_type_id,
                leave_type_id=item.leave_type_id,
                total_leave_days=item.total_leave_days,
                proof_required=resolved_leave_types[item.leave_type_id].proof_required,
            )
            created_ids.append(leave_master.id)

        self.db.commit()

        loaded_items: list[LeaveMaster] = []
        for leave_master_id in created_ids:
            loaded = self.leave_master_repository.get_by_id(leave_master_id)
            if loaded is None:
                raise NotFoundException("Leave master not found")
            loaded_items.append(loaded)
        grouped = self._group_by_employment_type(loaded_items)
        return grouped[0]

    def list_leave_masters(self, actor: User) -> list[LeaveMasterGroupedResponse]:
        _ = actor
        items = self.leave_master_repository.list_all()
        return self._group_by_employment_type(items)

    def get_leave_master(self, actor: User, leave_master_id: int) -> LeaveMasterResponse:
        _ = actor
        leave_master = self.leave_master_repository.get_by_id(leave_master_id)
        if leave_master is None:
            raise NotFoundException("Leave master not found")
        return self._to_response(leave_master)

    def update_leave_master(
        self,
        actor: User,
        leave_master_id: int,
        payload: LeaveMasterUpdateRequest,
    ) -> LeaveMasterGroupedResponse:
        _ = actor
        self._validate_total_leave_days(payload.total_leave_days)
        leave_master = self.leave_master_repository.get_by_id(leave_master_id)
        if leave_master is None:
            raise NotFoundException("Leave master not found")

        updated = self.leave_master_repository.update_total_days(
            leave_master,
            total_leave_days=payload.total_leave_days,
        )
        self.db.commit()
        self.db.refresh(updated)
        items = self.leave_master_repository.list_by_employment_type_id(updated.employment_type_id)
        grouped = self._group_by_employment_type(items)
        if not grouped:
            raise NotFoundException("Leave master not found")
        return grouped[0]

    def update_leave_masters_bulk(
        self,
        actor: User,
        payload: LeaveMasterBulkUpdateRequest,
    ) -> LeaveMasterGroupedResponse:
        _ = actor
        self._ensure_employment_type_exists(payload.employment_type_id)
        seen_leave_type_ids: set[int] = set()
        resolved_leave_types: dict[int, LeaveType] = {}
        existing_mappings: dict[int, LeaveMaster] = {}

        for item in payload.leaves:
            self._validate_total_leave_days(item.total_leave_days)
            if item.leave_type_id in seen_leave_type_ids:
                raise ConflictException(f"Duplicate leave_type_id in request: {item.leave_type_id}")
            seen_leave_type_ids.add(item.leave_type_id)

            leave_type = self._ensure_leave_type_exists(item.leave_type_id)
            resolved_leave_types[item.leave_type_id] = leave_type

            existing = self.leave_master_repository.get_by_employment_and_leave_type(
                employment_type_id=payload.employment_type_id,
                leave_type_id=item.leave_type_id,
            )
            if existing is None:
                raise NotFoundException(
                    f"Leave master not found for employment_type_id={payload.employment_type_id} "
                    f"and leave_type_id={item.leave_type_id}"
                )
            existing_mappings[item.leave_type_id] = existing

        for item in payload.leaves:
            self.leave_master_repository.update_total_days_and_proof_required(
                existing_mappings[item.leave_type_id],
                total_leave_days=item.total_leave_days,
                proof_required=resolved_leave_types[item.leave_type_id].proof_required,
            )

        self.db.commit()
        items = self.leave_master_repository.list_by_employment_type_id(payload.employment_type_id)
        grouped = self._group_by_employment_type(items)
        if not grouped:
            raise NotFoundException("Leave master not found")
        return grouped[0]

    def delete_leave_master(self, actor: User, leave_master_id: int) -> LeaveMasterGroupedResponse:
        _ = actor
        leave_master = self.leave_master_repository.get_by_id(leave_master_id)
        if leave_master is None:
            raise NotFoundException("Leave master not found")
        if self.leave_master_repository.is_used(leave_master_id):
            raise ConflictException("Cannot delete leave master because it is already in use")

        employment_type_id = leave_master.employment_type_id
        employment_type = self.employment_type_repository.get_by_id(employment_type_id)
        if employment_type is None:
            raise NotFoundException("Employment type not found")

        self.leave_master_repository.delete(leave_master)
        self.db.commit()
        remaining_items = self.leave_master_repository.list_by_employment_type_id(employment_type_id)
        grouped = self._group_by_employment_type(remaining_items)
        if grouped:
            return grouped[0]
        return LeaveMasterGroupedResponse(
            employment_type_id=employment_type_id,
            employment_type_name=employment_type.name,
            leaves=[],
        )

    def _ensure_employment_type_exists(self, employment_type_id: int) -> None:
        if self.employment_type_repository.get_by_id(employment_type_id) is None:
            raise NotFoundException("Employment type not found")

    def _ensure_leave_type_exists(self, leave_type_id: int) -> LeaveType:
        leave_type = self.leave_type_repository.get_by_id(leave_type_id)
        if leave_type is None:
            raise NotFoundException("Leave type not found")
        return leave_type

    def _ensure_unique_combination(self, employment_type_id: int, leave_type_id: int) -> None:
        existing = self.leave_master_repository.get_by_employment_and_leave_type(
            employment_type_id=employment_type_id,
            leave_type_id=leave_type_id,
        )
        if existing is not None:
            raise ConflictException("Leave master already exists for this employment type and leave type")

    @staticmethod
    def _validate_total_leave_days(total_leave_days: int) -> None:
        if total_leave_days < 0:
            raise BadRequestException("total_leave_days cannot be negative")

    @staticmethod
    def _to_response(item: LeaveMaster) -> LeaveMasterResponse:
        if item.employment_type is None:
            raise NotFoundException("Employment type not found")
        if item.leave_type is None:
            raise NotFoundException("Leave type not found")
        return LeaveMasterResponse(
            id=item.id,
            employment_type_id=item.employment_type_id,
            employment_type_name=item.employment_type.name,
            leave_type_id=item.leave_type_id,
            leave_type_name=item.leave_type.name,
            proof_required=item.proof_required,
            total_leave_days=item.total_leave_days,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    @staticmethod
    def _group_by_employment_type(items: list[LeaveMaster]) -> list[LeaveMasterGroupedResponse]:
        grouped: dict[int, LeaveMasterGroupedResponse] = {}
        for item in items:
            if item.employment_type is None:
                raise NotFoundException("Employment type not found")
            if item.leave_type is None:
                raise NotFoundException("Leave type not found")

            key = item.employment_type_id
            if key not in grouped:
                grouped[key] = LeaveMasterGroupedResponse(
                    employment_type_id=item.employment_type_id,
                    employment_type_name=item.employment_type.name,
                    leaves=[],
                )
            grouped[key].leaves.append(
                LeaveMasterGroupedLeaveItemResponse(
                    id=item.id,
                    leave_type_id=item.leave_type_id,
                    leave_type_name=item.leave_type.name,
                    proof_required=item.proof_required,
                    total_leave_days=item.total_leave_days,
                )
            )
        return list(grouped.values())
