from sqlalchemy import inspect, text
from sqlalchemy.orm import Session, joinedload

from app.models.leave_master import LeaveMaster


class LeaveMasterRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        employment_type_id: int,
        leave_type_id: int,
        total_leave_days: int,
        proof_required: bool,
    ) -> LeaveMaster:
        leave_master = LeaveMaster(
            employment_type_id=employment_type_id,
            leave_type_id=leave_type_id,
            total_leave_days=total_leave_days,
            proof_required=proof_required,
        )
        self.db.add(leave_master)
        self.db.flush()
        self.db.refresh(leave_master)
        return leave_master

    def get_by_id(self, leave_master_id: int) -> LeaveMaster | None:
        return (
            self.db.query(LeaveMaster)
            .options(
                joinedload(LeaveMaster.employment_type),
                joinedload(LeaveMaster.leave_type),
            )
            .filter(LeaveMaster.id == leave_master_id)
            .first()
        )

    def get_by_employment_and_leave_type(
        self,
        *,
        employment_type_id: int,
        leave_type_id: int,
    ) -> LeaveMaster | None:
        return (
            self.db.query(LeaveMaster)
            .filter(
                LeaveMaster.employment_type_id == employment_type_id,
                LeaveMaster.leave_type_id == leave_type_id,
            )
            .first()
        )

    def list_all(self) -> list[LeaveMaster]:
        return (
            self.db.query(LeaveMaster)
            .options(
                joinedload(LeaveMaster.employment_type),
                joinedload(LeaveMaster.leave_type),
            )
            .order_by(LeaveMaster.id.asc())
            .all()
        )

    def list_by_employment_type_id(self, employment_type_id: int) -> list[LeaveMaster]:
        return (
            self.db.query(LeaveMaster)
            .options(
                joinedload(LeaveMaster.employment_type),
                joinedload(LeaveMaster.leave_type),
            )
            .filter(LeaveMaster.employment_type_id == employment_type_id)
            .order_by(LeaveMaster.id.asc())
            .all()
        )

    def update_total_days(self, leave_master: LeaveMaster, *, total_leave_days: int) -> LeaveMaster:
        leave_master.total_leave_days = total_leave_days
        self.db.flush()
        self.db.refresh(leave_master)
        return leave_master

    def update_total_days_and_proof_required(
        self,
        leave_master: LeaveMaster,
        *,
        total_leave_days: int,
        proof_required: bool,
    ) -> LeaveMaster:
        leave_master.total_leave_days = total_leave_days
        leave_master.proof_required = proof_required
        self.db.flush()
        self.db.refresh(leave_master)
        return leave_master

    def delete(self, leave_master: LeaveMaster) -> None:
        self.db.delete(leave_master)
        self.db.flush()

    def is_used(self, leave_master_id: int) -> bool:
        bind = self.db.get_bind()
        inspector = inspect(bind)
        candidate_tables = (
            "leave_requests",
            "leave_transactions",
            "leave_allocations",
            "user_leave_balances",
        )

        for table_name in candidate_tables:
            if not inspector.has_table(table_name):
                continue
            column_names = {column["name"] for column in inspector.get_columns(table_name)}
            if "leave_master_id" not in column_names:
                continue

            result = self.db.execute(
                text(f"SELECT COUNT(*) FROM {table_name} WHERE leave_master_id = :leave_master_id"),
                {"leave_master_id": leave_master_id},
            ).scalar()
            if int(result or 0) > 0:
                return True

        return False
