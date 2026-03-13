from __future__ import annotations

import io
import calendar
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.models.salary import EmployeeSalary, EmployeeSalaryComponent, PayrollRecord, SalaryComponent, SalaryStructure
from app.models.user import User
from app.repository.company_repository import CompanyRepository
from app.repository.salary_repository import SalaryRepository
from app.repository.user_repository import UserRepository
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
        totals = self._summarize_assignment_components(assignment.components)

        existing_record = self.salary_repository.get_payroll_record(payload.employee_id, payload.year, payload.month)
        if existing_record is None:
            self.salary_repository.create_payroll_record(
                PayrollRecord(
                    employee_id=payload.employee_id,
                    salary_assignment_id=assignment.id,
                    year=payload.year,
                    month=payload.month,
                    gross_salary=totals["gross_salary"],
                    working_days=0,
                    present_days=0,
                    absent_days=0,
                    leave_days=0,
                    absent_deduction=Decimal("0.00"),
                    total_component_deduction=totals["total_deductions"],
                    pf_deduction=totals["deductions"].get("pf", Decimal("0.00")),
                    net_salary=totals["net_salary"],
                )
            )
        else:
            existing_record.salary_assignment_id = assignment.id
            existing_record.gross_salary = totals["gross_salary"]
            existing_record.total_component_deduction = totals["total_deductions"]
            existing_record.pf_deduction = totals["deductions"].get("pf", Decimal("0.00"))
            existing_record.net_salary = totals["net_salary"]
            existing_record.working_days = 0
            existing_record.present_days = 0
            existing_record.absent_days = 0
            existing_record.leave_days = 0
            existing_record.absent_deduction = Decimal("0.00")

        self.db.commit()
        return PayrollGenerateResponse(
            employee_id=payload.employee_id,
            year=payload.year,
            month=payload.month,
            earnings=totals["earnings"],
            deductions=totals["deductions"],
            gross_salary=totals["gross_salary"],
            total_deductions=totals["total_deductions"],
            net_salary=totals["net_salary"],
        )

    def list_payroll_records(self, actor: User, *, year: int | None = None, month: int | None = None) -> list[PayrollRecordResponse]:
        _ = actor
        return [self._to_payroll_record_response(item) for item in self.salary_repository.list_payroll_records(year=year, month=month)]

    def get_salary_slip(self, actor: User, employee_id: int, month: str) -> SalarySlipResponse:
        _ = actor
        parsed = self._parse_month_text(month)
        assignment = self._get_effective_assignment(employee_id, parsed.year, parsed.month)
        totals = self._summarize_assignment_components(assignment.components)
        if assignment.employee is None:
            raise NotFoundException("Employee not found")
        return SalarySlipResponse(
            employee=self._user_display_name(assignment.employee),
            month=parsed.strftime("%B %Y"),
            earnings=totals["earnings"],
            deductions=totals["deductions"],
            gross_salary=totals["gross_salary"],
            total_deductions=totals["total_deductions"],
            net_salary=totals["net_salary"],
        )

    def export_salary_slip_pdf(self, actor: User, employee_id: int, month: str) -> tuple[bytes, str]:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        slip = self.get_salary_slip(actor=actor, employee_id=employee_id, month=month)
        company = self.company_repository.get_single()
        output = io.BytesIO()
        doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=14 * mm)

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("SlipTitle", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=19, textColor=colors.HexColor("#0F172A"), spaceAfter=2)
        subtitle_style = ParagraphStyle("SlipSubTitle", parent=styles["Normal"], fontName="Helvetica", fontSize=10, textColor=colors.HexColor("#475569"), spaceAfter=8)
        section_style = ParagraphStyle("SectionTitle", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=11, textColor=colors.HexColor("#1E293B"), spaceAfter=4)

        story: list = []
        if company is not None and company.logo_url:
            logo_path = Path(company.logo_url)
            if logo_path.exists() and logo_path.is_file():
                logo = Image(str(logo_path))
                logo.drawHeight = 14 * mm
                logo.drawWidth = 40 * mm
                story.extend([logo, Spacer(1, 4)])

        story.append(Paragraph((company.company_name if company else "Company"), title_style))
        story.append(Paragraph("Salary Slip", subtitle_style))

        generated_on = datetime.now().strftime("%d-%b-%Y %I:%M %p")
        company_address = ", ".join([item for item in [company.address_line1 if company else None, company.address_line2 if company else None, company.city if company else None, company.state if company else None, company.country if company else None, company.pincode if company else None] if item])
        info_left = [["Employee Name", slip.employee], ["Employee ID", str(employee_id)], ["Pay Period", slip.month]]
        info_right = [["Generated On", generated_on], ["Company", company.company_name if company else "-"], ["Address", company_address or "-"], ["Gross Salary", self._fmt_money(slip.gross_salary)], ["Net Salary", self._fmt_money(slip.net_salary)]]
        info_table = Table([[Table(info_left, colWidths=[26 * mm, 58 * mm]), Table(info_right, colWidths=[26 * mm, 58 * mm])]], colWidths=[84 * mm, 84 * mm])
        info_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")), ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.extend([info_table, Spacer(1, 10), Paragraph("Earnings And Deductions", section_style)])

        earnings_items = [(k.replace("_", " ").title(), v) for k, v in slip.earnings.items()]
        deductions_items = [(k.replace("_", " ").title(), v) for k, v in slip.deductions.items()]
        row_count = max(len(earnings_items), len(deductions_items))
        rows = [["Earnings", "Amount", "Deductions", "Amount"]]
        for i in range(row_count):
            e_name, e_val = ("", "")
            d_name, d_val = ("", "")
            if i < len(earnings_items):
                e_name, amount = earnings_items[i]
                e_val = self._fmt_money(amount)
            if i < len(deductions_items):
                d_name, amount = deductions_items[i]
                d_val = self._fmt_money(amount)
            rows.append([e_name, e_val, d_name, d_val])
        rows.append(["Total Earnings", self._fmt_money(slip.gross_salary), "Total Deductions", self._fmt_money(slip.total_deductions)])

        table = Table(rows, colWidths=[62 * mm, 22 * mm, 62 * mm, 22 * mm], repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F172A")), ("FONTNAME", (0, 1), (-1, -2), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 9.5), ("ALIGN", (1, 1), (1, -1), "RIGHT"), ("ALIGN", (3, 1), (3, -1), "RIGHT"), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")), ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F1F5F9")), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")]))
        story.extend([table, Spacer(1, 10)])

        net = Table([["NET PAY", self._fmt_money(slip.net_salary)]], colWidths=[110 * mm, 58 * mm])
        net.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0F172A")), ("TEXTCOLOR", (0, 0), (-1, -1), colors.white), ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 12), ("ALIGN", (1, 0), (1, 0), "RIGHT"), ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
        story.append(net)

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
    def _user_display_name(user: User) -> str:
        if user.name and user.name.strip():
            return user.name.strip()
        full_name = " ".join(part for part in [user.first_name, user.middle_name, user.last_name] if part).strip()
        if full_name:
            return full_name
        return user.username
