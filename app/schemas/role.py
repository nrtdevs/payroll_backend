from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateRoleRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class RoleResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoleListResponse(BaseModel):
    items: list[RoleResponse]
    page: int
    size: int
    total: int
    total_pages: int
