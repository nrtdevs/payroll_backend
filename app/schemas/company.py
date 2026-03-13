from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class CompanyUpsertRequest(BaseModel):
    company_name: str = Field(min_length=2, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    pan_number: str | None = Field(default=None, max_length=20)
    tan_number: str | None = Field(default=None, max_length=20)
    gst_number: str | None = Field(default=None, max_length=30)
    pf_number: str | None = Field(default=None, max_length=50)
    esi_number: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    website: str | None = Field(default=None, max_length=255)
    logo_url: str | None = Field(default=None, max_length=500)
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    pincode: str | None = Field(default=None, max_length=20)


class CompanyResponse(BaseModel):
    id: int
    company_name: str
    legal_name: str | None
    pan_number: str | None
    tan_number: str | None
    gst_number: str | None
    pf_number: str | None
    esi_number: str | None
    email: str | None
    phone: str | None
    website: str | None
    logo_url: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    country: str | None
    pincode: str | None
    created_at: datetime
    updated_at: datetime
