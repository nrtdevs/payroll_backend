from datetime import datetime

from sqlalchemy.orm import Session

from app.models.revoked_token import RevokedToken


class RevokedTokenRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, jti: str, expires_at: datetime) -> RevokedToken:
        revoked = RevokedToken(jti=jti, expires_at=expires_at)
        self.db.add(revoked)
        self.db.flush()
        self.db.refresh(revoked)
        return revoked

    def exists_by_jti(self, jti: str) -> bool:
        return self.db.query(RevokedToken).filter(RevokedToken.jti == jti).first() is not None
