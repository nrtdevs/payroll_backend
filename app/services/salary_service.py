from __future__ import annotations

import io
import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.models.attendance import AttendanceStatus
from app.models.salary import EmployeeSalary, EmployeeSalaryComponent, PayrollRecord, SalaryComponent, SalaryStructure
from app.models.user import User
from app.repository.attendance_repository import AttendanceRepository
from app.repository.company_repository import CompanyRepository
from app.repository.holiday_repository import HolidayRepository
from app.repository.leave_request_repository import LeaveRequestRepository
from app.repository.salary_repository import SalaryRepository
from app.repository.user_repository import UserRepository
from app.repository.weekend_policy_repository import WeekendPolicyRepository
from app.schemas.salary import (
    EmployeeSalaryBreakdownItemResponse,
    EmployeeSalaryBreakdownResponse,
    EmployeeSalaryComponentAmountRequest,
    EmployeeSalaryComponentAmountResponse,
    EmployeeSalaryCreateRequest,
    EmployeeSalaryResponse,
    EmployeeSalaryUpdateRequest,
    PayrollGenerateRequest,
    PayrollGenerateResponse,
    PayrollRecordResponse,
    SalaryComponentCreateRequest,
    SalaryComponentResponse,
    SalaryComponentUpdateRequest,
    SalarySlipResponse,
    SalaryStructureCreateRequest,
    SalaryStructureResponse,
    SalaryStructureUpdateRequest,
)

_TWO_DECIMAL = Decimal("0.01")


class SalaryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.salary_repository = SalaryRepository(db)
        self.user_repository = UserRepository(db)
        self.company_repository = CompanyRepository(db)
        self.attendance_repository = AttendanceRepository(db)
        self.holiday_repository = HolidayRepository(db)
        self.weekend_policy_repository = WeekendPolicyRepository(db)
        self.leave_request_repository = LeaveRequestRepository(db)

    def create_salary_component(self, actor: User, payload: SalaryComponentCreateRequest) -> SalaryComponentResponse:
        _ = actor
        existing = self.salary_repository.get_salary_component_by_name(payload.name.strip())
        if existing is not None:
            raise ConflictException("Salary component already exists")

        component = SalaryComponent(name=payload.name.strip(), type=payload.type)
        try:
            self.salary_repository.create_salary_component(component)
            self.db.commit()
            return self._to_salary_component_response(component)
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictException("Salary component already exists") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise BadRequestException("Unable to save salary component") from exc

    def list_salary_components(self, actor: User) -> list[SalaryComponentResponse]:
        _ = actor
        return [self._to_salary_component_response(item) for item in self.salary_repository.list_salary_components()]

    def update_salary_component(self, actor: User, component_id: int, payload: SalaryComponentUpdateRequest) -> SalaryComponentResponse:
        _ = actor
        component = self.salary_repository.get_salary_component_by_id(component_id)
        if component is None:
            raise NotFoundException("Salary component not found")

        if payload.name is not None:
            name = payload.name.strip()
            existing = self.salary_repository.get_salary_component_by_name(name)
            if existing is not None and existing.id != component.id:
                raise ConflictException("Salary component already exists")
            component.name = name
        if payload.type is not None:
            component.type = payload.type
        if payload.is_active is not None:
            component.is_active = payload.is_active

        try:
            self.db.flush()
            self.db.commit()
            self.db.refresh(component)
            return self._to_salary_component_response(component)
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictException("Salary component already exists") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise BadRequestException("Unable to update salary component") from exc

    def delete_salary_component(self, actor: User, component_id: int) -> None:
        _ = actor
        component = self.salary_repository.get_salary_component_by_id(component_id)
        if component is None:
            raise NotFoundException("Salary component not found")
        if self.salary_repository.is_component_used(component_id):
            raise ConflictException("Cannot delete salary component because it is used")
        self.salary_repository.delete_salary_component(component)
        self.db.commit()

    def create_salary_structure(self, actor: User, payload: SalaryStructureCreateRequest) -> SalaryStructureResponse:
        _ = actor
        existing = self.salary_repository.get_salary_structure_by_name(payload.name.strip())
        if existing is not None:
            raise ConflictException("Salary structure already exists")

        component_ids = self._normalize_component_ids(payload.components)
        structure = SalaryStructure(name=payload.name.strip())
        self._set_structure_components(structure=structure, component_ids=component_ids)

        try:
            self.salary_repository.create_salary_structure(structure)
            self.db.commit()
            loaded = self.salary_repository.get_salary_structure_by_id(structure.id)
            if loaded is None:
                raise NotFoundException("Salary structure not found")
            return self._to_salary_structure_response(loaded)
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictException("Salary structure already exists") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise BadRequestException("Unable to save salary structure") from exc

    def list_salary_structures(self, actor: User) -> list[SalaryStructureResponse]:
        _ = actor
        return [self._to_salary_structure_response(item) for item in self.salary_repository.list_salary_structures()]

    def get_salary_structure(self, actor: User, structure_id: int) -> SalaryStructureResponse:
        _ = actor
        structure = self.salary_repository.get_salary_structure_by_id(structure_id)
        if structure is None:
            raise NotFoundException("Salary structure not found")
        return self._to_salary_structure_response(structure)

    def update_salary_structure(self, actor: User, structure_id: int, payload: SalaryStructureUpdateRequest) -> SalaryStructureResponse:
        _ = actor
        structure = self.salary_repository.get_salary_structure_by_id(structure_id)
        if structure is None:
            raise NotFoundException("Salary structure not found")

        if payload.name is not None:
            name = payload.name.strip()
            if not name:
                raise BadRequestException("name cannot be empty")
            existing = self.salary_repository.get_salary_structure_by_name(name)
            if existing is not None and existing.id != structure.id:
                raise ConflictException("Salary structure already exists")
            structure.name = name
        if payload.is_active is not None:
            structure.is_active = payload.is_active
        if payload.components is not None:
            self._set_structure_components(structure=structure, component_ids=self._normalize_component_ids(payload.components))

        try:
            self.db.flush()
            self.db.commit()
            loaded = self.salary_repository.get_salary_structure_by_id(structure.id)
            if loaded is None:
                raise NotFoundException("Salary structure not found")
            return self._to_salary_structure_response(loaded)
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictException("Salary structure already exists") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise BadRequestException("Unable to update salary structure") from exc

    def create_employee_salary(self, actor: User, payload: EmployeeSalaryCreateRequest) -> EmployeeSalaryResponse:
        _ = actor
        employee = self.user_repository.get_by_id(payload.employee_id)
        if employee is None:
            raise NotFoundException("Employee not found")

        structure = None
        if payload.salary_structure_id is not None:
            structure = self.salary_repository.get_salary_structure_by_id(payload.salary_structure_id)
            if structure is None:
                raise NotFoundException("Salary structure not found")
            if not structure.is_active:
                raise BadRequestException("Cannot assign inactive salary structure")

        self._validate_component_amount_payload(payload.components, structure)

        employee_salary = EmployeeSalary(
            employee_id=payload.employee_id,
            salary_structure_id=payload.salary_structure_id,
            effective_from=payload.effective_from,
            annual_ctc=None,
        )
        try:
            self.salary_repository.create_employee_salary(employee_salary)
            self._replace_employee_salary_components(employee_salary=employee_salary, components=payload.components)
            totals = self._summarize_assignment_components(employee_salary.components)
            employee_salary.annual_ctc = self._round_money(totals["gross_salary"] * Decimal("12"))
            self.db.commit()
            loaded = self.salary_repository.get_employee_salary_assignment_by_id(employee_salary.id)
            if loaded is None:
                raise NotFoundException("Employee salary not found")
            return self._to_employee_salary_response(loaded)
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictException("Employee salary already exists for this effective date") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise BadRequestException("Unable to save employee salary") from exc

    def update_employee_salary(self, actor: User, salary_id: int, payload: EmployeeSalaryUpdateRequest) -> EmployeeSalaryResponse:
        _ = actor
        employee_salary = self.salary_repository.get_employee_salary_assignment_by_id(salary_id)
        if employee_salary is None:
            raise NotFoundException("Employee salary not found")

        structure = None
        if payload.salary_structure_id is not None:
            structure = self.salary_repository.get_salary_structure_by_id(payload.salary_structure_id)
            if structure is None:
                raise NotFoundException("Salary structure not found")
            if not structure.is_active:
                raise BadRequestException("Cannot assign inactive salary structure")
            employee_salary.salary_structure_id = payload.salary_structure_id
        elif employee_salary.salary_structure_id is not None:
            structure = self.salary_repository.get_salary_structure_by_id(employee_salary.salary_structure_id)

        if payload.effective_from is not None:
            employee_salary.effective_from = payload.effective_from

        if payload.components is not None:
            self._validate_component_amount_payload(payload.components, structure)
            self._replace_employee_salary_components(employee_salary=employee_salary, components=payload.components)

        totals = self._summarize_assignment_components(employee_salary.components)
        employee_salary.annual_ctc = self._round_money(totals["gross_salary"] * Decimal("12"))

        try:
            self.db.flush()
            self.db.commit()
            loaded = self.salary_repository.get_employee_salary_assignment_by_id(employee_salary.id)
            if loaded is None:
                raise NotFoundException("Employee salary not found")
            return self._to_employee_salary_response(loaded)
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictException("Employee salary already exists for this effective date") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise BadRequestException("Unable to update employee salary") from exc

    def list_employee_salaries(self, actor: User) -> list[EmployeeSalaryResponse]:
        _ = actor
        return [self._to_employee_salary_response(item) for item in self.salary_repository.list_employee_salaries()]

    def get_employee_salary(self, actor: User, employee_id: int) -> EmployeeSalaryResponse:
        _ = actor
        item = self.salary_repository.get_latest_employee_salary(employee_id)
        if item is None:
            raise NotFoundException("Employee salary not found")
        return self._to_employee_salary_response(item)

    def get_employee_salary_breakdown(self, actor: User, employee_id: int) -> EmployeeSalaryBreakdownResponse:
        _ = actor
        assignment = self.salary_repository.get_latest_employee_salary(employee_id)
        if assignment is None:
            raise NotFoundException("Employee salary not found")
        totals = self._summarize_assignment_components(assignment.components)
        components = [
            EmployeeSalaryBreakdownItemResponse(
                name=item.component.name if item.component else str(item.component_id),
                amount=self._round_money(item.amount),
            )
            for item in assignment.components
        ]
        return EmployeeSalaryBreakdownResponse(
            gross_salary=totals["gross_salary"],
            total_deductions=totals["total_deductions"],
            net_salary=totals["net_salary"],
            components=components,
        )

    def generate_payroll(self, actor: User, payload: PayrollGenerateRequest) -> PayrollGenerateResponse:
        _ = actor
        assignment = self._get_effective_assignment(payload.employee_id, payload.year, payload.month)
        if assignment.employee is None:
            raise NotFoundException("Employee not found")
        month_data = self._calculate_monthly_payroll_details(
            assignment=assignment,
            target_year=payload.year,
            target_month=payload.month,
        )

        existing_record = self.salary_repository.get_payroll_record(payload.employee_id, payload.year, payload.month)
        if existing_record is None:
            self.salary_repository.create_payroll_record(
                PayrollRecord(
                    employee_id=payload.employee_id,
                    salary_assignment_id=assignment.id,
                    year=payload.year,
                    month=payload.month,
                    gross_salary=month_data["gross_salary"],
                    working_days=month_data["working_days"],
                    present_days=month_data["present_days"],
                    absent_days=month_data["absent_days"],
                    leave_days=month_data["leave_days"],
                    absent_deduction=month_data["absent_deduction"],
                    total_component_deduction=month_data["total_deductions"],
                    pf_deduction=month_data["component_deductions"].get("pf", Decimal("0.00")),
                    net_salary=month_data["net_salary"],
                )
            )
        else:
            existing_record.salary_assignment_id = assignment.id
            existing_record.gross_salary = month_data["gross_salary"]
            existing_record.total_component_deduction = month_data["total_deductions"]
            existing_record.pf_deduction = month_data["component_deductions"].get("pf", Decimal("0.00"))
            existing_record.net_salary = month_data["net_salary"]
            existing_record.working_days = month_data["working_days"]
            existing_record.present_days = month_data["present_days"]
            existing_record.absent_days = month_data["absent_days"]
            existing_record.leave_days = month_data["leave_days"]
            existing_record.absent_deduction = month_data["absent_deduction"]

        self.db.commit()
        return PayrollGenerateResponse(
            employee=self._user_display_name(assignment.employee),
            employee_id=payload.employee_id,
            year=payload.year,
            month=payload.month,
            month_label=month_data["month_label"],
            total_days=month_data["total_days"],
            weekend_days=month_data["weekend_days"],
            holiday_days=month_data["holiday_days"],
            working_days=month_data["working_days"],
            present_days=month_data["present_days"],
            leave_days=month_data["leave_days"],
            absent_days=month_data["absent_days"],
            per_day_salary=month_data["per_day_salary"],
            absent_deduction=month_data["absent_deduction"],
            earnings=month_data["earnings"],
            deductions=month_data["deductions"],
            gross_salary=month_data["gross_salary"],
            total_deductions=month_data["total_deductions"],
            net_salary=month_data["net_salary"],
        )

    def list_payroll_records(self, actor: User, *, year: int | None = None, month: int | None = None) -> list[PayrollRecordResponse]:
        _ = actor
        return [self._to_payroll_record_response(item) for item in self.salary_repository.list_payroll_records(year=year, month=month)]

    def get_salary_slip(self, actor: User, employee_id: int, month: str) -> SalarySlipResponse:
        _ = actor
        parsed = self._parse_month_text(month)
        assignment = self._get_effective_assignment(employee_id, parsed.year, parsed.month)
        if assignment.employee is None:
            raise NotFoundException("Employee not found")
        month_data = self._calculate_monthly_payroll_details(
            assignment=assignment,
            target_year=parsed.year,
            target_month=parsed.month,
        )
        return SalarySlipResponse(
            employee=self._user_display_name(assignment.employee),
            month=parsed.strftime("%B %Y"),
            earnings=month_data["earnings"],
            deductions=month_data["deductions"],
            gross_salary=month_data["gross_salary"],
            total_deductions=month_data["total_deductions"],
            net_salary=month_data["net_salary"],
        )

    def export_salary_slip_pdf(self, actor: User, employee_id: int, month: str) -> tuple[bytes, str]:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        parsed = self._parse_month_text(month)
        assignment = self._get_effective_assignment(employee_id, parsed.year, parsed.month)
        if assignment.employee is None:
            raise NotFoundException("Employee not found")
        month_data = self._calculate_monthly_payroll_details(
            assignment=assignment,
            target_year=parsed.year,
            target_month=parsed.month,
        )
        slip = self.get_salary_slip(actor=actor, employee_id=employee_id, month=month)
        company = self.company_repository.get_single()
        output = io.BytesIO()
        doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=14 * mm)

        styles = getSampleStyleSheet()
        company_style = ParagraphStyle(
            "CompanyName",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=colors.black,
            spaceAfter=1,
        )
        title_style = ParagraphStyle(
            "SlipMonthTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            alignment=1,
            textColor=colors.black,
        )
        tiny_style = ParagraphStyle(
            "TinyNote",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            textColor=colors.black,
        )

        story: list = []

        if company is not None and company.logo_url:
            logo_path = Path(company.logo_url)
            if logo_path.exists() and logo_path.is_file():
                logo = Image(str(logo_path))
                logo.drawHeight = 18 * mm
                logo.drawWidth = 36 * mm
                story.append(logo)
        story.append(Paragraph((company.company_name if company else "Company").upper(), company_style))

        top_bar = Table([[""]], colWidths=[177 * mm], rowHeights=[1.8 * mm])
        top_bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#9E9E9E"))]))
        story.extend([top_bar, Spacer(1, 6)])

        month_heading = Table(
            [[Paragraph(f"Pay Slip for the Month of {slip.month}", title_style)]],
            colWidths=[177 * mm],
        )
        month_heading.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(month_heading)

        employee_name = self._user_display_name(assignment.employee)
        employee_designation = str(assignment.employee.designation_id or "-")
        doj = assignment.employee.created_at.strftime("%d-%b-%y") if assignment.employee.created_at else "-"
        total_ctc = self._fmt_money(self._round_money(slip.gross_salary * Decimal("12")))

        info_rows = [
            ["Employee Name:", employee_name, "Date of Joining", doj],
            ["Department:", "IT", "Designation", employee_designation],
            ["Month Days:", str(month_data["total_days"]), "Casual Leave:", "0"],
            ["Days Present:", str(month_data["present_days"]), "Sick Leave:", str(month_data["leave_days"])],
            ["W. Off:", str(month_data["weekend_days"]), "Holiday:", str(month_data["holiday_days"])],
            ["Absent:", str(month_data["absent_days"]), "Balance Leave:", "0"],
        ]
        info_table = Table(info_rows, colWidths=[39 * mm, 49 * mm, 35 * mm, 54 * mm])
        info_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.7, colors.black),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.2),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.append(info_table)

        earnings_items = [(k.replace("_", " ").title(), v) for k, v in slip.earnings.items()]
        deductions_items = [(k.replace("_", " ").title(), v) for k, v in slip.deductions.items()]
        row_count = max(len(earnings_items), len(deductions_items), 6)
        pay_rows = [["", "Actuals (Rs.)", "Computed (Rs.)", "Deductions", "Employee Share", "Employer Share"]]
        for i in range(row_count):
            if i < len(earnings_items):
                e_name, e_value = earnings_items[i]
                actual = str(self._round_money(e_value))
                computed = str(self._round_money(e_value))
            else:
                e_name, actual, computed = "", "", ""

            if i < len(deductions_items):
                d_name, d_value = deductions_items[i]
                emp_share = str(self._round_money(d_value))
                employer_share = "0"
            else:
                d_name, emp_share, employer_share = "", "", ""

            pay_rows.append([e_name, actual, computed, d_name, emp_share, employer_share])

        pay_rows.append(["Total Gross", str(self._round_money(slip.gross_salary)), str(self._round_money(slip.gross_salary)), "Total", str(self._round_money(slip.total_deductions)), "0"])
        pay_rows.append(["Total CTC per month", str(self._round_money(slip.gross_salary)), str(self._round_money(slip.gross_salary)), "Net Pay", str(self._round_money(slip.net_salary)), total_ctc])

        pay_table = Table(pay_rows, colWidths=[39 * mm, 25 * mm, 25 * mm, 35 * mm, 26 * mm, 27 * mm], repeatRows=1)
        pay_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.7, colors.black),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, -2), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ("ALIGN", (0, 0), (0, -1), "LEFT"),
                    ("ALIGN", (3, 0), (3, -1), "LEFT"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.append(pay_table)
        story.append(Spacer(1, 3))
        story.append(Paragraph("*This information is system generated, hence no signatures are required.", tiny_style))
        story.append(Spacer(1, 7))

        footer_bar = Table([["", "", ""]], colWidths=[59 * mm, 59 * mm, 59 * mm], rowHeights=[2.4 * mm])
        footer_bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#5f6368"))]))
        story.append(footer_bar)
        footer_contact = Table(
            [[company.phone or "-", company.email or "-", ", ".join([item for item in [company.address_line1 if company else None, company.city if company else None, company.state if company else None, company.pincode if company else None] if item]) or "-"]],
            colWidths=[59 * mm, 59 * mm, 59 * mm],
        )
        footer_contact.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(footer_contact)

        doc.build(story)
        return output.getvalue(), f"salary_slip_{employee_id}_{month}.pdf"

    def _validate_component_amount_payload(self, components: list[EmployeeSalaryComponentAmountRequest], structure: SalaryStructure | None) -> None:
        ids = [item.component_id for item in components]
        if len(ids) != len(set(ids)):
            raise ConflictException("Duplicate component_id in components")
        for item in components:
            self._ensure_component_exists_and_active(item.component_id)
        if structure is not None:
            allowed = {item.component_id for item in structure.components}
            invalid = [item.component_id for item in components if item.component_id not in allowed]
            if invalid:
                raise BadRequestException(f"Components not allowed by salary structure: {', '.join(str(i) for i in invalid)}")

    def _replace_employee_salary_components(self, *, employee_salary: EmployeeSalary, components: list[EmployeeSalaryComponentAmountRequest]) -> None:
        employee_salary.components.clear()
        if employee_salary.id:
            self.db.flush()
        for item in components:
            employee_salary.components.append(EmployeeSalaryComponent(component_id=item.component_id, amount=item.amount))

    def _set_structure_components(self, *, structure: SalaryStructure, component_ids: list[int]) -> None:
        from app.models.salary import SalaryStructureComponent

        structure.components.clear()
        if structure.id:
            self.db.flush()
        for component_id in component_ids:
            component = self._ensure_component_exists_and_active(component_id)
            structure.components.append(SalaryStructureComponent(component_id=component.id))

    def _summarize_assignment_components(self, components: list[EmployeeSalaryComponent]) -> dict[str, object]:
        earnings: dict[str, Decimal] = {}
        deductions: dict[str, Decimal] = {}
        component_cache: dict[int, SalaryComponent] = {}
        for item in components:
            component = item.component
            if component is None:
                component = component_cache.get(item.component_id)
                if component is None:
                    component = self._ensure_component_exists_and_active(item.component_id)
                    component_cache[item.component_id] = component

            key = self._normalize_key(component.name)
            amount = self._round_money(Decimal(item.amount))
            if component.type.value == "EARNING":
                earnings[key] = amount
            else:
                deductions[key] = amount

        gross_salary = self._round_money(sum(earnings.values(), Decimal("0.00")))
        total_deductions = self._round_money(sum(deductions.values(), Decimal("0.00")))
        net_salary = self._round_money(gross_salary - total_deductions)
        return {"earnings": earnings, "deductions": deductions, "gross_salary": gross_salary, "total_deductions": total_deductions, "net_salary": net_salary}

    def _get_effective_assignment(self, employee_id: int, year: int, month: int) -> EmployeeSalary:
        last_day = calendar.monthrange(year, month)[1]
        target_date = date(year, month, last_day)
        assignment = self.salary_repository.get_effective_employee_salary(employee_id, target_date)
        if assignment is None:
            raise NotFoundException("No effective salary assignment found for this month")
        return assignment

    def _ensure_component_exists_and_active(self, component_id: int) -> SalaryComponent:
        component = self.salary_repository.get_salary_component_by_id(component_id)
        if component is None:
            raise NotFoundException(f"Salary component not found: {component_id}")
        if not component.is_active:
            raise BadRequestException(f"Salary component is inactive: {component_id}")
        return component

    def _calculate_monthly_payroll_details(
        self,
        *,
        assignment: EmployeeSalary,
        target_year: int,
        target_month: int,
    ) -> dict[str, object]:
        if assignment.employee is None:
            raise NotFoundException("Employee not found")

        component_totals = self._summarize_assignment_components(assignment.components)
        month_start = date(target_year, target_month, 1)
        month_end = date(target_year, target_month, calendar.monthrange(target_year, target_month)[1])
        total_days = (month_end - month_start).days + 1
        all_dates = [month_start + timedelta(days=offset) for offset in range(total_days)]

        weekend_dates = {current_date for current_date in all_dates if self._is_weekend_for_employee(assignment.employee, current_date)}
        holiday_dates = {current_date for current_date in all_dates if self._is_holiday_for_employee(assignment.employee, current_date)}
        effective_holiday_dates = holiday_dates - weekend_dates
        working_dates = [current_date for current_date in all_dates if current_date not in weekend_dates and current_date not in effective_holiday_dates]
        working_date_set = set(working_dates)
        working_days = len(working_dates)

        attendance_rows = self.attendance_repository.list_by_user(
            assignment.employee_id,
            start_date=month_start,
            end_date=month_end,
        )
        present_dates = {
            row.attendance_date
            for row in attendance_rows
            if row.status == AttendanceStatus.PRESENT and row.attendance_date in working_date_set
        }
        present_days = len(present_dates)

        approved_leaves = self.leave_request_repository.list_approved_for_user_between(
            user_id=assignment.employee_id,
            start_date=month_start,
            end_date=month_end,
        )
        leave_dates = self._expand_leave_dates(approved_leaves, working_date_set)
        leave_days = len(leave_dates)
        absent_days = max(working_days - present_days - leave_days, 0)

        # Gross salary must always match sum of earning components in the salary structure assignment.
        monthly_gross = self._round_money(component_totals["gross_salary"])
        per_day_salary = self._round_money(monthly_gross / Decimal(working_days)) if working_days > 0 else Decimal("0.00")
        raw_absent_deduction = self._round_money(per_day_salary * Decimal(absent_days))

        deductions = dict(component_totals["deductions"])
        component_deductions = dict(component_totals["deductions"])

        # Prevent negative payroll: absent deduction cannot push net salary below zero.
        max_absent_deduction = self._round_money(
            max(monthly_gross - component_totals["total_deductions"], Decimal("0.00"))
        )
        absent_deduction = self._round_money(min(raw_absent_deduction, max_absent_deduction))
        deductions["absent_deduction"] = absent_deduction

        raw_total_deductions = self._round_money(component_totals["total_deductions"] + absent_deduction)
        total_deductions = self._round_money(min(raw_total_deductions, monthly_gross))
        net_salary = self._round_money(max(monthly_gross - total_deductions, Decimal("0.00")))

        return {
            "month_label": month_start.strftime("%B %Y"),
            "total_days": total_days,
            "weekend_days": len(weekend_dates),
            "holiday_days": len(effective_holiday_dates),
            "working_days": working_days,
            "present_days": present_days,
            "leave_days": leave_days,
            "absent_days": absent_days,
            "per_day_salary": per_day_salary,
            "absent_deduction": absent_deduction,
            "earnings": component_totals["earnings"],
            "component_deductions": component_deductions,
            "deductions": deductions,
            "gross_salary": monthly_gross,
            "total_deductions": total_deductions,
            "net_salary": net_salary,
        }

    def _resolve_monthly_gross(self, employee: User, assignment: EmployeeSalary, fallback_gross: Decimal) -> Decimal:
        if employee.salary_type and employee.salary_type.strip().upper() == "MONTHLY" and employee.salary is not None:
            monthly_salary = Decimal(employee.salary)
            if monthly_salary > Decimal("0"):
                return self._round_money(monthly_salary)

        if assignment.annual_ctc is not None:
            annual = Decimal(assignment.annual_ctc)
            if annual > Decimal("0"):
                return self._round_money(annual / Decimal("12"))

        return self._round_money(fallback_gross)

    def _expand_leave_dates(self, leave_requests: list, working_date_set: set[date]) -> set[date]:
        leave_dates: set[date] = set()
        for item in leave_requests:
            cursor = item.start_date
            while cursor <= item.end_date:
                if cursor in working_date_set:
                    leave_dates.add(cursor)
                cursor += timedelta(days=1)
        return leave_dates

    def _is_weekend_for_employee(self, employee: User, target_date: date) -> bool:
        session = self.weekend_policy_repository.get_active_session_for_date(
            branch_id=employee.branch_id,
            target_date=target_date,
        )
        if session is None:
            return False

        policy = self.weekend_policy_repository.get_active_policy_for_date(
            session_id=session.id,
            branch_id=employee.branch_id,
            target_date=target_date,
        )
        if policy is None:
            return False

        day_of_week = self._day_of_week(target_date)
        week_index = self._week_index(target_date)
        return any(
            rule.day_of_week == day_of_week and (rule.week_number is None or rule.week_number == week_index)
            for rule in policy.rules
        )

    def _is_holiday_for_employee(self, employee: User, target_date: date) -> bool:
        session = self.weekend_policy_repository.get_active_session_for_date(
            branch_id=employee.branch_id,
            target_date=target_date,
        )
        if session is None:
            return False

        holiday = self.holiday_repository.get_holiday_for_date(
            session_id=session.id,
            branch_id=employee.branch_id,
            target_date=target_date,
        )
        return holiday is not None

    @staticmethod
    def _normalize_component_ids(component_ids: list[int]) -> list[int]:
        if len(component_ids) != len(set(component_ids)):
            raise ConflictException("Duplicate component_id in request")
        return [int(item) for item in component_ids]

    @staticmethod
    def _to_salary_component_response(item: SalaryComponent) -> SalaryComponentResponse:
        return SalaryComponentResponse(id=item.id, name=item.name, type=item.type, is_active=item.is_active, created_at=item.created_at, updated_at=item.updated_at)

    def _to_salary_structure_response(self, item: SalaryStructure) -> SalaryStructureResponse:
        components = []
        for component_item in item.components:
            if component_item.component is None:
                raise NotFoundException("Salary component not found")
            components.append({"id": component_item.id, "component_id": component_item.component_id, "component_name": component_item.component.name, "component_type": component_item.component.type})
        return SalaryStructureResponse(id=item.id, name=item.name, is_active=item.is_active, components=components, created_at=item.created_at, updated_at=item.updated_at)

    def _to_employee_salary_response(self, item: EmployeeSalary) -> EmployeeSalaryResponse:
        if item.employee is None:
            raise NotFoundException("Employee not found")
        totals = self._summarize_assignment_components(item.components)
        components: list[EmployeeSalaryComponentAmountResponse] = []
        for component_item in item.components:
            if component_item.component is None:
                raise NotFoundException("Salary component not found")
            components.append(EmployeeSalaryComponentAmountResponse(component_id=component_item.component_id, component_name=component_item.component.name, component_type=component_item.component.type, amount=self._round_money(component_item.amount)))

        return EmployeeSalaryResponse(
            id=item.id,
            employee_id=item.employee_id,
            employee_name=self._user_display_name(item.employee),
            salary_structure_id=item.salary_structure_id,
            salary_structure_name=item.salary_structure.name if item.salary_structure is not None else None,
            effective_from=item.effective_from,
            components=components,
            gross_salary=totals["gross_salary"],
            total_deductions=totals["total_deductions"],
            net_salary=totals["net_salary"],
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    def _to_payroll_record_response(self, item: PayrollRecord) -> PayrollRecordResponse:
        if item.employee is None:
            raise NotFoundException("Employee not found")
        return PayrollRecordResponse(id=item.id, employee_id=item.employee_id, employee_name=self._user_display_name(item.employee), year=item.year, month=item.month, gross_salary=self._round_money(item.gross_salary), total_deductions=self._round_money(item.total_component_deduction), net_salary=self._round_money(item.net_salary), created_at=item.created_at, updated_at=item.updated_at)

    @staticmethod
    def _parse_month_text(value: str) -> datetime:
        try:
            return datetime.strptime(value, "%Y-%m")
        except ValueError as exc:
            raise BadRequestException("Invalid month format. Use YYYY-MM") from exc

    @staticmethod
    def _round_money(value: Decimal) -> Decimal:
        return Decimal(value).quantize(_TWO_DECIMAL, rounding=ROUND_HALF_UP)

    @staticmethod
    def _fmt_money(value: Decimal) -> str:
        rounded = SalaryService._round_money(value)
        return f"INR {rounded:,.2f}"

    @staticmethod
    def _normalize_key(name: str) -> str:
        return "_".join(name.strip().lower().split())

    @staticmethod
    def _day_of_week(target_date: date) -> int:
        return (target_date.weekday() + 1) % 7

    @staticmethod
    def _week_index(target_date: date) -> int:
        return ((target_date.day - 1) // 7) + 1

    @staticmethod
    def _user_display_name(user: User) -> str:
        if user.name and user.name.strip():
            return user.name.strip()
        full_name = " ".join(part for part in [user.first_name, user.middle_name, user.last_name] if part).strip()
        if full_name:
            return full_name
        return user.username
