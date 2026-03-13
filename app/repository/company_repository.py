from sqlalchemy.orm import Session

from app.models.company import Company


class CompanyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_single(self) -> Company | None:
        return self.db.query(Company).order_by(Company.id.asc()).first()

    def create(self, company: Company) -> Company:
        self.db.add(company)
        self.db.flush()
        self.db.refresh(company)
        return company
