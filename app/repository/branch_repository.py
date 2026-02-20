from sqlalchemy.orm import Session

from app.models.branch import Branch


class BranchRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        name: str,
        address: str,
        city: str,
        state: str,
        country: str,
    ) -> Branch:
        branch = Branch(
            name=name,
            address=address,
            city=city,
            state=state,
            country=country,
        )
        self.db.add(branch)
        self.db.flush()
        self.db.refresh(branch)
        return branch

    def get_by_id(self, branch_id: int) -> Branch | None:
        return self.db.query(Branch).filter(Branch.id == branch_id).first()

    def list_all(self) -> list[Branch]:
        return self.db.query(Branch).order_by(Branch.id.asc()).all()

    def list_paginated(
        self,
        *,
        page: int,
        size: int,
        name: str | None = None,
        city: str | None = None,
        state: str | None = None,
        country: str | None = None,
    ) -> tuple[list[Branch], int]:
        query = self.db.query(Branch)

        if name:
            query = query.filter(Branch.name.ilike(f"%{name.strip()}%"))
        if city:
            query = query.filter(Branch.city.ilike(f"%{city.strip()}%"))
        if state:
            query = query.filter(Branch.state.ilike(f"%{state.strip()}%"))
        if country:
            query = query.filter(Branch.country.ilike(f"%{country.strip()}%"))

        total = query.count()
        items = (
            query.order_by(Branch.id.asc())
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )
        return items, total

    def update(
        self,
        branch: Branch,
        *,
        name: str,
        address: str,
        city: str,
        state: str,
        country: str,
    ) -> Branch:
        branch.name = name
        branch.address = address
        branch.city = city
        branch.state = state
        branch.country = country
        self.db.flush()
        self.db.refresh(branch)
        return branch

    def delete(self, branch: Branch) -> None:
        self.db.delete(branch)
        self.db.flush()
