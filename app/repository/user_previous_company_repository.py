from sqlalchemy.orm import Session

from app.models.user_previous_company import UserPreviousCompany


class UserPreviousCompanyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, company: UserPreviousCompany) -> UserPreviousCompany:
        self.db.add(company)
        self.db.flush()
        return company

    def list_by_user_id(self, user_id: int) -> list[UserPreviousCompany]:
        return (
            self.db.query(UserPreviousCompany)
            .filter(UserPreviousCompany.user_id == user_id)
            .order_by(UserPreviousCompany.id.asc())
            .all()
        )

    def delete_by_user_id(self, user_id: int) -> None:
        self.db.query(UserPreviousCompany).filter(UserPreviousCompany.user_id == user_id).delete(
            synchronize_session=False
        )
