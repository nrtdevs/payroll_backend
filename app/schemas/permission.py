from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreatePermissionRequest(BaseModel):
    permission_name: str = Field(min_length=2, max_length=150)
    group: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=2, max_length=500)


class UpdatePermissionRequest(BaseModel):
    permission_name: str = Field(min_length=2, max_length=150)
    group: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=2, max_length=500)


class PermissionResponse(BaseModel):
    id: int
    permission_name: str
    group: str
    description: str
    created_at: datetime
    created_by: int

    model_config = ConfigDict(from_attributes=True)


class PermissionListResponse(BaseModel):
    items: list[PermissionResponse]
    page: int
    size: int
    total: int
    total_pages: int
