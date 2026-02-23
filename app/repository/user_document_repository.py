from sqlalchemy.orm import Session

from app.models.user_document import UserDocument, UserDocumentType


class UserDocumentRepository:
    SINGLETON_TYPES: set[UserDocumentType] = {
        UserDocumentType.PROFILE_IMAGE,
        UserDocumentType.AADHAAR_COPY,
        UserDocumentType.PAN_COPY,
        UserDocumentType.BANK_PROOF,
    }

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, document: UserDocument) -> UserDocument:
        self.db.add(document)
        self.db.flush()
        return document

    def get_by_id(self, document_id: int) -> UserDocument | None:
        return self.db.query(UserDocument).filter(UserDocument.id == document_id).first()

    def exists_by_user_type_checksum(
        self,
        *,
        user_id: int,
        document_type: UserDocumentType,
        checksum: str,
    ) -> bool:
        return (
            self.db.query(UserDocument)
            .filter(
                UserDocument.user_id == user_id,
                UserDocument.document_type == document_type,
                UserDocument.checksum == checksum,
            )
            .first()
            is not None
        )

    def get_singleton_by_user_and_type(
        self,
        *,
        user_id: int,
        document_type: UserDocumentType,
    ) -> UserDocument | None:
        return (
            self.db.query(UserDocument)
            .filter(
                UserDocument.user_id == user_id,
                UserDocument.document_type == document_type,
                UserDocument.education_id.is_(None),
                UserDocument.company_id.is_(None),
            )
            .first()
        )

    def delete_singleton_by_user_and_type(
        self,
        *,
        user_id: int,
        document_type: UserDocumentType,
    ) -> None:
        (
            self.db.query(UserDocument)
            .filter(
                UserDocument.user_id == user_id,
                UserDocument.document_type == document_type,
                UserDocument.education_id.is_(None),
                UserDocument.company_id.is_(None),
            )
            .delete(synchronize_session=False)
        )
