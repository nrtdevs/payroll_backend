from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BranchCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    address: str = Field(min_length=3, max_length=500)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    country: str = Field(min_length=2, max_length=100)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    radius_meters: int = Field(default=200, ge=1, le=10000)


class BranchUpdateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    address: str = Field(min_length=3, max_length=500)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    country: str = Field(min_length=2, max_length=100)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    radius_meters: int = Field(default=200, ge=1, le=10000)


class BranchResponse(BaseModel):
    id: int
    name: str
    address: str
    city: str
    state: str
    country: str
    latitude: float | None
    longitude: float | None
    radius_meters: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BranchListResponse(BaseModel):
    items: list[BranchResponse]
    page: int
    size: int
    total: int
    total_pages: int
