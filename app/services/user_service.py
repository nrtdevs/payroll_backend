from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.dependencies import ensure_same_business_or_master
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.core.security import hash_password
from app.models.role import RoleEnum
from app.models.user import User
from app.models.user_bank_account import UserBankAccount
from app.models.user_document import UserDocument, UserDocumentType
from app.models.user_education import UserEducation
from app.models.user_previous_company import UserPreviousCompany
from app.repository.branch_repository import BranchRepository
from app.repository.business_repository import BusinessRepository
from app.repository.role_repository import RoleRepository
from app.repository.user_bank_account_repository import UserBankAccountRepository
from app.repository.user_document_repository import UserDocumentRepository
from app.repository.user_education_repository import UserEducationRepository
from app.repository.user_previous_company_repository import UserPreviousCompanyRepository
from app.repository.user_repository import UserRepository
from app.schemas.user import (
    UserBankAccountResponse,
    UserCreateRequest,
    UserDocumentResponse,
    UserEducationResponse,
    UserListResponse,
    UserPreviousCompanyResponse,
    UserResponse,
    UserUpdateRequest,
)
from app.services.file_service import FileService


@dataclass
class UserFilePayload:
    profile_image: UploadFile | None = None
    aadhaar_copy: UploadFile | None = None
    pan_copy: UploadFile | None = None
    bank_proof: UploadFile | None = None
    education_marksheets: list[UploadFile] = field(default_factory=list)
    education_file_map: dict[str, list[int]] = field(default_factory=dict)
    experience_proofs: list[UploadFile] = field(default_factory=list)
    company_file_map: dict[str, list[int]] = field(default_factory=dict)


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_repository = UserRepository(db)
        self.business_repository = BusinessRepository(db)
        self.branch_repository = BranchRepository(db)
        self.role_repository = RoleRepository(db)
        self.education_repository = UserEducationRepository(db)
        self.previous_company_repository = UserPreviousCompanyRepository(db)
        self.bank_account_repository = UserBankAccountRepository(db)
        self.document_repository = UserDocumentRepository(db)
        self.file_service = FileService()

    def get_me(self, current_user: User) -> UserResponse:
        refreshed = self.user_repository.get_by_id(current_user.id)
        if refreshed is None:
            raise NotFoundException("User not found")
        return self._build_user_response(refreshed)

    def list_users(self, current_user: User) -> list[UserResponse]:
        users = self.user_repository.list_for_actor(current_user)
        return [self._build_user_response(item) for item in users]

    def list_users_paginated(
        self,
        current_user: User,
        *,
        page: int,
        size: int,
        first_name: str | None = None,
        mobile_number: str | None = None,
        branch_id: int | None = None,
    ) -> UserListResponse:
        items, total = self.user_repository.list_paginated_for_actor(
            current_user,
            page=page,
            size=size,
            first_name=first_name,
            mobile_number=mobile_number,
            branch_id=branch_id,
        )
        total_pages = (total + size - 1) // size if total > 0 else 0
        return UserListResponse(
            items=[self._build_user_response(item) for item in items],
            page=page,
            size=size,
            total=total,
            total_pages=total_pages,
        )

    def create_user(self, actor: User, payload: UserCreateRequest, files: UserFilePayload) -> UserResponse:
        target_business_id = self._resolve_actor_business_id(actor)
        self._ensure_business_exists(target_business_id)
        self._ensure_role_exists(payload.role_id)
        self._ensure_branch_exists(payload.branch_id)
        self._ensure_unique_identity_for_create(payload.email, payload.pan, payload.aadhaar, payload.mobile)
        self._validate_file_maps(payload, files)

        created_file_paths: list[str] = []
        try:
            user = User(
                username=payload.email.lower(),
                email=payload.email.lower(),
                first_name=payload.name,
                middle_name=None,
                last_name="",
                password_hash=hash_password(payload.password),
                role=RoleEnum.BUSINESS_EMPLOYEE,
                business_id=target_business_id,
                name=payload.name,
                branch_id=payload.branch_id,
                role_id=payload.role_id,
                salary_type=payload.salary_type,
                salary=payload.salary,
                leave_balance=payload.leave_balance,
                status=payload.status,
                current_address=payload.current_address,
                home_address=payload.home_address,
                pan=payload.pan.upper(),
                aadhaar=payload.aadhaar,
                mobile=payload.mobile,
                number=payload.number,
                father_name=payload.father_name,
                mother_name=payload.mother_name,
            )
            self.user_repository.create(user)
            self._upsert_bank_account(user_id=user.id, payload=payload.bank_account.model_dump())
            self._replace_educations(
                user_id=user.id,
                payload=payload,
                files=files,
                created_file_paths=created_file_paths,
            )
            self._replace_companies(
                user_id=user.id,
                payload=payload,
                files=files,
                created_file_paths=created_file_paths,
            )
            self._upsert_singleton_documents(
                user_id=user.id,
                files=files,
                created_file_paths=created_file_paths,
                require_all_singletons=True,
            )
            self.db.commit()
            fresh_user = self.user_repository.get_by_id(user.id)
            if fresh_user is None:
                raise NotFoundException("User not found after creation")
            return self._build_user_response(fresh_user)
        except Exception:
            self.db.rollback()
            self.file_service.delete_many(created_file_paths)
            raise

    def get_user(self, actor: User, user_id: int) -> UserResponse:
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise NotFoundException("User not found")
        self._ensure_user_access(actor, user)
        return self._build_user_response(user)

    def update_user(
        self,
        actor: User,
        user_id: int,
        payload: UserUpdateRequest,
        files: UserFilePayload,
    ) -> UserResponse:
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise NotFoundException("User not found")
        self._ensure_user_access(actor, user)

        target_business_id = self._resolve_target_business_id(actor, payload.business_id, fallback=user.business_id)
        self._ensure_business_exists(target_business_id)
        self._ensure_role_exists(payload.role_id)
        self._ensure_branch_exists(payload.branch_id)
        self._ensure_unique_identity_for_update(
            user,
            payload.email,
            payload.pan,
            payload.aadhaar,
            payload.mobile,
        )
        self._validate_file_maps(
            payload,
            files,
            require_distinct_file_indexes=True,
        )

        created_file_paths: list[str] = []
        deleted_file_paths: list[str] = []
        try:
            user.username = payload.email.lower()
            user.email = payload.email.lower()
            user.first_name = payload.name
            user.name = payload.name
            user.branch_id = payload.branch_id
            user.role_id = payload.role_id
            user.salary_type = payload.salary_type
            user.salary = payload.salary
            user.leave_balance = payload.leave_balance
            user.status = payload.status
            user.current_address = payload.current_address
            user.home_address = payload.home_address
            user.pan = payload.pan.upper()
            user.aadhaar = payload.aadhaar
            user.mobile = payload.mobile
            user.number = payload.number
            user.father_name = payload.father_name
            user.mother_name = payload.mother_name
            user.business_id = target_business_id
            self.user_repository.update(user)

            self._upsert_bank_account(user_id=user.id, payload=payload.bank_account.model_dump())
            self._replace_educations(
                user_id=user.id,
                payload=payload,
                files=files,
                created_file_paths=created_file_paths,
                deleted_file_paths=deleted_file_paths,
            )
            self._replace_companies(
                user_id=user.id,
                payload=payload,
                files=files,
                created_file_paths=created_file_paths,
                deleted_file_paths=deleted_file_paths,
            )
            self._upsert_singleton_documents(
                user_id=user.id,
                files=files,
                created_file_paths=created_file_paths,
                deleted_file_paths=deleted_file_paths,
                require_all_singletons=False,
            )

            self.db.commit()
            self.file_service.delete_many(deleted_file_paths)
            fresh_user = self.user_repository.get_by_id(user.id)
            if fresh_user is None:
                raise NotFoundException("User not found after update")
            return self._build_user_response(fresh_user)
        except Exception:
            self.db.rollback()
            self.file_service.delete_many(created_file_paths)
            raise

    def delete_user(self, actor: User, user_id: int) -> None:
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise NotFoundException("User not found")
        self._ensure_user_access(actor, user)
        if user.role == RoleEnum.MASTER_ADMIN:
            raise ForbiddenException("Master admin user cannot be deleted")

        file_paths = [item.file_path for item in user.documents]
        self.user_repository.delete(user)
        self.db.commit()
        self.file_service.delete_many(file_paths)

    def get_document_preview(
        self,
        *,
        actor: User,
        user_id: int,
        document_id: int,
    ) -> FileResponse:
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise NotFoundException("User not found")
        self._ensure_document_access(actor=actor, target_user=user)

        document = self.document_repository.get_by_id(document_id)
        if document is None or document.user_id != user_id:
            raise NotFoundException("Document not found")

        file_path = Path(document.file_path)
        if not file_path.exists() or not file_path.is_file():
            raise NotFoundException("Document file not found on server")

        return FileResponse(
            path=str(file_path),
            media_type=document.content_type,
            filename=document.original_filename,
        )

    def _replace_educations(
        self,
        *,
        user_id: int,
        payload: UserCreateRequest | UserUpdateRequest,
        files: UserFilePayload,
        created_file_paths: list[str],
        deleted_file_paths: list[str] | None = None,
    ) -> None:
        if deleted_file_paths is None:
            deleted_file_paths = []

        existing_educations = self.education_repository.list_by_user_id(user_id)
        key_to_id: dict[str, int] = {}
        for index, item in enumerate(payload.educations):
            if index < len(existing_educations):
                education = existing_educations[index]
                education.degree = item.degree
                education.institution = item.institution
                education.year_of_passing = item.year_of_passing
                education.percentage = item.percentage
                self.education_repository.update(education)
            else:
                education = UserEducation(
                    user_id=user_id,
                    degree=item.degree,
                    institution=item.institution,
                    year_of_passing=item.year_of_passing,
                    percentage=item.percentage,
                )
                self.education_repository.create(education)
            key_to_id[item.record_key] = education.id

        for education in existing_educations[len(payload.educations) :]:
            old_docs = self.document_repository.list_by_education_id(education.id)
            deleted_file_paths.extend(item.file_path for item in old_docs)
            self.education_repository.delete(education)

        for record_key, indexes in files.education_file_map.items():
            education_id = key_to_id[record_key]
            old_docs = self.document_repository.list_by_education_id(education_id)
            if old_docs:
                deleted_file_paths.extend(item.file_path for item in old_docs)
                self.document_repository.delete_by_education_id(education_id)
            for index in indexes:
                upload = files.education_marksheets[index]
                self._create_document_for_file(
                    user_id=user_id,
                    document_type=UserDocumentType.EDUCATION_MARKSHEET,
                    upload=upload,
                    education_id=education_id,
                    created_file_paths=created_file_paths,
                )
        return None

    def _replace_companies(
        self,
        *,
        user_id: int,
        payload: UserCreateRequest | UserUpdateRequest,
        files: UserFilePayload,
        created_file_paths: list[str],
        deleted_file_paths: list[str] | None = None,
    ) -> None:
        if deleted_file_paths is None:
            deleted_file_paths = []

        existing_companies = self.previous_company_repository.list_by_user_id(user_id)
        key_to_id: dict[str, int] = {}
        for index, item in enumerate(payload.previous_companies):
            if index < len(existing_companies):
                company = existing_companies[index]
                company.company_name = item.company_name
                company.designation = item.designation
                company.start_date = item.start_date
                company.end_date = item.end_date
                self.previous_company_repository.update(company)
            else:
                company = UserPreviousCompany(
                    user_id=user_id,
                    company_name=item.company_name,
                    designation=item.designation,
                    start_date=item.start_date,
                    end_date=item.end_date,
                )
                self.previous_company_repository.create(company)
            key_to_id[item.record_key] = company.id

        for company in existing_companies[len(payload.previous_companies) :]:
            old_docs = self.document_repository.list_by_company_id(company.id)
            deleted_file_paths.extend(item.file_path for item in old_docs)
            self.previous_company_repository.delete(company)

        for record_key, indexes in files.company_file_map.items():
            company_id = key_to_id[record_key]
            old_docs = self.document_repository.list_by_company_id(company_id)
            if old_docs:
                deleted_file_paths.extend(item.file_path for item in old_docs)
                self.document_repository.delete_by_company_id(company_id)
            for index in indexes:
                upload = files.experience_proofs[index]
                self._create_document_for_file(
                    user_id=user_id,
                    document_type=UserDocumentType.EXPERIENCE_PROOF,
                    upload=upload,
                    company_id=company_id,
                    created_file_paths=created_file_paths,
                )
        return None

    def _upsert_bank_account(self, *, user_id: int, payload: dict[str, Any]) -> None:
        bank_account = self.bank_account_repository.get_by_user_id(user_id)
        if bank_account is None:
            self.bank_account_repository.create(
                UserBankAccount(
                    user_id=user_id,
                    account_holder_name=payload["account_holder_name"],
                    account_number=payload["account_number"],
                    ifsc_code=payload["ifsc_code"].upper(),
                    bank_name=payload["bank_name"],
                )
            )
            return

        bank_account.account_holder_name = payload["account_holder_name"]
        bank_account.account_number = payload["account_number"]
        bank_account.ifsc_code = payload["ifsc_code"].upper()
        bank_account.bank_name = payload["bank_name"]
        self.bank_account_repository.update(bank_account)

    def _upsert_singleton_documents(
        self,
        *,
        user_id: int,
        files: UserFilePayload,
        created_file_paths: list[str],
        deleted_file_paths: list[str] | None = None,
        require_all_singletons: bool,
    ) -> None:
        if deleted_file_paths is None:
            deleted_file_paths = []

        singleton_files: dict[UserDocumentType, UploadFile | None] = {
            UserDocumentType.PROFILE_IMAGE: files.profile_image,
            UserDocumentType.AADHAAR_COPY: files.aadhaar_copy,
            UserDocumentType.PAN_COPY: files.pan_copy,
            UserDocumentType.BANK_PROOF: files.bank_proof,
        }
        if require_all_singletons:
            missing = [doc_type.value for doc_type, upload in singleton_files.items() if upload is None]
            if missing:
                raise BadRequestException(f"Missing required document uploads: {', '.join(missing)}")

        for document_type, upload in singleton_files.items():
            if upload is None:
                continue
            old_doc = self.document_repository.get_singleton_by_user_and_type(
                user_id=user_id,
                document_type=document_type,
            )
            if old_doc is not None:
                deleted_file_paths.append(old_doc.file_path)
                self.document_repository.delete_singleton_by_user_and_type(
                    user_id=user_id,
                    document_type=document_type,
                )
            self._create_document_for_file(
                user_id=user_id,
                document_type=document_type,
                upload=upload,
                created_file_paths=created_file_paths,
            )

    def _create_document_for_file(
        self,
        *,
        user_id: int,
        document_type: UserDocumentType,
        upload: UploadFile,
        education_id: int | None = None,
        company_id: int | None = None,
        created_file_paths: list[str] | None = None,
    ) -> UserDocument:
        stored = self.file_service.store(upload=upload, document_type=document_type, user_id=user_id)
        if created_file_paths is not None:
            created_file_paths.append(stored.file_path)
        if self.document_repository.exists_by_user_type_checksum(
            user_id=user_id,
            document_type=document_type,
            checksum=stored.checksum,
        ):
            self.file_service.delete_file(stored.file_path)
            raise ConflictException(f"Duplicate document upload for {document_type.value}")
        document = UserDocument(
            user_id=user_id,
            education_id=education_id,
            company_id=company_id,
            document_type=document_type,
            original_filename=stored.original_filename,
            stored_filename=stored.stored_filename,
            file_path=stored.file_path,
            content_type=stored.content_type,
            file_size=stored.file_size,
            checksum=stored.checksum,
        )
        self.document_repository.create(document)
        return document

    def _validate_file_maps(
        self,
        payload: UserCreateRequest | UserUpdateRequest,
        files: UserFilePayload,
        *,
        require_file_for_each_record: bool = False,
        require_distinct_file_indexes: bool = False,
    ) -> None:
        education_keys = {item.record_key for item in payload.educations}
        company_keys = {item.record_key for item in payload.previous_companies}
        if len(education_keys) != len(payload.educations):
            raise BadRequestException("Duplicate education record_key is not allowed")
        if len(company_keys) != len(payload.previous_companies):
            raise BadRequestException("Duplicate previous_company record_key is not allowed")

        self._validate_single_file_map(
            entity_keys=education_keys,
            mapping=files.education_file_map,
            file_count=len(files.education_marksheets),
            context_name="education_file_map",
            require_file_for_each_record=require_file_for_each_record,
            require_distinct_file_indexes=require_distinct_file_indexes,
        )
        self._validate_single_file_map(
            entity_keys=company_keys,
            mapping=files.company_file_map,
            file_count=len(files.experience_proofs),
            context_name="company_file_map",
            require_file_for_each_record=require_file_for_each_record,
            require_distinct_file_indexes=require_distinct_file_indexes,
        )

    def _validate_single_file_map(
        self,
        *,
        entity_keys: set[str],
        mapping: dict[str, list[int]],
        file_count: int,
        context_name: str,
        require_file_for_each_record: bool,
        require_distinct_file_indexes: bool,
    ) -> None:
        if require_file_for_each_record:
            missing_keys = entity_keys - set(mapping.keys())
            if missing_keys:
                missing = ", ".join(sorted(missing_keys))
                raise BadRequestException(
                    f"Missing file mapping for record key(s) [{missing}] in {context_name}"
                )

        used_indexes: set[int] = set()
        for record_key, indexes in mapping.items():
            if record_key not in entity_keys:
                raise BadRequestException(f"Unknown record key '{record_key}' in {context_name}")
            if not indexes:
                raise BadRequestException(f"File indexes cannot be empty for key '{record_key}'")
            for index in indexes:
                if index < 0 or index >= file_count:
                    raise BadRequestException(f"Invalid file index '{index}' in {context_name}")
                if require_distinct_file_indexes and index in used_indexes:
                    raise BadRequestException(
                        f"File index '{index}' is mapped more than once in {context_name}"
                    )
                used_indexes.add(index)

    def _resolve_actor_business_id(self, actor: User) -> int:
        if actor.business_id is None:
            raise BadRequestException("Creator user is not assigned to any business")
        return actor.business_id

    def _ensure_user_access(self, actor: User, target_user: User) -> None:
        if actor.role == RoleEnum.MASTER_ADMIN:
            return
        if actor.role not in {RoleEnum.BUSINESS_OWNER, RoleEnum.BUSINESS_ADMIN}:
            raise ForbiddenException("Not enough permissions")
        ensure_same_business_or_master(actor, target_user.business_id)

    def _ensure_document_access(self, *, actor: User, target_user: User) -> None:
        if actor.role in {RoleEnum.MASTER_ADMIN, RoleEnum.BUSINESS_OWNER, RoleEnum.BUSINESS_ADMIN}:
            self._ensure_user_access(actor, target_user)
            return
        if actor.id != target_user.id:
            raise ForbiddenException("Not enough permissions")

    def _resolve_target_business_id(
        self,
        actor: User,
        requested_business_id: int | None,
        fallback: int | None = None,
    ) -> int | None:
        if actor.role == RoleEnum.MASTER_ADMIN:
            return requested_business_id if requested_business_id is not None else fallback

        if actor.business_id is None:
            raise ForbiddenException("User has no assigned business")

        if requested_business_id is not None and requested_business_id != actor.business_id:
            raise ForbiddenException("Cross-business access is forbidden")
        return actor.business_id

    def _ensure_business_exists(self, business_id: int | None) -> None:
        if business_id is None:
            return
        if self.business_repository.get_by_id(business_id) is None:
            raise NotFoundException("Business not found")

    def _ensure_role_exists(self, role_id: int) -> None:
        if self.role_repository.get_by_id(role_id) is None:
            raise NotFoundException("Role not found")

    def _ensure_branch_exists(self, branch_id: int) -> None:
        if self.branch_repository.get_by_id(branch_id) is None:
            raise NotFoundException("Branch not found")

    def _ensure_unique_identity_for_create(self, email: str, pan: str, aadhaar: str, mobile: str) -> None:
        if self.user_repository.get_by_email(email.lower()):
            raise ConflictException("Email already exists")
        if self.user_repository.get_by_username(email.lower()):
            raise ConflictException("Username already exists")
        if self.user_repository.get_by_pan(pan.upper()):
            raise ConflictException("PAN already exists")
        if self.user_repository.get_by_aadhaar(aadhaar):
            raise ConflictException("Aadhaar already exists")
        if self.user_repository.get_by_mobile(mobile):
            raise ConflictException("Mobile already exists")

    def _ensure_unique_identity_for_update(
        self,
        current_user: User,
        email: str,
        pan: str,
        aadhaar: str,
        mobile: str,
    ) -> None:
        existing_email = self.user_repository.get_by_email(email.lower())
        if existing_email is not None and existing_email.id != current_user.id:
            raise ConflictException("Email already exists")

        existing_username = self.user_repository.get_by_username(email.lower())
        if existing_username is not None and existing_username.id != current_user.id:
            raise ConflictException("Username already exists")

        existing_pan = self.user_repository.get_by_pan(pan.upper())
        if existing_pan is not None and existing_pan.id != current_user.id:
            raise ConflictException("PAN already exists")

        existing_aadhaar = self.user_repository.get_by_aadhaar(aadhaar)
        if existing_aadhaar is not None and existing_aadhaar.id != current_user.id:
            raise ConflictException("Aadhaar already exists")

        existing_mobile = self.user_repository.get_by_mobile(mobile)
        if existing_mobile is not None and existing_mobile.id != current_user.id:
            raise ConflictException("Mobile already exists")

    def _build_user_response(self, user: User) -> UserResponse:
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            first_name=user.first_name,
            middle_name=user.middle_name,
            last_name=user.last_name,
            role=user.role,
            business_id=user.business_id,
            name=user.name,
            branch_id=user.branch_id,
            role_id=user.role_id,
            salary_type=user.salary_type,
            salary=user.salary,
            leave_balance=user.leave_balance,
            status=user.status,
            current_address=user.current_address,
            home_address=user.home_address,
            pan=user.pan,
            aadhaar=self._mask_aadhaar(user.aadhaar),
            mobile=user.mobile,
            number=user.number,
            father_name=user.father_name,
            mother_name=user.mother_name,
            bank_account=self._build_bank_account_response(user.bank_account),
            educations=[self._build_education_response(item) for item in user.educations],
            previous_companies=[self._build_company_response(item) for item in user.previous_companies],
            documents=[
                self._build_document_response(item)
                for item in user.documents
                if item.education_id is None and item.company_id is None
            ],
            created_at=user.created_at,
        )

    def _build_education_response(self, education: UserEducation) -> UserEducationResponse:
        return UserEducationResponse(
            id=education.id,
            degree=education.degree,
            institution=education.institution,
            year_of_passing=education.year_of_passing,
            percentage=education.percentage,
            documents=[self._build_document_response(item) for item in education.documents],
        )

    def _build_company_response(self, company: UserPreviousCompany) -> UserPreviousCompanyResponse:
        return UserPreviousCompanyResponse(
            id=company.id,
            company_name=company.company_name,
            designation=company.designation,
            start_date=company.start_date,
            end_date=company.end_date,
            documents=[self._build_document_response(item) for item in company.documents],
        )

    def _build_bank_account_response(self, bank_account: UserBankAccount | None) -> UserBankAccountResponse | None:
        if bank_account is None:
            return None
        return UserBankAccountResponse(
            account_holder_name=bank_account.account_holder_name,
            account_number=self._mask_account_number(bank_account.account_number),
            ifsc_code=bank_account.ifsc_code,
            bank_name=bank_account.bank_name,
        )

    @staticmethod
    def _build_document_response(document: UserDocument) -> UserDocumentResponse:
        return UserDocumentResponse(
            id=document.id,
            document_type=document.document_type,
            original_filename=document.original_filename,
            content_type=document.content_type,
            file_size=document.file_size,
            created_at=document.created_at,
        )

    @staticmethod
    def _mask_aadhaar(value: str | None) -> str | None:
        if value is None:
            return None
        if len(value) <= 4:
            return "*" * len(value)
        return ("*" * (len(value) - 4)) + value[-4:]

    @staticmethod
    def _mask_account_number(value: str) -> str:
        if len(value) <= 4:
            return "*" * len(value)
        return ("*" * (len(value) - 4)) + value[-4:]
