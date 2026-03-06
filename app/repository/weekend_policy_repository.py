from datetime import date

from sqlalchemy import and_, case, inspect, or_, text
from sqlalchemy.orm import Session, joinedload

from app.models.weekend_policy import WeekendPolicy, WeekendPolicyRule, WeekendSession


class WeekendPolicyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_session_by_id(self, session_id: int) -> WeekendSession | None:
        return self.db.query(WeekendSession).filter(WeekendSession.id == session_id).first()

    def create_session(self, session: WeekendSession) -> WeekendSession:
        self.db.add(session)
        self.db.flush()
        self.db.refresh(session)
        return session

    def list_sessions(self, *, branch_id: int | None = None) -> list[WeekendSession]:
        query = self.db.query(WeekendSession).filter(WeekendSession.is_active.is_(True))
        if branch_id is not None:
            query = query.filter(WeekendSession.branch_id == branch_id)
        return query.order_by(WeekendSession.start_date.desc(), WeekendSession.id.desc()).all()

    def get_active_session_for_date(self, *, branch_id: int | None, target_date: date) -> WeekendSession | None:
        query = (
            self.db.query(WeekendSession)
            .filter(
                WeekendSession.is_active.is_(True),
                WeekendSession.start_date <= target_date,
                WeekendSession.end_date >= target_date,
            )
        )
        if branch_id is not None:
            query = query.filter(or_(WeekendSession.branch_id == branch_id, WeekendSession.branch_id.is_(None)))
            query = query.order_by(
                case((WeekendSession.branch_id == branch_id, 0), else_=1),
                WeekendSession.start_date.desc(),
                WeekendSession.id.desc(),
            )
        else:
            query = query.filter(WeekendSession.branch_id.is_(None)).order_by(
                WeekendSession.start_date.desc(),
                WeekendSession.id.desc(),
            )
        return query.first()

    def create_policy(self, policy: WeekendPolicy) -> WeekendPolicy:
        self.db.add(policy)
        self.db.flush()
        self.db.refresh(policy)
        return policy

    def get_policy_by_id(self, policy_id: int) -> WeekendPolicy | None:
        return (
            self.db.query(WeekendPolicy)
            .options(joinedload(WeekendPolicy.rules), joinedload(WeekendPolicy.session))
            .filter(WeekendPolicy.id == policy_id)
            .first()
        )

    def list_policies(self, *, branch_id: int | None = None) -> list[WeekendPolicy]:
        query = self.db.query(WeekendPolicy).options(
            joinedload(WeekendPolicy.rules),
            joinedload(WeekendPolicy.session),
        ).filter(WeekendPolicy.is_active.is_(True))
        if branch_id is not None:
            query = query.filter(WeekendPolicy.branch_id == branch_id)
        return query.order_by(WeekendPolicy.id.desc()).all()

    def list_policies_by_session(self, session_id: int) -> list[WeekendPolicy]:
        return self.db.query(WeekendPolicy).filter(WeekendPolicy.session_id == session_id).all()

    def find_overlapping_active_policy(
        self,
        *,
        session_id: int,
        branch_id: int | None,
        effective_from: date,
        effective_to: date | None,
        exclude_policy_id: int | None = None,
    ) -> WeekendPolicy | None:
        query = self.db.query(WeekendPolicy).filter(
            WeekendPolicy.session_id == session_id,
            WeekendPolicy.is_active.is_(True),
        )
        if branch_id is None:
            query = query.filter(WeekendPolicy.branch_id.is_(None))
        else:
            query = query.filter(WeekendPolicy.branch_id == branch_id)

        if exclude_policy_id is not None:
            query = query.filter(WeekendPolicy.id != exclude_policy_id)

        conditions = [
            or_(WeekendPolicy.effective_to.is_(None), WeekendPolicy.effective_to >= effective_from),
        ]
        if effective_to is not None:
            conditions.append(WeekendPolicy.effective_from <= effective_to)

        return query.filter(and_(*conditions)).order_by(WeekendPolicy.id.asc()).first()

    def replace_rules(self, policy_id: int, rules: list[tuple[int, int | None]]) -> None:
        self.db.query(WeekendPolicyRule).filter(WeekendPolicyRule.weekend_policy_id == policy_id).delete(
            synchronize_session=False
        )
        if rules:
            self.db.add_all(
                WeekendPolicyRule(
                    weekend_policy_id=policy_id,
                    day_of_week=day_of_week,
                    week_number=week_number,
                )
                for day_of_week, week_number in rules
            )
        self.db.flush()

    def get_active_policy_for_date(
        self,
        *,
        session_id: int,
        branch_id: int | None,
        target_date: date,
    ) -> WeekendPolicy | None:
        query = (
            self.db.query(WeekendPolicy)
            .options(joinedload(WeekendPolicy.rules), joinedload(WeekendPolicy.session))
            .filter(
                WeekendPolicy.session_id == session_id,
                WeekendPolicy.is_active.is_(True),
                WeekendPolicy.effective_from <= target_date,
                or_(WeekendPolicy.effective_to.is_(None), WeekendPolicy.effective_to >= target_date),
            )
        )
        if branch_id is not None:
            query = query.filter(or_(WeekendPolicy.branch_id == branch_id, WeekendPolicy.branch_id.is_(None)))
            query = query.order_by(
                case((WeekendPolicy.branch_id == branch_id, 0), else_=1),
                WeekendPolicy.effective_from.desc(),
                WeekendPolicy.id.desc(),
            )
        else:
            query = query.filter(WeekendPolicy.branch_id.is_(None)).order_by(
                WeekendPolicy.effective_from.desc(),
                WeekendPolicy.id.desc(),
            )
        return query.first()

    def is_policy_used(self, policy_id: int) -> bool:
        bind = self.db.get_bind()
        inspector = inspect(bind)
        candidate_tables = ("payroll_entries", "salary_slips", "attendance", "leave_requests")

        for table_name in candidate_tables:
            if not inspector.has_table(table_name):
                continue
            columns = {column["name"] for column in inspector.get_columns(table_name)}
            if "weekend_policy_id" not in columns:
                continue
            result = self.db.execute(
                text(f"SELECT COUNT(*) FROM {table_name} WHERE weekend_policy_id = :policy_id"),
                {"policy_id": policy_id},
            ).scalar()
            if int(result or 0) > 0:
                return True
        return False
