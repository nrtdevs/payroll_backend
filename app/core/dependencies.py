from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_access_token
from app.models.role import RoleEnum
from app.repository.role_permission_repository import RolePermissionRepository
from app.repository.revoked_token_repository import RevokedTokenRepository
from app.models.user import User
from app.repository.user_repository import UserRepository


token_bearer = HTTPBearer(auto_error=False)


def _normalize_role_value(role: RoleEnum | str | None) -> str | None:
    if role is None:
        return None
    if isinstance(role, RoleEnum):
        return role.value
    return role.strip().upper()


def get_current_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(token_bearer)],
) -> str:
    if credentials is None:
        raise UnauthorizedException("Missing bearer token")
    return credentials.credentials


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(token_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None:
        raise UnauthorizedException("Missing bearer token")

    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise UnauthorizedException("Invalid bearer token") from exc
    user_id = payload.get("sub")
    jti = payload.get("jti")
    if user_id is None:
        raise UnauthorizedException("Invalid token payload")
    if jti is None or not isinstance(jti, str):
        raise UnauthorizedException("Invalid token payload")
    if RevokedTokenRepository(db).exists_by_jti(jti):
        raise UnauthorizedException("Token has been logged out")
    try:
        parsed_user_id = int(user_id)
    except (TypeError, ValueError) as exc:
        raise UnauthorizedException("Invalid token subject") from exc

    user = UserRepository(db).get_by_id(parsed_user_id)
    if user is None:
        raise UnauthorizedException("User from token does not exist")
    return user


def require_roles(*roles: RoleEnum) -> Callable[[User], User]:
    def _role_checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        # Token-based access mode: if user is authenticated, allow.
        return current_user

    return _role_checker


def require_permission(permission_name: str) -> Callable[[User, Session], User]:
    normalized_permission = permission_name.strip().upper()

    def _permission_checker(
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[Session, Depends(get_db)],
    ) -> User:
        if current_user.role_id is None:
            raise ForbiddenException("You do not have permission: role is not assigned")

        has_permission = RolePermissionRepository(db).has_permission_for_role(
            role_id=current_user.role_id,
            permission_name=normalized_permission,
        )
        if not has_permission:
            raise ForbiddenException(f"You do not have permission: {normalized_permission}")
        return current_user

    return _permission_checker


def ensure_same_business_or_master(actor: User, business_id: int | None) -> None:
    if actor.role == RoleEnum.MASTER_ADMIN:
        return
    if actor.business_id is None:
        raise ForbiddenException("User is not assigned to a business")
    if business_id != actor.business_id:
        raise ForbiddenException("Cross-business access is forbidden")
