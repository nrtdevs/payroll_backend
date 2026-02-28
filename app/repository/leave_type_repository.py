from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.leave_type import LeaveType


class LeaveTypeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        name: str,
        description: str | None,
        is_active: bool,
        proof_required: bool,
    ) -> LeaveType:
        leave_type = LeaveType(
            name=name,
            description=description,
            is_active=is_active,
            proof_required=proof_required,
        )
        self.db.add(leave_type)
        self.db.flush()
        self.db.refresh(leave_type)
        return leave_type

    def get_by_id(self, leave_type_id: int) -> LeaveType | None:
        return self.db.query(LeaveType).filter(LeaveType.id == leave_type_id).first()

    def get_by_name(self, name: str) -> LeaveType | None:
        return (
            self.db.query(LeaveType)
            .filter(func.lower(LeaveType.name) == name.lower())
            .first()
        )

    def list_all(self) -> list[LeaveType]:
        return self.db.query(LeaveType).order_by(LeaveType.id.asc()).all()

    def update(
        self,
        leave_type: LeaveType,
        *,
        name: str,
        description: str | None,
        is_active: bool,
        proof_required: bool,
    ) -> LeaveType:
        leave_type.name = name
        leave_type.description = description
        leave_type.is_active = is_active
        leave_type.proof_required = proof_required
        self.db.flush()
        self.db.refresh(leave_type)
        return leave_type

    def delete(self, leave_type: LeaveType) -> None:
        self.db.delete(leave_type)
        self.db.flush()
