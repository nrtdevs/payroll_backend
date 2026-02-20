from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BusinessResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
