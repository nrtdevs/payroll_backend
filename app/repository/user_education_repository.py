from sqlalchemy.orm import Session

from app.models.user_education import UserEducation


class UserEducationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, education: UserEducation) -> UserEducation:
        self.db.add(education)
        self.db.flush()
        return education

    def update(self, education: UserEducation) -> UserEducation:
        self.db.add(education)
        self.db.flush()
        return education

    def list_by_user_id(self, user_id: int) -> list[UserEducation]:
        return (
            self.db.query(UserEducation)
            .filter(UserEducation.user_id == user_id)
            .order_by(UserEducation.id.asc())
            .all()
        )

    def delete_by_user_id(self, user_id: int) -> None:
        self.db.query(UserEducation).filter(UserEducation.user_id == user_id).delete(
            synchronize_session=False
        )

    def delete(self, education: UserEducation) -> None:
        self.db.delete(education)
        self.db.flush()
