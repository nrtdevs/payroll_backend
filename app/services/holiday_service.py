from datetime import date

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.models.holiday import Holiday, HolidayType
from app.models.user import User
from app.repository.branch_repository import BranchRepository
from app.repository.holiday_repository import HolidayRepository
from app.repository.weekend_policy_repository import WeekendPolicyRepository
from app.schemas.holiday import (
    HolidayCheckResponse,
    HolidayCreateRequest,
    HolidayResponse,
    HolidayTypeCreateRequest,
    HolidayTypeResponse,
    HolidayTypeUpdateRequest,
    HolidayUpdateRequest,
)


class HolidayService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.holiday_repository = HolidayRepository(db)
        self.branch_repository = BranchRepository(db)
        self.weekend_policy_repository = WeekendPolicyRepository(db)

    def create_holiday_type(self, actor: User, payload: HolidayTypeCreateRequest) -> HolidayTypeResponse:
        _ = actor
        normalized_name = self._normalize_name(payload.name)
        existing = self.holiday_repository.get_holiday_type_by_name(normalized_name)
        if existing is not None and existing.is_active:
            raise ConflictException("Holiday type already exists")

        holiday_type = HolidayType(
            name=normalized_name,
            description=self._normalize_description(payload.description),
            is_paid=payload.is_paid,
            is_active=True,
        )
        self.holiday_repository.create_holiday_type(holiday_type)
        self.db.commit()
        return self._to_holiday_type_response(holiday_type)

    def list_holiday_types(self, actor: User) -> list[HolidayTypeResponse]:
        _ = actor
        return [self._to_holiday_type_response(item) for item in self.holiday_repository.list_holiday_types()]

    def update_holiday_type(
        self,
        actor: User,
        *,
        holiday_type_id: int,
        payload: HolidayTypeUpdateRequest,
    ) -> HolidayTypeResponse:
        _ = actor
        holiday_type = self._ensure_holiday_type_exists(holiday_type_id)
        fields = payload.model_fields_set

        next_name = (
            self._normalize_name(payload.name) if payload.name is not None else holiday_type.name
        )
        existing = self.holiday_repository.get_holiday_type_by_name(next_name)
        if existing is not None and existing.id != holiday_type.id and existing.is_active:
            raise ConflictException("Holiday type already exists")

        next_description = (
            self._normalize_description(payload.description) if "description" in fields else holiday_type.description
        )
        next_is_paid = payload.is_paid if payload.is_paid is not None else holiday_type.is_paid
        next_is_active = payload.is_active if payload.is_active is not None else holiday_type.is_active

        holiday_type.name = next_name
        holiday_type.description = next_description
        holiday_type.is_paid = next_is_paid
        holiday_type.is_active = next_is_active
        self.db.commit()
        return self._to_holiday_type_response(holiday_type)

    def delete_holiday_type(self, actor: User, holiday_type_id: int) -> None:
        _ = actor
        holiday_type = self._ensure_holiday_type_exists(holiday_type_id)
        holiday_type.is_active = False
        self.db.commit()

    def create_holiday(self, actor: User, payload: HolidayCreateRequest) -> HolidayResponse:
        _ = actor
        holiday_type = self._ensure_holiday_type_exists(payload.holiday_type_id)
        if not holiday_type.is_active:
            raise BadRequestException("Holiday type is inactive")

        session = self._ensure_session_exists(payload.session_id)
        self._ensure_branch_exists(payload.branch_id)
        self._validate_branch_matches_session(session_branch_id=session.branch_id, branch_id=payload.branch_id)
        self._validate_holiday_date_within_session(
            holiday_date=payload.holiday_date,
            session_start=session.start_date,
            session_end=session.end_date,
        )
        self._ensure_no_duplicate_holiday(
            holiday_date=payload.holiday_date,
            session_id=payload.session_id,
            branch_id=payload.branch_id,
            exclude_holiday_id=None,
        )

        holiday = Holiday(
            name=self._normalize_name(payload.name),
            holiday_date=payload.holiday_date,
            holiday_type_id=payload.holiday_type_id,
            branch_id=payload.branch_id,
            session_id=payload.session_id,
            description=self._normalize_description(payload.description),
            is_optional=payload.is_optional,
            is_active=True,
        )
        self.holiday_repository.create_holiday(holiday)
        self.db.commit()
        loaded = self.holiday_repository.get_holiday_by_id(holiday.id)
        if loaded is None:
            raise NotFoundException("Holiday not found")
        return self._to_holiday_response(loaded)

    def list_holidays(
        self,
        actor: User,
        *,
        session_id: int | None = None,
        branch_id: int | None = None,
        year: int | None = None,
    ) -> list[HolidayResponse]:
        _ = actor
        if session_id is not None:
            self._ensure_session_exists(session_id)
        if branch_id is not None:
            self._ensure_branch_exists(branch_id)
        if year is not None and year < 1900:
            raise BadRequestException("year must be valid")
        items = self.holiday_repository.list_holidays(session_id=session_id, branch_id=branch_id, year=year)
        return [self._to_holiday_response(item) for item in items]

    def get_holiday(self, actor: User, holiday_id: int) -> HolidayResponse:
        _ = actor
        holiday = self.holiday_repository.get_holiday_by_id(holiday_id)
        if holiday is None or not holiday.is_active:
            raise NotFoundException("Holiday not found")
        return self._to_holiday_response(holiday)

    def update_holiday(self, actor: User, *, holiday_id: int, payload: HolidayUpdateRequest) -> HolidayResponse:
        _ = actor
        holiday = self.holiday_repository.get_holiday_by_id(holiday_id)
        if holiday is None:
            raise NotFoundException("Holiday not found")

        fields = payload.model_fields_set
        next_name = self._normalize_name(payload.name) if payload.name is not None else holiday.name
        next_holiday_date = payload.holiday_date if payload.holiday_date is not None else holiday.holiday_date
        next_holiday_type_id = payload.holiday_type_id if payload.holiday_type_id is not None else holiday.holiday_type_id
        next_session_id = payload.session_id if payload.session_id is not None else holiday.session_id
        next_description = (
            self._normalize_description(payload.description) if "description" in fields else holiday.description
        )
        next_is_optional = payload.is_optional if payload.is_optional is not None else holiday.is_optional
        next_is_active = payload.is_active if payload.is_active is not None else holiday.is_active
        next_branch_id = payload.branch_id if "branch_id" in fields else holiday.branch_id

        holiday_type = self._ensure_holiday_type_exists(next_holiday_type_id)
        if not holiday_type.is_active:
            raise BadRequestException("Holiday type is inactive")
        session = self._ensure_session_exists(next_session_id)
        self._ensure_branch_exists(next_branch_id)
        self._validate_branch_matches_session(session_branch_id=session.branch_id, branch_id=next_branch_id)
        self._validate_holiday_date_within_session(
            holiday_date=next_holiday_date,
            session_start=session.start_date,
            session_end=session.end_date,
        )
        if next_is_active:
            self._ensure_no_duplicate_holiday(
                holiday_date=next_holiday_date,
                session_id=next_session_id,
                branch_id=next_branch_id,
                exclude_holiday_id=holiday.id,
            )

        holiday.name = next_name
        holiday.holiday_date = next_holiday_date
        holiday.holiday_type_id = next_holiday_type_id
        holiday.session_id = next_session_id
        holiday.branch_id = next_branch_id
        holiday.description = next_description
        holiday.is_optional = next_is_optional
        holiday.is_active = next_is_active
        self.db.commit()

        loaded = self.holiday_repository.get_holiday_by_id(holiday.id)
        if loaded is None:
            raise NotFoundException("Holiday not found")
        return self._to_holiday_response(loaded)

    def delete_holiday(self, actor: User, holiday_id: int) -> None:
        _ = actor
        holiday = self.holiday_repository.get_holiday_by_id(holiday_id)
        if holiday is None:
            raise NotFoundException("Holiday not found")
        holiday.is_active = False
        self.db.commit()

    def check_holiday(self, actor: User, *, target_date: date, branch_id: int | None) -> HolidayCheckResponse:
        _ = actor
        if branch_id is not None:
            self._ensure_branch_exists(branch_id)

        session = self.weekend_policy_repository.get_active_session_for_date(
            branch_id=branch_id,
            target_date=target_date,
        )
        if session is None:
            return HolidayCheckResponse(is_holiday=False, holiday_name=None, holiday_id=None)

        holiday = self.holiday_repository.get_holiday_for_date(
            session_id=session.id,
            branch_id=branch_id,
            target_date=target_date,
        )
        if holiday is None:
            return HolidayCheckResponse(is_holiday=False, holiday_name=None, holiday_id=None)

        return HolidayCheckResponse(is_holiday=True, holiday_name=holiday.name, holiday_id=holiday.id)

    def _ensure_holiday_type_exists(self, holiday_type_id: int) -> HolidayType:
        holiday_type = self.holiday_repository.get_holiday_type_by_id(holiday_type_id)
        if holiday_type is None:
            raise NotFoundException("Holiday type not found")
        return holiday_type

    def _ensure_session_exists(self, session_id: int):
        session = self.weekend_policy_repository.get_session_by_id(session_id)
        if session is None:
            raise NotFoundException("Session not found")
        return session

    def _ensure_branch_exists(self, branch_id: int | None) -> None:
        if branch_id is None:
            return
        if self.branch_repository.get_by_id(branch_id) is None:
            raise NotFoundException("Branch not found")

    @staticmethod
    def _validate_holiday_date_within_session(*, holiday_date: date, session_start: date, session_end: date) -> None:
        if holiday_date < session_start or holiday_date > session_end:
            raise BadRequestException("holiday_date must be within session date range")

    @staticmethod
    def _validate_branch_matches_session(*, session_branch_id: int | None, branch_id: int | None) -> None:
        if session_branch_id is None and branch_id is not None:
            raise BadRequestException("branch_id must match session branch")
        if session_branch_id is not None and session_branch_id != branch_id:
            raise BadRequestException("branch_id must match session branch")

    def _ensure_no_duplicate_holiday(
        self,
        *,
        holiday_date: date,
        session_id: int,
        branch_id: int | None,
        exclude_holiday_id: int | None,
    ) -> None:
        existing = self.holiday_repository.find_duplicate_holiday(
            holiday_date=holiday_date,
            session_id=session_id,
            branch_id=branch_id,
            exclude_holiday_id=exclude_holiday_id,
        )
        if existing is not None:
            raise ConflictException("Holiday already exists for this date, session and branch")

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

    @staticmethod
    def _to_holiday_type_response(item: HolidayType) -> HolidayTypeResponse:
        return HolidayTypeResponse(
            id=item.id,
            name=item.name,
            description=item.description,
            is_paid=item.is_paid,
            is_active=item.is_active,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    @staticmethod
    def _to_holiday_response(item: Holiday) -> HolidayResponse:
        if item.holiday_type is None:
            raise NotFoundException("Holiday type not found")
        if item.session is None:
            raise NotFoundException("Session not found")
        return HolidayResponse(
            id=item.id,
            name=item.name,
            holiday_date=item.holiday_date,
            holiday_type_id=item.holiday_type_id,
            holiday_type_name=item.holiday_type.name,
            branch_id=item.branch_id,
            session_id=item.session_id,
            session_name=item.session.name,
            description=item.description,
            is_optional=item.is_optional,
            is_active=item.is_active,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
