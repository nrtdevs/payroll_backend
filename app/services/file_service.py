from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import FileValidationException
from app.models.user_document import UserDocumentType


@dataclass(frozen=True)
class StoredFile:
    original_filename: str
    stored_filename: str
    file_path: str
    content_type: str
    file_size: int
    checksum: str


class FileService:
    DOCUMENT_MIME_TYPES: dict[UserDocumentType, set[str]] = {
        UserDocumentType.PROFILE_IMAGE: {"image/jpeg", "image/png", "image/webp"},
        UserDocumentType.AADHAAR_COPY: {"application/pdf", "image/jpeg", "image/png"},
        UserDocumentType.PAN_COPY: {"application/pdf", "image/jpeg", "image/png"},
        UserDocumentType.BANK_PROOF: {"application/pdf", "image/jpeg", "image/png"},
        UserDocumentType.EDUCATION_MARKSHEET: {"application/pdf", "image/jpeg", "image/png"},
        UserDocumentType.EXPERIENCE_PROOF: {"application/pdf", "image/jpeg", "image/png"},
    }

    EXTENSION_MIME_MAP: dict[str, str] = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }

    def __init__(self, root_dir: str | None = None) -> None:
        self.root_dir = Path(root_dir or settings.upload_root_dir).resolve()

    def store(
        self,
        *,
        upload: UploadFile,
        document_type: UserDocumentType,
        user_id: int,
    ) -> StoredFile:
        original_filename = (upload.filename or "").strip()
        if not original_filename:
            raise FileValidationException("Uploaded file must have a filename")

        extension = Path(original_filename).suffix.lower()
        if extension not in self.EXTENSION_MIME_MAP:
            raise FileValidationException("Unsupported file extension")

        content_type = (upload.content_type or "").strip().lower()
        if not content_type:
            content_type = self.EXTENSION_MIME_MAP[extension]
        if content_type not in self.DOCUMENT_MIME_TYPES[document_type]:
            raise FileValidationException(f"Invalid file type for {document_type.value}")

        binary_data = upload.file.read()
        file_size = len(binary_data)
        if file_size <= 0:
            raise FileValidationException("Uploaded file is empty")
        if file_size > settings.max_file_size_bytes:
            raise FileValidationException(
                f"File exceeds allowed size of {settings.max_file_size_bytes} bytes"
            )

        checksum = sha256(binary_data).hexdigest()
        safe_filename = f"{uuid4().hex}{extension}"

        user_dir = (self.root_dir / str(user_id)).resolve()
        if self.root_dir not in user_dir.parents and user_dir != self.root_dir:
            raise FileValidationException("Invalid file storage path")
        user_dir.mkdir(parents=True, exist_ok=True)

        target_path = (user_dir / safe_filename).resolve()
        if self.root_dir not in target_path.parents and target_path.parent != self.root_dir:
            raise FileValidationException("Invalid target file path")
        target_path.write_bytes(binary_data)

        return StoredFile(
            original_filename=original_filename,
            stored_filename=safe_filename,
            file_path=str(target_path),
            content_type=content_type,
            file_size=file_size,
            checksum=checksum,
        )

    def delete_file(self, file_path: str) -> None:
        path = Path(file_path)
        if path.exists() and path.is_file():
            path.unlink(missing_ok=True)

    def delete_many(self, file_paths: list[str]) -> None:
        for file_path in file_paths:
            self.delete_file(file_path)
