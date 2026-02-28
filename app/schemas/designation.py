from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DesignationCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    is_active: bool = True


class DesignationUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None
    is_active: bool = True


class DesignationResponse(BaseModel):
    id: int
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
