from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.leave_request import LeaveRequestStatus
from app.models.user import User
from app.schemas.leave_request import LeaveRequestApplyRequest, LeaveRequestRejectRequest, LeaveRequestResponse
from app.services.leave_request_service import LeaveRequestService


router = APIRouter(tags=["Leave Requests"])


@router.post("/leave-requests", response_model=LeaveRequestResponse)
def apply_leave_request(
    payload: LeaveRequestApplyRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> LeaveRequestResponse:
    service = LeaveRequestService(db)
    return service.apply_leave(current_user=current_user, payload=payload)


@router.get("/leave-requests/my", response_model=list[LeaveRequestResponse])
def list_my_leave_requests(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[LeaveRequestResponse]:
    service = LeaveRequestService(db)
    return service.list_my_requests(current_user=current_user)


@router.get("/leave-requests/team", response_model=list[LeaveRequestResponse])
def list_team_leave_requests(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    status: LeaveRequestStatus | None = LeaveRequestStatus.PENDING,
) -> list[LeaveRequestResponse]:
    service = LeaveRequestService(db)
    return service.list_team_requests(current_user=current_user, status=status)


@router.put("/leave-requests/{leave_request_id}/approve", response_model=LeaveRequestResponse)
def approve_leave_request(
    leave_request_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> LeaveRequestResponse:
    service = LeaveRequestService(db)
    return service.approve_request(current_user=current_user, leave_request_id=leave_request_id)


@router.put("/leave-requests/{leave_request_id}/reject", response_model=LeaveRequestResponse)
def reject_leave_request(
    leave_request_id: int,
    payload: LeaveRequestRejectRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> LeaveRequestResponse:
    service = LeaveRequestService(db)
    return service.reject_request(
        current_user=current_user,
        leave_request_id=leave_request_id,
        payload=payload,
    )
