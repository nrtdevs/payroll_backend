from datetime import date

from sqlalchemy import case, extract, func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.holiday import Holiday, HolidayType


class HolidayRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_holiday_type(self, holiday_type: HolidayType) -> HolidayType:
        self.db.add(holiday_type)
        self.db.flush()
        self.db.refresh(holiday_type)
        return holiday_type

    def get_holiday_type_by_id(self, holiday_type_id: int) -> HolidayType | None:
        return self.db.query(HolidayType).filter(HolidayType.id == holiday_type_id).first()

    def get_holiday_type_by_name(self, name: str) -> HolidayType | None:
        return self.db.query(HolidayType).filter(func.lower(HolidayType.name) == name.lower()).first()

    def list_holiday_types(self) -> list[HolidayType]:
        return (
            self.db.query(HolidayType)
            .filter(HolidayType.is_active.is_(True))
            .order_by(HolidayType.id.asc())
            .all()
        )

    def create_holiday(self, holiday: Holiday) -> Holiday:
        self.db.add(holiday)
        self.db.flush()
        self.db.refresh(holiday)
        return holiday

    def get_holiday_by_id(self, holiday_id: int) -> Holiday | None:
        return (
            self.db.query(Holiday)
            .options(joinedload(Holiday.holiday_type), joinedload(Holiday.session))
            .filter(Holiday.id == holiday_id)
            .first()
        )

    def list_holidays(
        self,
        *,
        session_id: int | None = None,
        branch_id: int | None = None,
        year: int | None = None,
    ) -> list[Holiday]:
        query = self.db.query(Holiday).options(
            joinedload(Holiday.holiday_type),
            joinedload(Holiday.session),
        ).filter(Holiday.is_active.is_(True))

        if session_id is not None:
            query = query.filter(Holiday.session_id == session_id)
        if branch_id is not None:
            query = query.filter(Holiday.branch_id == branch_id)
        if year is not None:
            query = query.filter(extract("year", Holiday.holiday_date) == year)

        return query.order_by(Holiday.holiday_date.asc(), Holiday.id.asc()).all()

    def find_duplicate_holiday(
        self,
        *,
        holiday_date: date,
        session_id: int,
        branch_id: int | None,
        exclude_holiday_id: int | None = None,
    ) -> Holiday | None:
        query = self.db.query(Holiday).filter(
            Holiday.is_active.is_(True),
            Holiday.holiday_date == holiday_date,
            Holiday.session_id == session_id,
        )
        if branch_id is None:
            query = query.filter(Holiday.branch_id.is_(None))
        else:
            query = query.filter(Holiday.branch_id == branch_id)
        if exclude_holiday_id is not None:
            query = query.filter(Holiday.id != exclude_holiday_id)
        return query.first()

    def get_holiday_for_date(self, *, session_id: int, branch_id: int | None, target_date: date) -> Holiday | None:
        query = (
            self.db.query(Holiday)
            .options(joinedload(Holiday.holiday_type), joinedload(Holiday.session))
            .filter(
                Holiday.is_active.is_(True),
                Holiday.session_id == session_id,
                Holiday.holiday_date == target_date,
            )
        )
        if branch_id is not None:
            query = query.filter(or_(Holiday.branch_id == branch_id, Holiday.branch_id.is_(None)))
            query = query.order_by(case((Holiday.branch_id == branch_id, 0), else_=1), Holiday.id.asc())
        else:
            query = query.filter(Holiday.branch_id.is_(None)).order_by(Holiday.id.asc())
        return query.first()
