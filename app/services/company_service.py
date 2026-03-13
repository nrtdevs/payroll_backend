from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BadRequestException, FileValidationException, NotFoundException
from app.models.company import Company
from app.models.user import User
from app.repository.company_repository import CompanyRepository
from app.schemas.company import CompanyResponse, CompanyUpsertRequest


class CompanyService:
    ALLOWED_LOGO_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
    ALLOWED_LOGO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

    def __init__(self, db: Session) -> None:
        self.db = db
        self.company_repository = CompanyRepository(db)

    def get_company(self, actor: User) -> CompanyResponse:
        _ = actor
        company = self.company_repository.get_single()
        if company is None:
            raise NotFoundException("Company profile not found")
        return self._to_response(company)

    def upsert_company(self, actor: User, payload: CompanyUpsertRequest) -> CompanyResponse:
        _ = actor
        company = self.company_repository.get_single()

        if company is None:
            company = Company(company_name=payload.company_name)
            self.company_repository.create(company)

        company.company_name = payload.company_name
        company.legal_name = payload.legal_name
        company.pan_number = payload.pan_number
        company.tan_number = payload.tan_number
        company.gst_number = payload.gst_number
        company.pf_number = payload.pf_number
        company.esi_number = payload.esi_number
        company.email = payload.email
        company.phone = payload.phone
        company.website = payload.website
        company.logo_url = payload.logo_url if payload.logo_url is not None else company.logo_url
        company.address_line1 = payload.address_line1
        company.address_line2 = payload.address_line2
        company.city = payload.city
        company.state = payload.state
        company.country = payload.country
        company.pincode = payload.pincode

        try:
            self.db.commit()
            self.db.refresh(company)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise BadRequestException("Unable to save company profile") from exc

        return self._to_response(company)

    def upload_logo(self, actor: User, upload: UploadFile) -> CompanyResponse:
        _ = actor
        company = self.company_repository.get_single()
        if company is None:
            raise NotFoundException("Company profile not found. Save company first.")

        original_filename = (upload.filename or "").strip()
        extension = Path(original_filename).suffix.lower()
        if extension not in self.ALLOWED_LOGO_EXTENSIONS:
            raise FileValidationException("Unsupported logo file extension")

        content_type = (upload.content_type or "").strip().lower()
        if content_type not in self.ALLOWED_LOGO_MIME_TYPES:
            raise FileValidationException("Unsupported logo file type")

        binary_data = upload.file.read()
        if not binary_data:
            raise FileValidationException("Uploaded logo is empty")
        if len(binary_data) > settings.max_file_size_bytes:
            raise FileValidationException(
                f"Logo exceeds allowed size of {settings.max_file_size_bytes} bytes"
            )

        root = Path(settings.upload_root_dir).resolve()
        company_dir = (root / "company").resolve()
        company_dir.mkdir(parents=True, exist_ok=True)

        new_filename = f"company_logo_{uuid4().hex}{extension}"
        target_path = (company_dir / new_filename).resolve()
        target_path.write_bytes(binary_data)

        company.logo_url = str(target_path)
        try:
            self.db.commit()
            self.db.refresh(company)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise BadRequestException("Unable to save company logo") from exc

        return self._to_response(company)

    @staticmethod
    def _to_response(company: Company) -> CompanyResponse:
        return CompanyResponse(
            id=company.id,
            company_name=company.company_name,
            legal_name=company.legal_name,
            pan_number=company.pan_number,
            tan_number=company.tan_number,
            gst_number=company.gst_number,
            pf_number=company.pf_number,
            esi_number=company.esi_number,
            email=company.email,
            phone=company.phone,
            website=company.website,
            logo_url=company.logo_url,
            address_line1=company.address_line1,
            address_line2=company.address_line2,
            city=company.city,
            state=company.state,
            country=company.country,
            pincode=company.pincode,
            created_at=company.created_at,
            updated_at=company.updated_at,
        )
