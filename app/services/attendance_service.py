from __future__ import annotations

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
    def __init__(self, db: Session) -> None:
        self.db = db
        self.attendance_repository = AttendanceRepository(db)
        self.user_repository = UserRepository(db)
        self.branch_repository = BranchRepository(db)
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
        try:
            items, total = self.attendance_repository.list_paginated(
                business_id=None,
                user_id=user_id,
                branch_id=branch_id,
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
