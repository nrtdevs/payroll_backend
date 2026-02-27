from __future__ import annotations

import io
from datetime import date, datetime, timezone
from math import asin, cos, radians, sin, sqrt

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import ensure_same_business_or_master
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    TooManyRequestsException,
    UnauthorizedException,
)
from app.core.rate_limiter import InMemoryRateLimiter
from app.models.attendance import Attendance, AttendanceStatus
from app.models.role import RoleEnum
from app.models.user import User
from app.repository.attendance_repository import AttendanceRepository
from app.repository.branch_repository import BranchRepository
from app.repository.role_permission_repository import RolePermissionRepository
from app.repository.user_repository import UserRepository
from app.schemas.attendance import (
    AttendanceCheckInResponse,
    AttendanceListResponse,
    AttendanceResponse,
    AutoAbsenceResponse,
    FaceEnrollResponse,
)
from app.services.face_verification_service import FaceVerificationService


CHECK_IN_RATE_LIMITER = InMemoryRateLimiter(
    max_requests=settings.attendance_check_in_rate_limit,
    window_seconds=settings.attendance_check_in_rate_window_seconds,
)


class AttendanceService:
    LIST_ALL_ATTENDANCE_PERMISSION = "LIST_ALL_ATTENDANCE"
    LIST_BRANCH_ATTENDANCE_PERMISSION = "LIST_BRANCH_ATTENDANCE"
    LIST_OWN_ATTENDANCE_PERMISSION = "LIST_OWN_ATTENDANCE"
    EXPORT_ALL_ATTENDANCE_PERMISSION = "EXPORT_ALL_ATTENDANCE"
    EXPORT_BRANCH_ATTENDANCE_PERMISSION = "EXPORT_BRANCH_ATTENDANCE"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.attendance_repository = AttendanceRepository(db)
        self.user_repository = UserRepository(db)
        self.branch_repository = BranchRepository(db)
        self.role_permission_repository = RolePermissionRepository(db)
        self.face_verification_service = FaceVerificationService()

    def enroll_face(
        self,
        actor: User,
        *,
        image_base64: str | None = None,
        image_bytes: bytes | None = None,
        user_id: int | None = None,
    ) -> FaceEnrollResponse:
        target_user = self._resolve_target_user(actor, user_id)
        if not self._is_active_user(target_user):
            raise ForbiddenException("Inactive users cannot enroll face")
        encoding = self._extract_encoding(image_base64=image_base64, image_bytes=image_bytes)
        target_user.face_encoding = self.face_verification_service.serialize_encoding(encoding)
        try:
            self.db.flush()
            self.db.commit()
            return FaceEnrollResponse(message="Face enrollment successful")
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise BadRequestException("Unable to save face enrollment") from exc

    def check_in(
        self,
        actor: User,
        *,
        image_base64: str | None = None,
        image_bytes: bytes | None = None,
        latitude: float,
        longitude: float,
        ip_address: str | None = None,
        device_info: str | None = None,
        user_id: int | None = None,
    ) -> AttendanceCheckInResponse:
        target_user = self._resolve_target_user(actor, user_id)
        if not self._is_active_user(target_user):
            raise ForbiddenException("Inactive users are not allowed to check in")
        if not CHECK_IN_RATE_LIMITER.allow(f"attendance-check-in:{target_user.id}"):
            raise TooManyRequestsException("Too many check-in attempts, please retry later")
        if not target_user.face_encoding:
            raise BadRequestException("Face enrollment is required before check-in")

        now = datetime.now(timezone.utc)
        attendance_date = now.date()
        try:
            existing = self.attendance_repository.get_by_user_and_date(target_user.id, attendance_date)
        except SQLAlchemyError as exc:
            raise BadRequestException("Unable to read attendance data") from exc
        if existing is not None:
            raise ConflictException("Attendance already exists for this user on this date")

        live_encoding = self._extract_encoding(image_base64=image_base64, image_bytes=image_bytes)
        stored_encoding = self.face_verification_service.deserialize_encoding(target_user.face_encoding)
        distance, confidence = self.face_verification_service.compare_face_encodings(
            stored=stored_encoding,
            live=live_encoding,
        )
        if distance >= settings.attendance_face_distance_threshold:
            raise UnauthorizedException("Face mismatch")

        branch, geo_distance = self._validate_branch_geofence(
            target_user,
            latitude=latitude,
            longitude=longitude,
        )

        attendance = Attendance(
            user_id=target_user.id,
            branch_id=branch.id,
            attendance_date=attendance_date,
            check_in=now,
            latitude=latitude,
            longitude=longitude,
            ip_address=ip_address,
            device_info=device_info,
            face_confidence=confidence,
            check_in_latitude=latitude,
            check_in_longitude=longitude,
            check_in_ip=ip_address,
            location_distance_meters=geo_distance,
            face_match_score=confidence,
            status=AttendanceStatus.PRESENT,
        )
        try:
            self.attendance_repository.create(attendance)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictException("Attendance already exists for this user on this date") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise BadRequestException("Unable to save check-in attendance") from exc

        return AttendanceCheckInResponse(
            message="Check-in successful",
            confidence=round(confidence, 4),
            location_verified=True,
        )

    def check_out(self, actor: User, *, user_id: int | None = None) -> AttendanceResponse:
        target_user = self._resolve_target_user(actor, user_id)
        now = datetime.now(timezone.utc)
        attendance_date = now.date()
        try:
            attendance = self.attendance_repository.get_by_user_and_date(target_user.id, attendance_date)
        except SQLAlchemyError as exc:
            raise BadRequestException("Unable to read attendance data") from exc
        if attendance is None or attendance.check_in is None:
            raise BadRequestException("Check-in is required before check-out")
        if attendance.check_out is not None:
            raise ConflictException("Check-out already completed for this attendance date")
        check_in_time = self._to_utc_datetime(attendance.check_in)
        if now < check_in_time:
            raise BadRequestException("Invalid check-out time: earlier than check-in")

        total_minutes = int((now - check_in_time).total_seconds() // 60)
        attendance.check_in = check_in_time
        attendance.check_out = now
        attendance.total_minutes = total_minutes
        attendance.status = self._status_from_minutes(total_minutes)

        try:
            self.attendance_repository.update(attendance)
            self.db.commit()
            return AttendanceResponse.model_validate(attendance)
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictException("Invalid attendance state for check-out") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise BadRequestException("Unable to save check-out attendance") from exc

    def list_attendance(
        self,
        actor: User,
        *,
        user_id: int | None = None,
        branch_id: int | None = None,
        status: str | None = None,
        search: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        page: int = 1,
        size: int = 10,
    ) -> AttendanceListResponse:
        normalized_status = self._normalize_status(status)
        scoped_business_id, scoped_user_id, scoped_branch_id = self._resolve_list_scope(
            actor=actor,
            requested_user_id=user_id,
            requested_branch_id=branch_id,
        )
        try:
            items, total = self.attendance_repository.list_paginated(
                business_id=scoped_business_id,
                user_id=scoped_user_id,
                branch_id=scoped_branch_id,
                status=normalized_status,
                start_date=start_date,
                end_date=end_date,
                search=search,
                page=page,
                size=size,
            )
        except SQLAlchemyError as exc:
            raise BadRequestException("Unable to read attendance list") from exc
        total_pages = (total + size - 1) // size if total > 0 else 0
        return AttendanceListResponse(
            items=[AttendanceResponse.model_validate(item) for item in items],
            page=page,
            size=size,
            total=total,
            total_pages=total_pages,
        )

    def mark_auto_absence(
        self,
        actor: User,
        *,
        attendance_date: date,
        business_id: int | None = None,
    ) -> AutoAbsenceResponse:
        if attendance_date.weekday() >= 5:
            return AutoAbsenceResponse(attendance_date=attendance_date, created_count=0, skipped_existing_count=0)

        scoped_business_id = self._resolve_business_scope(actor, business_id)
        user_ids = self._list_employee_user_ids(scoped_business_id)
        if not user_ids:
            return AutoAbsenceResponse(attendance_date=attendance_date, created_count=0, skipped_existing_count=0)

        existing_user_ids = self.attendance_repository.list_existing_user_ids_for_date(user_ids, attendance_date)
        missing_user_ids = [item for item in user_ids if item not in existing_user_ids]

        if missing_user_ids:
            for target_user_id in missing_user_ids:
                user = self.user_repository.get_by_id(target_user_id)
                self.db.add(
                    Attendance(
                        user_id=target_user_id,
                        branch_id=user.branch_id if user else None,
                        attendance_date=attendance_date,
                        total_minutes=0,
                        status=AttendanceStatus.ABSENT,
                    )
                )
            try:
                self.db.commit()
            except IntegrityError as exc:
                self.db.rollback()
                raise ConflictException("Attendance already exists for one or more users on this date") from exc
            except SQLAlchemyError as exc:
                self.db.rollback()
                raise BadRequestException("Unable to mark auto absence") from exc

        return AutoAbsenceResponse(
            attendance_date=attendance_date,
            created_count=len(missing_user_ids),
            skipped_existing_count=len(existing_user_ids),
        )

    def export_attendance_excel(
        self,
        actor: User,
        *,
        user_id: int | None = None,
        branch_id: int | None = None,
        status: str | None = None,
        search: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> tuple[bytes, str]:
        from openpyxl import Workbook

        rows = self._list_export_rows(
            actor=actor,
            user_id=user_id,
            branch_id=branch_id,
            status=status,
            search=search,
            start_date=start_date,
            end_date=end_date,
        )

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Attendance"
        sheet.append(
            [
                "Attendance ID",
                "User ID",
                "Username",
                "Name",
                "Email",
                "Business ID",
                "Branch ID",
                "Attendance Date",
                "Check In",
                "Check Out",
                "Total Minutes",
                "Status",
                "IP Address",
                "Device Info",
                "Created At",
                "Updated At",
            ]
        )

        for attendance, target_user in rows:
            sheet.append(
                [
                    attendance.id,
                    attendance.user_id,
                    target_user.username,
                    self._display_name(target_user),
                    target_user.email,
                    target_user.business_id,
                    attendance.branch_id,
                    attendance.attendance_date.isoformat(),
                    self._fmt_datetime(attendance.check_in),
                    self._fmt_datetime(attendance.check_out),
                    attendance.total_minutes,
                    attendance.status.value,
                    attendance.ip_address,
                    attendance.device_info,
                    self._fmt_datetime(attendance.created_at),
                    self._fmt_datetime(attendance.updated_at),
                ]
            )

        output = io.BytesIO()
        workbook.save(output)
        filename = f"attendance_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.xlsx"
        return output.getvalue(), filename

    def export_attendance_pdf(
        self,
        actor: User,
        *,
        user_id: int | None = None,
        branch_id: int | None = None,
        status: str | None = None,
        search: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> tuple[bytes, str]:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import landscape, letter
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

        rows = self._list_export_rows(
            actor=actor,
            user_id=user_id,
            branch_id=branch_id,
            status=status,
            search=search,
            start_date=start_date,
            end_date=end_date,
        )

        table_data = [
            [
                "ID",
                "User",
                "Name",
                "Branch",
                "Date",
                "In",
                "Out",
                "Minutes",
                "Status",
            ]
        ]
        for attendance, target_user in rows:
            table_data.append(
                [
                    str(attendance.id),
                    str(attendance.user_id),
                    self._display_name(target_user),
                    "" if attendance.branch_id is None else str(attendance.branch_id),
                    attendance.attendance_date.isoformat(),
                    self._fmt_datetime(attendance.check_in),
                    self._fmt_datetime(attendance.check_out),
                    str(attendance.total_minutes),
                    attendance.status.value,
                ]
            )

        output = io.BytesIO()
        doc = SimpleDocTemplate(
            output,
            pagesize=landscape(letter),
            leftMargin=10 * mm,
            rightMargin=10 * mm,
            topMargin=8 * mm,
            bottomMargin=8 * mm,
        )
        table = Table(table_data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        doc.build([table])

        filename = f"attendance_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
        return output.getvalue(), filename

    def _validate_branch_geofence(self, target_user: User, *, latitude: float, longitude: float):
        if target_user.branch_id is None:
            raise BadRequestException("User is not assigned to a branch")
        branch = self.branch_repository.get_by_id(target_user.branch_id)
        if branch is None:
            raise NotFoundException("Assigned branch not found")
        if branch.latitude is None or branch.longitude is None:
            raise BadRequestException("Branch latitude/longitude is not configured")
        radius_meters = int(branch.radius_meters)
        distance = self._haversine_meters(
            float(latitude),
            float(longitude),
            float(branch.latitude),
            float(branch.longitude),
        )
        if distance > radius_meters:
            raise ForbiddenException(f"Outside allowed branch radius ({radius_meters} meters)")
        return branch, int(round(distance))

    def _resolve_target_user(self, actor: User, user_id: int | None) -> User:
        target_user_id = actor.id if user_id is None else user_id
        if target_user_id != actor.id and actor.role not in {
            RoleEnum.MASTER_ADMIN,
            RoleEnum.BUSINESS_OWNER,
            RoleEnum.BUSINESS_ADMIN,
        }:
            raise ForbiddenException("Not allowed to manage attendance for other users")

        user = self.user_repository.get_by_id(target_user_id)
        if user is None:
            raise NotFoundException("User not found")
        ensure_same_business_or_master(actor, user.business_id)
        return user

    def _resolve_business_scope(self, actor: User, business_id: int | None) -> int | None:
        if actor.role == RoleEnum.MASTER_ADMIN:
            return business_id
        if actor.business_id is None:
            raise ForbiddenException("User is not assigned to a business")
        if business_id is not None and business_id != actor.business_id:
            raise ForbiddenException("Cross-business access is forbidden")
        return actor.business_id

    def _list_employee_user_ids(self, business_id: int | None) -> list[int]:
        query = self.db.query(User.id).filter(User.role == RoleEnum.BUSINESS_EMPLOYEE)
        if business_id is not None:
            query = query.filter(User.business_id == business_id)
        rows = query.all()
        return [int(item[0]) for item in rows]

    def _resolve_list_scope(
        self,
        *,
        actor: User,
        requested_user_id: int | None,
        requested_branch_id: int | None,
    ) -> tuple[int | None, int | None, int | None]:
        has_all = self._has_permission(actor, self.LIST_ALL_ATTENDANCE_PERMISSION)
        has_branch = self._has_permission(actor, self.LIST_BRANCH_ATTENDANCE_PERMISSION)
        has_own = self._has_permission(actor, self.LIST_OWN_ATTENDANCE_PERMISSION)

        if not (has_all or has_branch or has_own):
            raise ForbiddenException("You do not have permission to list attendance")

        scoped_business_id = None if actor.role == RoleEnum.MASTER_ADMIN else actor.business_id
        if actor.role != RoleEnum.MASTER_ADMIN and actor.business_id is None:
            raise ForbiddenException("User is not assigned to a business")

        if has_all:
            if requested_user_id is not None:
                self._ensure_user_accessible(actor, requested_user_id)
            if requested_branch_id is not None:
                self._ensure_branch_accessible(actor, requested_branch_id)
            return scoped_business_id, requested_user_id, requested_branch_id

        if has_branch:
            if actor.branch_id is None:
                raise ForbiddenException("User is not assigned to a branch")
            if requested_branch_id is not None and requested_branch_id != actor.branch_id:
                raise ForbiddenException("Not allowed to list attendance outside your branch")
            if requested_user_id is not None:
                target_user = self.user_repository.get_by_id(requested_user_id)
                if target_user is None:
                    raise NotFoundException("User not found")
                ensure_same_business_or_master(actor, target_user.business_id)
                if target_user.branch_id != actor.branch_id:
                    raise ForbiddenException("Not allowed to list attendance outside your branch")
            return scoped_business_id, requested_user_id, actor.branch_id

        if requested_user_id is not None and requested_user_id != actor.id:
            raise ForbiddenException("Not allowed to list attendance for other users")
        if requested_branch_id is not None and requested_branch_id != actor.branch_id:
            raise ForbiddenException("Not allowed to list attendance outside your own scope")
        return scoped_business_id, actor.id, actor.branch_id

    def _resolve_export_scope(
        self,
        *,
        actor: User,
        requested_user_id: int | None,
        requested_branch_id: int | None,
    ) -> tuple[int | None, int | None, int | None]:
        has_all = self._has_permission(actor, self.EXPORT_ALL_ATTENDANCE_PERMISSION)
        has_branch = self._has_permission(actor, self.EXPORT_BRANCH_ATTENDANCE_PERMISSION)

        if not (has_all or has_branch):
            raise ForbiddenException("You do not have permission to export attendance")

        scoped_business_id = None if actor.role == RoleEnum.MASTER_ADMIN else actor.business_id
        if actor.role != RoleEnum.MASTER_ADMIN and actor.business_id is None:
            raise ForbiddenException("User is not assigned to a business")

        if has_all:
            if requested_user_id is not None:
                self._ensure_user_accessible(actor, requested_user_id)
            if requested_branch_id is not None:
                self._ensure_branch_accessible(actor, requested_branch_id)
            return scoped_business_id, requested_user_id, requested_branch_id

        if actor.branch_id is None:
            raise ForbiddenException("User is not assigned to a branch")
        if requested_branch_id is not None and requested_branch_id != actor.branch_id:
            raise ForbiddenException("Not allowed to export attendance outside your branch")
        if requested_user_id is not None:
            target_user = self.user_repository.get_by_id(requested_user_id)
            if target_user is None:
                raise NotFoundException("User not found")
            ensure_same_business_or_master(actor, target_user.business_id)
            if target_user.branch_id != actor.branch_id:
                raise ForbiddenException("Not allowed to export attendance outside your branch")
        return scoped_business_id, requested_user_id, actor.branch_id

    def _has_permission(self, actor: User, permission_name: str) -> bool:
        if actor.role_id is None:
            return False
        return self.role_permission_repository.has_permission_for_role(
            role_id=actor.role_id,
            permission_name=permission_name,
        )

    def _ensure_user_accessible(self, actor: User, user_id: int) -> None:
        target_user = self.user_repository.get_by_id(user_id)
        if target_user is None:
            raise NotFoundException("User not found")
        ensure_same_business_or_master(actor, target_user.business_id)

    def _ensure_branch_accessible(self, actor: User, branch_id: int) -> None:
        branch = self.branch_repository.get_by_id(branch_id)
        if branch is None:
            raise NotFoundException("Branch not found")
        ensure_same_business_or_master(actor, branch.business_id)

    def _list_export_rows(
        self,
        *,
        actor: User,
        user_id: int | None,
        branch_id: int | None,
        status: str | None,
        search: str | None,
        start_date: date | None,
        end_date: date | None,
    ) -> list[tuple[Attendance, User]]:
        normalized_status = self._normalize_status(status)
        scoped_business_id, scoped_user_id, scoped_branch_id = self._resolve_export_scope(
            actor=actor,
            requested_user_id=user_id,
            requested_branch_id=branch_id,
        )
        try:
            return self.attendance_repository.list_for_export(
                business_id=scoped_business_id,
                user_id=scoped_user_id,
                branch_id=scoped_branch_id,
                status=normalized_status,
                start_date=start_date,
                end_date=end_date,
                search=search,
            )
        except SQLAlchemyError as exc:
            raise BadRequestException("Unable to read attendance export data") from exc

    @staticmethod
    def _display_name(target_user: User) -> str:
        if target_user.name and target_user.name.strip():
            return target_user.name.strip()
        parts = [target_user.first_name, target_user.middle_name, target_user.last_name]
        return " ".join(part.strip() for part in parts if part and part.strip())

    @staticmethod
    def _fmt_datetime(value: datetime | None) -> str:
        if value is None:
            return ""
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    @staticmethod
    def _is_active_user(user: User) -> bool:
        return bool(user.status and user.status.strip().upper() == "ACTIVE")

    @staticmethod
    def _status_from_minutes(total_minutes: int) -> AttendanceStatus:
        if total_minutes >= 540:
            return AttendanceStatus.OVERTIME
        if total_minutes >= 480:
            return AttendanceStatus.PRESENT
        if 240 <= total_minutes < 480:
            return AttendanceStatus.HALF_DAY
        return AttendanceStatus.ABSENT

    @staticmethod
    def _to_utc_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        earth_radius_m = 6371000.0
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        return earth_radius_m * c

    def _extract_encoding(self, *, image_base64: str | None, image_bytes: bytes | None) -> list[float]:
        if image_bytes is not None:
            return self.face_verification_service.extract_face_encoding_from_bytes(image_bytes)
        if image_base64 is not None:
            return self.face_verification_service.extract_face_encoding(image_base64)
        raise BadRequestException("Image is required")

    @staticmethod
    def _normalize_status(status: str | None) -> str | None:
        if status is None:
            return None
        normalized = status.strip().upper()
        if not normalized:
            return None
        try:
            return AttendanceStatus(normalized).value
        except ValueError as exc:
            raise BadRequestException("Invalid status filter") from exc
