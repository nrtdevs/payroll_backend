from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AssignRolePermissionsRequest(BaseModel):
    permission_ids: list[int] = Field(default_factory=list, alias="permissionIds")

    model_config = ConfigDict(populate_by_name=True)


class RolePermissionItemResponse(BaseModel):
    id: int
    name: str
    group: str


class RolePermissionsResponse(BaseModel):
    role_id: int = Field(serialization_alias="roleId")
    role_name: str = Field(serialization_alias="roleName")
    permissions: list[RolePermissionItemResponse]
    page: int
    size: int
    total: int
    total_pages: int = Field(serialization_alias="totalPages")

    model_config = ConfigDict(populate_by_name=True)


class RolePermissionCountItemResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    permission_count: int = Field(serialization_alias="permissionCount")

    model_config = ConfigDict(populate_by_name=True)


class RolePermissionCountListResponse(BaseModel):
    items: list[RolePermissionCountItemResponse]
    page: int
    size: int
    total: int
    total_pages: int = Field(serialization_alias="totalPages")

    model_config = ConfigDict(populate_by_name=True)
