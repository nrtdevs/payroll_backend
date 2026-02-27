from __future__ import annotations

from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.attendance import Attendance
from app.models.user import User


class AttendanceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, attendance: Attendance) -> Attendance:
        self.db.add(attendance)
        self.db.flush()
        self.db.refresh(attendance)
        return attendance

    def update(self, attendance: Attendance) -> Attendance:
        self.db.flush()
        self.db.refresh(attendance)
        return attendance

    def get_by_user_and_date(self, user_id: int, attendance_date: date) -> Attendance | None:
        return (
            self.db.query(Attendance)
            .filter(Attendance.user_id == user_id, Attendance.attendance_date == attendance_date)
            .first()
        )

    def list_existing_user_ids_for_date(self, user_ids: list[int], attendance_date: date) -> set[int]:
        if not user_ids:
            return set()
        rows = (
            self.db.query(Attendance.user_id)
            .filter(Attendance.attendance_date == attendance_date, Attendance.user_id.in_(user_ids))
            .all()
        )
        return {int(item[0]) for item in rows}

    def list_by_user(
        self,
        user_id: int,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[Attendance]:
        query = self.db.query(Attendance).filter(Attendance.user_id == user_id)
        if start_date is not None:
            query = query.filter(Attendance.attendance_date >= start_date)
        if end_date is not None:
            query = query.filter(Attendance.attendance_date <= end_date)
        return query.order_by(Attendance.attendance_date.desc()).all()

    def list_paginated(
        self,
        *,
        business_id: int | None,
        user_id: int | None,
        branch_id: int | None,
        status: str | None,
        start_date: date | None,
        end_date: date | None,
        search: str | None,
        page: int,
        size: int,
    ) -> tuple[list[Attendance], int]:
        query = self.db.query(Attendance).join(User, Attendance.user_id == User.id)

        if business_id is not None:
            query = query.filter(User.business_id == business_id)
        if user_id is not None:
            query = query.filter(Attendance.user_id == user_id)
        if branch_id is not None:
            query = query.filter(Attendance.branch_id == branch_id)
        if status is not None:
            query = query.filter(Attendance.status == status)
        if start_date is not None:
            query = query.filter(Attendance.attendance_date >= start_date)
        if end_date is not None:
            query = query.filter(Attendance.attendance_date <= end_date)
        if search:
            token = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    User.name.ilike(token),
                    User.email.ilike(token),
                    User.first_name.ilike(token),
                    User.last_name.ilike(token),
                    User.username.ilike(token),
                )
            )

        total = query.count()
        items = (
            query.order_by(Attendance.attendance_date.desc(), Attendance.id.desc())
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )
        return items, total

    def list_for_export(
        self,
        *,
        business_id: int | None,
        user_id: int | None,
        branch_id: int | None,
        status: str | None,
        start_date: date | None,
        end_date: date | None,
        search: str | None,
    ) -> list[tuple[Attendance, User]]:
        query = self.db.query(Attendance, User).join(User, Attendance.user_id == User.id)

        if business_id is not None:
            query = query.filter(User.business_id == business_id)
        if user_id is not None:
            query = query.filter(Attendance.user_id == user_id)
        if branch_id is not None:
            query = query.filter(Attendance.branch_id == branch_id)
        if status is not None:
            query = query.filter(Attendance.status == status)
        if start_date is not None:
            query = query.filter(Attendance.attendance_date >= start_date)
        if end_date is not None:
            query = query.filter(Attendance.attendance_date <= end_date)
        if search:
            token = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    User.name.ilike(token),
                    User.email.ilike(token),
                    User.first_name.ilike(token),
                    User.last_name.ilike(token),
                    User.username.ilike(token),
                )
            )

        return query.order_by(Attendance.attendance_date.desc(), Attendance.id.desc()).all()
