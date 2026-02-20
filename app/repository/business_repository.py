from sqlalchemy.orm import Session

from app.models.business import Business


class BusinessRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, name: str) -> Business:
        business = Business(name=name)
        self.db.add(business)
        self.db.flush()
        self.db.refresh(business)
        return business

    def get_by_id(self, business_id: int) -> Business | None:
        return self.db.query(Business).filter(Business.id == business_id).first()
