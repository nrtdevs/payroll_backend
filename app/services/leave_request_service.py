from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException
from app.models.leave_request import LeaveRequest, LeaveRequestStatus
from app.models.role import RoleEnum
from app.models.user import User
from app.repository.employee_leave_balance_repository import EmployeeLeaveBalanceRepository
from app.repository.leave_master_repository import LeaveMasterRepository
from app.repository.leave_request_repository import LeaveRequestRepository
from app.repository.leave_type_repository import LeaveTypeRepository
from app.repository.role_permission_repository import RolePermissionRepository
from app.repository.user_repository import UserRepository
from app.schemas.leave_request import LeaveRequestApplyRequest, LeaveRequestRejectRequest, LeaveRequestResponse


class LeaveRequestService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.leave_type_repository = LeaveTypeRepository(db)
        self.leave_master_repository = LeaveMasterRepository(db)
        self.leave_request_repository = LeaveRequestRepository(db)
        self.balance_repository = EmployeeLeaveBalanceRepository(db)
        self.user_repository = UserRepository(db)
        self.role_permission_repository = RolePermissionRepository(db)

    def apply_leave(self, current_user: User, payload: LeaveRequestApplyRequest) -> LeaveRequestResponse:
        leave_type = self.leave_type_repository.get_by_id(payload.leave_type_id)
        if leave_type is None:
            raise NotFoundException("Leave type not found")
        if payload.end_date < payload.start_date:
            raise BadRequestException("end_date must be greater than or equal to start_date")

        total_days = (payload.end_date - payload.start_date).days + 1
        if total_days <= 0:
            raise BadRequestException("total leave days must be greater than zero")

        if self.leave_request_repository.exists_overlap_for_user(
            user_id=current_user.id,
            start_date=payload.start_date,
            end_date=payload.end_date,
        ):
            raise ConflictException("Overlapping leave request already exists")

        if leave_type.proof_required:
            if payload.proof_file_path is None or not payload.proof_file_path.strip():
                raise BadRequestException("Proof is required for this leave type")

        balance = self._get_or_initialize_balance(user=current_user, leave_type_id=payload.leave_type_id)
        if balance.remaining_days < total_days:
            raise BadRequestException("Insufficient leave balance")

        item = self.leave_request_repository.create(
            user_id=current_user.id,
            leave_type_id=payload.leave_type_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            total_days=total_days,
            reason=payload.reason.strip(),
            proof_file_path=payload.proof_file_path.strip() if payload.proof_file_path else None,
        )
        self.db.commit()
        loaded = self.leave_request_repository.get_by_id(item.id)
        if loaded is None:
            raise NotFoundException("Leave request not found")
        return self._to_response(loaded)

    def list_my_requests(self, current_user: User) -> list[LeaveRequestResponse]:
        items = self.leave_request_repository.list_by_user_id(current_user.id)
        return [self._to_response(item) for item in items]

    def list_team_requests(
        self,
        current_user: User,
        *,
        status: LeaveRequestStatus | None = LeaveRequestStatus.PENDING,
    ) -> list[LeaveRequestResponse]:
        include_admin_scope = self._can_admin_override(current_user)
        items = self.leave_request_repository.list_for_team(
            manager_id=current_user.id,
            manager_business_id=current_user.business_id,
            include_admin_scope=include_admin_scope,
            status=status,
        )
        return [self._to_response(item) for item in items]

    def approve_request(self, current_user: User, leave_request_id: int) -> LeaveRequestResponse:
        item = self.leave_request_repository.get_by_id(leave_request_id)
        if item is None:
            raise NotFoundException("Leave request not found")
        if item.status != LeaveRequestStatus.PENDING:
            raise BadRequestException("Only pending leave requests can be approved")
        if item.user_id == current_user.id:
            raise ForbiddenException("You cannot approve your own leave request")
        if item.user is None:
            raise NotFoundException("Leave request user not found")

        if not self._can_approve(current_user=current_user, employee=item.user):
            raise ForbiddenException("Only direct reporting manager or admin can approve this leave")

        balance = self._get_or_initialize_balance(user=item.user, leave_type_id=item.leave_type_id)
        if balance.remaining_days < item.total_days:
            raise BadRequestException("Insufficient leave balance")

        balance.used_days += item.total_days
        balance.remaining_days -= item.total_days
        self.balance_repository.update(balance)

        item.status = LeaveRequestStatus.APPROVED
        item.approved_by = current_user.id
        item.approved_at = datetime.now(timezone.utc)
        item.rejection_reason = None
        self.leave_request_repository.update(item)
        self.db.commit()

        loaded = self.leave_request_repository.get_by_id(item.id)
        if loaded is None:
            raise NotFoundException("Leave request not found")
        return self._to_response(loaded)

    def reject_request(
        self,
        current_user: User,
        leave_request_id: int,
        payload: LeaveRequestRejectRequest,
    ) -> LeaveRequestResponse:
        item = self.leave_request_repository.get_by_id(leave_request_id)
        if item is None:
            raise NotFoundException("Leave request not found")
        if item.status != LeaveRequestStatus.PENDING:
            raise BadRequestException("Only pending leave requests can be rejected")
        if item.user_id == current_user.id:
            raise ForbiddenException("You cannot reject your own leave request")
        if item.user is None:
            raise NotFoundException("Leave request user not found")
        if not self._can_approve(current_user=current_user, employee=item.user):
            raise ForbiddenException("Only direct reporting manager or admin can reject this leave")

        item.status = LeaveRequestStatus.REJECTED
        item.approved_by = current_user.id
        item.approved_at = datetime.now(timezone.utc)
        item.rejection_reason = payload.rejection_reason.strip()
        self.leave_request_repository.update(item)
        self.db.commit()

        loaded = self.leave_request_repository.get_by_id(item.id)
        if loaded is None:
            raise NotFoundException("Leave request not found")
        return self._to_response(loaded)

    def _get_or_initialize_balance(self, *, user: User, leave_type_id: int):
        balance = self.balance_repository.get_by_user_and_leave_type(user_id=user.id, leave_type_id=leave_type_id)
        if balance is not None:
            return balance
        if user.employment_type_id is None:
            raise BadRequestException("User has no employment type assigned")

        leave_master = self.leave_master_repository.get_by_employment_and_leave_type(
            employment_type_id=user.employment_type_id,
            leave_type_id=leave_type_id,
        )
        if leave_master is None:
            raise NotFoundException("Leave policy not configured for this user employment type")
        return self.balance_repository.create(
            user_id=user.id,
            leave_type_id=leave_type_id,
            allocated_days=leave_master.total_leave_days,
            used_days=0,
            remaining_days=leave_master.total_leave_days,
        )

    def _can_admin_override(self, current_user: User) -> bool:
        if current_user.role in {RoleEnum.MASTER_ADMIN, RoleEnum.BUSINESS_OWNER, RoleEnum.BUSINESS_ADMIN}:
            return True
        if current_user.role_id is None:
            return False
        return self.role_permission_repository.has_permission_for_role(
            role_id=current_user.role_id,
            permission_name="APPROVE_ANY_LEAVE",
        )

    def _can_approve(self, *, current_user: User, employee: User) -> bool:
        if self._can_admin_override(current_user):
            return True
        return employee.reporting_manager_id == current_user.id

    @staticmethod
    def _to_response(item: LeaveRequest) -> LeaveRequestResponse:
        if item.leave_type is None:
            raise NotFoundException("Leave type not found")
        return LeaveRequestResponse(
            id=item.id,
            user_id=item.user_id,
            user_name=(item.user.name if item.user is not None else None),
            leave_type_id=item.leave_type_id,
            leave_type_name=item.leave_type.name,
            start_date=item.start_date,
            end_date=item.end_date,
            total_days=item.total_days,
            reason=item.reason,
            proof_file_path=item.proof_file_path,
            status=item.status,
            applied_at=item.applied_at,
            approved_by=item.approved_by,
            approved_by_name=(item.approver.name if item.approver is not None else None),
            approved_at=item.approved_at,
            rejection_reason=item.rejection_reason,
        )
