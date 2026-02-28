from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.employment_type import EmploymentType


class EmploymentTypeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, *, name: str) -> EmploymentType:
        employment_type = EmploymentType(name=name)
        self.db.add(employment_type)
        self.db.flush()
        self.db.refresh(employment_type)
        return employment_type

    def get_by_id(self, employment_type_id: int) -> EmploymentType | None:
        return self.db.query(EmploymentType).filter(EmploymentType.id == employment_type_id).first()

    def get_by_name(self, name: str) -> EmploymentType | None:
        return (
            self.db.query(EmploymentType)
            .filter(func.lower(EmploymentType.name) == name.lower())
            .first()
        )

    def list_all(self) -> list[EmploymentType]:
        return self.db.query(EmploymentType).order_by(EmploymentType.id.asc()).all()

    def update(self, employment_type: EmploymentType, *, name: str) -> EmploymentType:
        employment_type.name = name
        self.db.flush()
        self.db.refresh(employment_type)
        return employment_type

    def delete(self, employment_type: EmploymentType) -> None:
        self.db.delete(employment_type)
        self.db.flush()
