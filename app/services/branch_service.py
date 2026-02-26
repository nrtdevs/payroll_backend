from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.models.branch import Branch
from app.models.user import User
from app.repository.branch_repository import BranchRepository
from app.schemas.branch import BranchCreateRequest, BranchListResponse, BranchUpdateRequest


class BranchService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.branch_repository = BranchRepository(db)

    def create_branch(self, actor: User, payload: BranchCreateRequest) -> Branch:
        branch = self.branch_repository.create(
            name=payload.name,
            address=payload.address,
            city=payload.city,
            state=payload.state,
            country=payload.country,
            latitude=payload.latitude,
            longitude=payload.longitude,
            radius_meters=payload.radius_meters,
        )
        self.db.commit()
        self.db.refresh(branch)
        return branch

    def list_branches(self, actor: User) -> list[Branch]:
        return self.branch_repository.list_all()

    def list_branches_paginated(
        self,
        actor: User,
        *,
        page: int,
        size: int,
        name: str | None = None,
        city: str | None = None,
        state: str | None = None,
        country: str | None = None,
    ) -> BranchListResponse:
        _ = actor
        items, total = self.branch_repository.list_paginated(
            page=page,
            size=size,
            name=name,
            city=city,
            state=state,
            country=country,
        )
        total_pages = (total + size - 1) // size if total > 0 else 0
        return BranchListResponse(
            items=items,
            page=page,
            size=size,
            total=total,
            total_pages=total_pages,
        )

    def get_branch(self, actor: User, branch_id: int) -> Branch:
        branch = self.branch_repository.get_by_id(branch_id)
        if branch is None:
            raise NotFoundException("Branch not found")
        return branch

    def update_branch(self, actor: User, branch_id: int, payload: BranchUpdateRequest) -> Branch:
        branch = self.branch_repository.get_by_id(branch_id)
        if branch is None:
            raise NotFoundException("Branch not found")

        updated = self.branch_repository.update(
            branch,
            name=payload.name,
            address=payload.address,
            city=payload.city,
            state=payload.state,
            country=payload.country,
            latitude=payload.latitude,
            longitude=payload.longitude,
            radius_meters=payload.radius_meters,
        )
        self.db.commit()
        self.db.refresh(updated)
        return updated

    def delete_branch(self, actor: User, branch_id: int) -> None:
        branch = self.branch_repository.get_by_id(branch_id)
        if branch is None:
            raise NotFoundException("Branch not found")

        self.branch_repository.delete(branch)
        self.db.commit()
