from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import UnauthorizedException
from app.core.security import create_access_token, decode_access_token, verify_password
from app.repository.revoked_token_repository import RevokedTokenRepository
from app.repository.user_repository import UserRepository
from app.schemas.auth import LogoutResponse, TokenResponse
from app.services.user_service import UserService


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_repository = UserRepository(db)
        self.revoked_token_repository = RevokedTokenRepository(db)

    def login(self, username: str, password: str) -> TokenResponse:
        user = self.user_repository.get_by_username_or_email(username)
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedException("Invalid username/email or password")

        token = create_access_token(subject=str(user.id))
        user_response = UserService(self.db).get_me(current_user=user)
        return TokenResponse(access_token=token, user=user_response)

    def logout(self, token: str) -> LogoutResponse:
        try:
            payload = decode_access_token(token)
        except ValueError as exc:
            raise UnauthorizedException("Invalid bearer token") from exc

        jti = payload.get("jti")
        exp = payload.get("exp")
        if not isinstance(jti, str) or exp is None:
            raise UnauthorizedException("Invalid token payload")

        if not self.revoked_token_repository.exists_by_jti(jti):
            if isinstance(exp, (int, float)):
                expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
            else:
                raise UnauthorizedException("Invalid token expiry")
            self.revoked_token_repository.create(jti=jti, expires_at=expires_at)
            self.db.commit()

        return LogoutResponse(detail="Logout successfully")
