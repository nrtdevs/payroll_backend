from sqlalchemy.orm import Session

from app.models.user_bank_account import UserBankAccount


class UserBankAccountRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_user_id(self, user_id: int) -> UserBankAccount | None:
        return (
            self.db.query(UserBankAccount)
            .filter(UserBankAccount.user_id == user_id)
            .first()
        )

    def create(self, bank_account: UserBankAccount) -> UserBankAccount:
        self.db.add(bank_account)
        self.db.flush()
        return bank_account

    def update(self, bank_account: UserBankAccount) -> UserBankAccount:
        self.db.flush()
        return bank_account
