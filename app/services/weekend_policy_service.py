from datetime import date

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.models.user import User
from app.models.weekend_policy import WeekendPolicy, WeekendSession
from app.repository.branch_repository import BranchRepository
from app.repository.weekend_policy_repository import WeekendPolicyRepository
from app.schemas.weekend_policy import (
    SessionCreateRequest,
    SessionResponse,
    SessionUpdateRequest,
    WeekendCheckResponse,
    WeekendPolicyCreateRequest,
    WeekendPolicyResponse,
    WeekendPolicyRuleRequest,
    WeekendPolicyRuleResponse,
    WeekendPolicyUpdateRequest,
)


class WeekendPolicyService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.weekend_policy_repository = WeekendPolicyRepository(db)
        self.branch_repository = BranchRepository(db)

    def create_policy(self, actor: User, payload: WeekendPolicyCreateRequest) -> WeekendPolicyResponse:
        _ = actor
        session = self._ensure_session_exists(payload.session_id)
        effective_from = session.start_date
        effective_to = session.end_date
        self._ensure_branch_exists(payload.branch_id)
        self._validate_effective_range(effective_from, effective_to)
        self._validate_within_session(
            session_start=session.start_date,
            session_end=session.end_date,
            effective_from=effective_from,
            effective_to=effective_to,
        )
        self._validate_branch_matches_session(
            session_branch_id=session.branch_id,
            branch_id=payload.branch_id,
        )
        normalized_rules = self._normalize_rules(payload.rules)
        self._ensure_no_overlap(
            session_id=payload.session_id,
            branch_id=payload.branch_id,
            effective_from=effective_from,
            effective_to=effective_to,
            exclude_policy_id=None,
        )

        policy = WeekendPolicy(
            session_id=payload.session_id,
            name=self._normalize_name(payload.name, field_name="name"),
            branch_id=payload.branch_id,
            effective_from=effective_from,
            effective_to=effective_to,
            is_active=True,
        )
        self.weekend_policy_repository.create_policy(policy)
        self.weekend_policy_repository.replace_rules(policy.id, normalized_rules)
        self.db.commit()
        loaded = self.weekend_policy_repository.get_policy_by_id(policy.id)
        if loaded is None:
            raise NotFoundException("Weekend policy not found")
        return self._to_response(loaded)

    def create_session(self, actor: User, payload: SessionCreateRequest) -> SessionResponse:
        _ = actor
        self._ensure_branch_exists(payload.branch_id)
        if payload.end_date < payload.start_date:
            raise BadRequestException("end_date cannot be before start_date")

        session = WeekendSession(
            name=self._normalize_name(payload.name, field_name="name"),
            start_date=payload.start_date,
            end_date=payload.end_date,
            branch_id=payload.branch_id,
            is_active=payload.is_active,
        )
        self.weekend_policy_repository.create_session(session)
        self.db.commit()
        return self._to_session_response(session)

    def list_sessions(self, actor: User, *, branch_id: int | None = None) -> list[SessionResponse]:
        _ = actor
        if branch_id is not None:
            self._ensure_branch_exists(branch_id)
        sessions = self.weekend_policy_repository.list_sessions(branch_id=branch_id)
        return [self._to_session_response(item) for item in sessions]

    def update_session(self, actor: User, *, session_id: int, payload: SessionUpdateRequest) -> SessionResponse:
        _ = actor
        session = self._ensure_session_exists(session_id)

        next_name = self._normalize_name(payload.name, field_name="name") if payload.name is not None else session.name
        next_start_date = payload.start_date if payload.start_date is not None else session.start_date
        next_end_date = payload.end_date if payload.end_date is not None else session.end_date
        next_is_active = payload.is_active if payload.is_active is not None else session.is_active

        if next_end_date < next_start_date:
            raise BadRequestException("end_date cannot be before start_date")

        session.name = next_name
        session.start_date = next_start_date
        session.end_date = next_end_date
        session.is_active = next_is_active

        for policy in self.weekend_policy_repository.list_policies_by_session(session.id):
            if not policy.is_active:
                continue
            policy.effective_from = next_start_date
            policy.effective_to = next_end_date

        self.db.commit()
        return self._to_session_response(session)

    def list_policies(self, actor: User, *, branch_id: int | None = None) -> list[WeekendPolicyResponse]:
        _ = actor
        if branch_id is not None:
            self._ensure_branch_exists(branch_id)
        items = self.weekend_policy_repository.list_policies(branch_id=branch_id)
        return [self._to_response(item) for item in items]

    def get_policy(self, actor: User, policy_id: int) -> WeekendPolicyResponse:
        _ = actor
        policy = self.weekend_policy_repository.get_policy_by_id(policy_id)
        if policy is None:
            raise NotFoundException("Weekend policy not found")
        return self._to_response(policy)

    def update_policy(self, actor: User, *, policy_id: int, payload: WeekendPolicyUpdateRequest) -> WeekendPolicyResponse:
        _ = actor
        policy = self.weekend_policy_repository.get_policy_by_id(policy_id)
        if policy is None:
            raise NotFoundException("Weekend policy not found")

        if self.weekend_policy_repository.is_policy_used(policy.id):
            raise ConflictException(
                "Policy already used in payroll/attendance. Close old policy and create a new one."
            )

        fields = payload.model_fields_set
        next_name = self._normalize_name(payload.name, field_name="name") if payload.name is not None else policy.name
        next_branch_id = payload.branch_id if "branch_id" in fields else policy.branch_id
        next_is_active = payload.is_active if payload.is_active is not None else policy.is_active

        session = self._ensure_session_exists(policy.session_id)
        next_effective_from = session.start_date
        next_effective_to = session.end_date
        self._ensure_branch_exists(next_branch_id)
        self._validate_effective_range(next_effective_from, next_effective_to)
        self._validate_within_session(
            session_start=session.start_date,
            session_end=session.end_date,
            effective_from=next_effective_from,
            effective_to=next_effective_to,
        )
        self._validate_branch_matches_session(
            session_branch_id=session.branch_id,
            branch_id=next_branch_id,
        )
        if next_is_active:
            self._ensure_no_overlap(
                session_id=policy.session_id,
                branch_id=next_branch_id,
                effective_from=next_effective_from,
                effective_to=next_effective_to,
                exclude_policy_id=policy.id,
            )

        policy.name = next_name
        policy.branch_id = next_branch_id
        policy.effective_from = next_effective_from
        policy.effective_to = next_effective_to
        policy.is_active = next_is_active

        if payload.rules is not None:
            normalized_rules = self._normalize_rules(payload.rules)
            self.weekend_policy_repository.replace_rules(policy.id, normalized_rules)

        self.db.commit()
        loaded = self.weekend_policy_repository.get_policy_by_id(policy.id)
        if loaded is None:
            raise NotFoundException("Weekend policy not found")
        return self._to_response(loaded)

    def delete_policy(self, actor: User, policy_id: int) -> None:
        _ = actor
        policy = self.weekend_policy_repository.get_policy_by_id(policy_id)
        if policy is None:
            raise NotFoundException("Weekend policy not found")
        if self.weekend_policy_repository.is_policy_used(policy.id):
            raise ConflictException("Cannot delete weekend policy because it is already used in payroll/attendance")
        policy.is_active = False
        closing_date = date.today()
        if closing_date < policy.effective_from:
            closing_date = policy.effective_from
        if policy.effective_to is None or policy.effective_to > closing_date:
            policy.effective_to = closing_date
        self.db.commit()

    def delete_session(self, actor: User, session_id: int) -> None:
        _ = actor
        session = self._ensure_session_exists(session_id)
        policies = self.weekend_policy_repository.list_policies_by_session(session.id)
        if any(self.weekend_policy_repository.is_policy_used(policy.id) for policy in policies):
            raise ConflictException("Cannot delete session because one or more weekend policies are already used")

        session.is_active = False
        for policy in policies:
            policy.is_active = False
            closing_date = date.today()
            if closing_date < policy.effective_from:
                closing_date = policy.effective_from
            if policy.effective_to is None or policy.effective_to > closing_date:
                policy.effective_to = closing_date

        self.db.commit()

    def is_weekend(self, actor: User, *, branch_id: int | None, target_date: date) -> WeekendCheckResponse:
        _ = actor
        if branch_id is not None:
            self._ensure_branch_exists(branch_id)

        session = self.weekend_policy_repository.get_active_session_for_date(
            branch_id=branch_id,
            target_date=target_date,
        )
        if session is None:
            return WeekendCheckResponse(is_weekend=False, session_id=None, policy_id=None)

        policy = self.weekend_policy_repository.get_active_policy_for_date(
            session_id=session.id,
            branch_id=branch_id,
            target_date=target_date,
        )
        if policy is None:
            return WeekendCheckResponse(is_weekend=False, session_id=session.id, policy_id=None)

        day_of_week = self._day_of_week(target_date)
        week_index = self._week_index(target_date)
        is_match = any(
            rule.day_of_week == day_of_week and (rule.week_number is None or rule.week_number == week_index)
            for rule in policy.rules
        )
        return WeekendCheckResponse(is_weekend=is_match, session_id=session.id, policy_id=policy.id)

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
    def _validate_branch_matches_session(*, session_branch_id: int | None, branch_id: int | None) -> None:
        if session_branch_id is None and branch_id is not None:
            raise BadRequestException("branch_id must match session branch")
        if session_branch_id is not None and session_branch_id != branch_id:
            raise BadRequestException("branch_id must match session branch")

    @staticmethod
    def _validate_effective_range(effective_from: date, effective_to: date | None) -> None:
        if effective_to is not None and effective_to < effective_from:
            raise BadRequestException("effective_to cannot be before effective_from")

    @staticmethod
    def _validate_within_session(
        *,
        session_start: date,
        session_end: date,
        effective_from: date,
        effective_to: date | None,
    ) -> None:
        if effective_from < session_start or effective_from > session_end:
            raise BadRequestException("effective_from must be within session date range")
        if effective_to is not None and (effective_to < session_start or effective_to > session_end):
            raise BadRequestException("effective_to must be within session date range")

    def _ensure_no_overlap(
        self,
        *,
        session_id: int,
        branch_id: int | None,
        effective_from: date,
        effective_to: date | None,
        exclude_policy_id: int | None,
    ) -> None:
        overlap = self.weekend_policy_repository.find_overlapping_active_policy(
            session_id=session_id,
            branch_id=branch_id,
            effective_from=effective_from,
            effective_to=effective_to,
            exclude_policy_id=exclude_policy_id,
        )
        if overlap is not None:
            raise ConflictException("Overlapping active weekend policy already exists for this branch and session")

    @staticmethod
    def _normalize_rules(rules: list[WeekendPolicyRuleRequest]) -> list[tuple[int, int | None]]:
        normalized = [(rule.day_of_week, rule.week_number) for rule in rules]
        if len(normalized) != len(set(normalized)):
            raise ConflictException("Duplicate weekend rule combinations are not allowed")
        return normalized

    @staticmethod
    def _normalize_name(value: str, *, field_name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise BadRequestException(f"{field_name} cannot be empty")
        return normalized

    @staticmethod
    def _day_of_week(target_date: date) -> int:
        return (target_date.weekday() + 1) % 7

    @staticmethod
    def _week_index(target_date: date) -> int:
        return ((target_date.day - 1) // 7) + 1

    @staticmethod
    def _to_response(policy: WeekendPolicy) -> WeekendPolicyResponse:
        if policy.session is None:
            raise NotFoundException("Session not found")
        return WeekendPolicyResponse(
            id=policy.id,
            session_id=policy.session_id,
            session_name=policy.session.name,
            name=policy.name,
            branch_id=policy.branch_id,
            effective_from=policy.effective_from,
            effective_to=policy.effective_to,
            is_active=policy.is_active,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
            rules=[
                WeekendPolicyRuleResponse(
                    id=rule.id,
                    day_of_week=rule.day_of_week,
                    week_number=rule.week_number,
                )
                for rule in sorted(policy.rules, key=lambda item: item.id)
            ],
        )

    @staticmethod
    def _to_session_response(session: WeekendSession) -> SessionResponse:
        return SessionResponse(
            id=session.id,
            name=session.name,
            start_date=session.start_date,
            end_date=session.end_date,
            branch_id=session.branch_id,
            is_active=session.is_active,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
