from datetime import date

from sqlalchemy.orm import Session, joinedload

from app.models.leave_request import LeaveRequest, LeaveRequestStatus


class LeaveRequestRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        user_id: int,
        leave_type_id: int,
        start_date: date,
        end_date: date,
        total_days: int,
        reason: str,
        proof_file_path: str | None,
    ) -> LeaveRequest:
        item = LeaveRequest(
            user_id=user_id,
            leave_type_id=leave_type_id,
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            reason=reason,
            proof_file_path=proof_file_path,
            status=LeaveRequestStatus.PENDING,
        )
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def get_by_id(self, leave_request_id: int) -> LeaveRequest | None:
        return (
            self.db.query(LeaveRequest)
            .options(
                joinedload(LeaveRequest.user),
                joinedload(LeaveRequest.leave_type),
                joinedload(LeaveRequest.approver),
            )
            .filter(LeaveRequest.id == leave_request_id)
            .first()
        )

    def list_by_user_id(self, user_id: int) -> list[LeaveRequest]:
        return (
            self.db.query(LeaveRequest)
            .options(joinedload(LeaveRequest.leave_type), joinedload(LeaveRequest.approver))
            .filter(LeaveRequest.user_id == user_id)
            .order_by(LeaveRequest.id.desc())
            .all()
        )

    def list_for_team(
        self,
        *,
        manager_id: int,
        manager_business_id: int | None,
        include_admin_scope: bool,
        status: LeaveRequestStatus | None = None,
    ) -> list[LeaveRequest]:
        query = self.db.query(LeaveRequest).options(
            joinedload(LeaveRequest.user),
            joinedload(LeaveRequest.leave_type),
            joinedload(LeaveRequest.approver),
        )
        if include_admin_scope:
            if manager_business_id is not None:
                query = query.join(LeaveRequest.user).filter(LeaveRequest.user.has(business_id=manager_business_id))
        else:
            query = query.join(LeaveRequest.user).filter(LeaveRequest.user.has(reporting_manager_id=manager_id))
        if status is not None:
            query = query.filter(LeaveRequest.status == status)
        return query.order_by(LeaveRequest.id.desc()).all()

    def exists_overlap_for_user(
        self,
        *,
        user_id: int,
        start_date: date,
        end_date: date,
    ) -> bool:
        return (
            self.db.query(LeaveRequest)
            .filter(
                LeaveRequest.user_id == user_id,
                LeaveRequest.status.in_([LeaveRequestStatus.PENDING, LeaveRequestStatus.APPROVED]),
                LeaveRequest.start_date <= end_date,
                LeaveRequest.end_date >= start_date,
            )
            .first()
            is not None
        )

    def update(self, item: LeaveRequest) -> LeaveRequest:
        self.db.flush()
        self.db.refresh(item)
        return item
