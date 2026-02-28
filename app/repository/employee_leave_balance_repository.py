from sqlalchemy.orm import Session

from app.models.employee_leave_balance import EmployeeLeaveBalance


class EmployeeLeaveBalanceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_user_and_leave_type(self, *, user_id: int, leave_type_id: int) -> EmployeeLeaveBalance | None:
        return (
            self.db.query(EmployeeLeaveBalance)
            .filter(
                EmployeeLeaveBalance.user_id == user_id,
                EmployeeLeaveBalance.leave_type_id == leave_type_id,
            )
            .first()
        )

    def create(
        self,
        *,
        user_id: int,
        leave_type_id: int,
        allocated_days: int,
        used_days: int,
        remaining_days: int,
    ) -> EmployeeLeaveBalance:
        item = EmployeeLeaveBalance(
            user_id=user_id,
            leave_type_id=leave_type_id,
            allocated_days=allocated_days,
            used_days=used_days,
            remaining_days=remaining_days,
        )
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def update(self, item: EmployeeLeaveBalance) -> EmployeeLeaveBalance:
        self.db.flush()
        self.db.refresh(item)
        return item
