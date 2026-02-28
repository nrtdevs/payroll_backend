from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.designation import Designation


class DesignationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        name: str,
        description: str | None,
        is_active: bool,
    ) -> Designation:
        designation = Designation(name=name, description=description, is_active=is_active)
        self.db.add(designation)
        self.db.flush()
        self.db.refresh(designation)
        return designation

    def get_by_id(self, designation_id: int) -> Designation | None:
        return self.db.query(Designation).filter(Designation.id == designation_id).first()

    def get_by_name(self, name: str) -> Designation | None:
        return (
            self.db.query(Designation)
            .filter(func.lower(Designation.name) == name.lower())
            .first()
        )

    def list_all(self) -> list[Designation]:
        return self.db.query(Designation).order_by(Designation.id.asc()).all()

    def update(
        self,
        designation: Designation,
        *,
        name: str,
        description: str | None,
        is_active: bool,
    ) -> Designation:
        designation.name = name
        designation.description = description
        designation.is_active = is_active
        self.db.flush()
        self.db.refresh(designation)
        return designation

    def delete(self, designation: Designation) -> None:
        self.db.delete(designation)
        self.db.flush()
