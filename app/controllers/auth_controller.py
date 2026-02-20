from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_token, get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, LogoutResponse, TokenResponse
from app.services.auth_service import AuthService


router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    service = AuthService(db)
    return service.login(username=payload.username, password=payload.password)


@router.post("/logout", response_model=LogoutResponse)
def logout(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    token: Annotated[str, Depends(get_current_token)],
) -> LogoutResponse:
    service = AuthService(db)
    return service.logout(token=token)
