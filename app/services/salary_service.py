from __future__ import annotations

import io
from calendar import monthrange
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.models.salary import (
    EmployeeSalary,
    PayrollRecord,
    SalaryComponentBaseType,
    SalaryComponent,
    SalaryComponentType,
    SalaryStructure,
)
from app.models.user import User
from app.repository.salary_repository import SalaryRepository
from app.repository.user_repository import UserRepository
from app.schemas.salary import (
    EmployeeSalaryBreakdownItemResponse,
    EmployeeSalaryBreakdownResponse,
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
        items = self.salary_repository.list_salary_components()
        return [self._to_salary_component_response(item) for item in items]

    def update_salary_component(
        self,
        actor: User,
        component_id: int,
        payload: SalaryComponentUpdateRequest,
    ) -> SalaryComponentResponse:
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
            raise ConflictException("Cannot delete salary component because it is used in salary structures")

        try:
            self.salary_repository.delete_salary_component(component)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise BadRequestException("Unable to delete salary component") from exc

    def create_salary_structure(self, actor: User, payload: SalaryStructureCreateRequest) -> SalaryStructureResponse:
        _ = actor
        existing = self.salary_repository.get_salary_structure_by_name(payload.name.strip())
        if existing is not None:
            raise ConflictException("Salary structure already exists")

        component_ids = [item.component_id for item in payload.components]
        if len(component_ids) != len(set(component_ids)):
            raise ConflictException("Duplicate component_id in request")

        structure = SalaryStructure(name=payload.name.strip())
        self._replace_structure_components(structure=structure, component_payloads=payload.components)

        try:
            self.salary_repository.create_salary_structure(structure)
            self.db.commit()
            loaded = self.salary_repository.get_salary_structure_by_id(structure.id)
            if loaded is None:
                raise NotFoundException("Salary structure not found")
            return self._to_salary_structure_response(loaded)
        except IntegrityError as exc:
            self.db.rollback()
            self._raise_structure_integrity_conflict(exc, default_detail="Unable to save salary structure")
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise BadRequestException("Unable to save salary structure") from exc

    def list_salary_structures(self, actor: User) -> list[SalaryStructureResponse]:
        _ = actor
        items = self.salary_repository.list_salary_structures()
        return [self._to_salary_structure_response(item) for item in items]

    def get_salary_structure(self, actor: User, structure_id: int) -> SalaryStructureResponse:
        _ = actor
        structure = self.salary_repository.get_salary_structure_by_id(structure_id)
        if structure is None:
            raise NotFoundException("Salary structure not found")
        return self._to_salary_structure_response(structure)

    def update_salary_structure(
        self,
        actor: User,
        structure_id: int,
        payload: SalaryStructureUpdateRequest,
    ) -> SalaryStructureResponse:
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
            component_ids = [item.component_id for item in payload.components]
            if len(component_ids) != len(set(component_ids)):
                raise ConflictException("Duplicate component_id in request")
            self._replace_structure_components(structure=structure, component_payloads=payload.components)

        try:
            self.db.flush()
            self.db.commit()
            loaded = self.salary_repository.get_salary_structure_by_id(structure.id)
            if loaded is None:
                raise NotFoundException("Salary structure not found")
            return self._to_salary_structure_response(loaded)
        except IntegrityError as exc:
            self.db.rollback()
            self._raise_structure_integrity_conflict(exc, default_detail="Unable to update salary structure")
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise BadRequestException("Unable to update salary structure") from exc

    def create_employee_salary(self, actor: User, payload: EmployeeSalaryCreateRequest) -> EmployeeSalaryResponse:
        _ = actor
        employee = self.user_repository.get_by_id(payload.employee_id)
        if employee is None:
            raise NotFoundException("Employee not found")

        structure = self.salary_repository.get_salary_structure_by_id(payload.salary_structure_id)
        if structure is None:
            raise NotFoundException("Salary structure not found")
        if not structure.is_active:
            raise BadRequestException("Cannot assign inactive salary structure")

        employee_salary = EmployeeSalary(
            employee_id=payload.employee_id,
            salary_structure_id=payload.salary_structure_id,
            annual_ctc=payload.annual_ctc,
            effective_from=payload.effective_from,
        )
        try:
            self.salary_repository.create_employee_salary(employee_salary)
            self.db.commit()
            loaded = self.salary_repository.get_latest_employee_salary(payload.employee_id)
            if loaded is None:
                raise NotFoundException("Employee salary not found")
            return self._to_employee_salary_response(loaded)
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictException("Employee salary already exists for this effective date") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise BadRequestException("Unable to save employee salary") from exc

    def update_employee_salary(
        self,
        actor: User,
        salary_id: int,
        payload: EmployeeSalaryUpdateRequest,
    ) -> EmployeeSalaryResponse:
        _ = actor
        employee_salary = self.salary_repository.get_employee_salary_assignment_by_id(salary_id)
        if employee_salary is None:
            raise NotFoundException("Employee salary not found")

        if payload.salary_structure_id is not None:
            structure = self.salary_repository.get_salary_structure_by_id(payload.salary_structure_id)
            if structure is None:
                raise NotFoundException("Salary structure not found")
            if not structure.is_active:
                raise BadRequestException("Cannot assign inactive salary structure")
            employee_salary.salary_structure_id = payload.salary_structure_id

        if payload.annual_ctc is not None:
            employee_salary.annual_ctc = payload.annual_ctc

        if payload.effective_from is not None:
            employee_salary.effective_from = payload.effective_from

        try:
            self.db.flush()
            self.db.commit()
            self.db.refresh(employee_salary)
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
        items = self.salary_repository.list_employee_salaries()
        return [self._to_employee_salary_response(item) for item in items]

    def get_employee_salary(self, actor: User, employee_id: int) -> EmployeeSalaryResponse:
        _ = actor
        employee_salary = self.salary_repository.get_latest_employee_salary(employee_id)
        if employee_salary is None:
            raise NotFoundException("Employee salary not found")
        return self._to_employee_salary_response(employee_salary)

    def get_employee_salary_breakdown(self, actor: User, employee_id: int) -> EmployeeSalaryBreakdownResponse:
        _ = actor
        employee_salary = self.salary_repository.get_latest_employee_salary(employee_id)
        if employee_salary is None:
            raise NotFoundException("Employee salary not found")

        structure = self.salary_repository.get_salary_structure_by_id(employee_salary.salary_structure_id)
        if structure is None:
            raise NotFoundException("Salary structure not found")

        gross_salary = self._round_money(Decimal(employee_salary.annual_ctc) / Decimal("12"))
        component_amounts, _, _ = self._calculate_structure_components(structure=structure, gross_salary=gross_salary)
        components: list[EmployeeSalaryBreakdownItemResponse] = [
            EmployeeSalaryBreakdownItemResponse(name=name, amount=amount) for name, amount in component_amounts.items()
        ]

        return EmployeeSalaryBreakdownResponse(gross_salary=gross_salary, components=components)

    def generate_payroll(self, actor: User, payload: PayrollGenerateRequest) -> PayrollGenerateResponse:
        _ = actor
        parsed_month = datetime(payload.year, payload.month, 1)
        calculation = self._calculate_payroll(employee_id=payload.employee_id, parsed_month=parsed_month)

        existing_record = self.salary_repository.get_payroll_record(payload.employee_id, payload.year, payload.month)
        if existing_record is None:
            record = PayrollRecord(
                employee_id=payload.employee_id,
                salary_assignment_id=calculation["salary_assignment_id"],
                year=payload.year,
                month=payload.month,
                gross_salary=calculation["gross_salary"],
                working_days=calculation["working_days"],
                present_days=calculation["present_days"],
                absent_days=calculation["absent_days"],
                leave_days=calculation["leave_days"],
                absent_deduction=calculation["absent_deduction"],
                total_component_deduction=calculation["total_component_deduction"],
                pf_deduction=calculation["pf_deduction"],
                net_salary=calculation["net_salary"],
            )
            self.salary_repository.create_payroll_record(record)
        else:
            existing_record.salary_assignment_id = calculation["salary_assignment_id"]
            existing_record.gross_salary = calculation["gross_salary"]
            existing_record.working_days = calculation["working_days"]
            existing_record.present_days = calculation["present_days"]
            existing_record.absent_days = calculation["absent_days"]
            existing_record.leave_days = calculation["leave_days"]
            existing_record.absent_deduction = calculation["absent_deduction"]
            existing_record.total_component_deduction = calculation["total_component_deduction"]
            existing_record.pf_deduction = calculation["pf_deduction"]
            existing_record.net_salary = calculation["net_salary"]

        try:
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise BadRequestException("Unable to generate payroll") from exc

        return PayrollGenerateResponse(
            employee_id=payload.employee_id,
            year=payload.year,
            month=payload.month,
            gross_salary=calculation["gross_salary"],
            working_days=calculation["working_days"],
            present_days=calculation["present_days"],
            absent_days=calculation["absent_days"],
            leave_days=calculation["leave_days"],
            absent_deduction=calculation["absent_deduction"],
            component_deductions=calculation["component_deductions"],
            pf_deduction=calculation["pf_deduction"],
            net_salary=calculation["net_salary"],
        )

    def list_payroll_records(
        self,
        actor: User,
        *,
        year: int | None = None,
        month: int | None = None,
    ) -> list[PayrollRecordResponse]:
        _ = actor
        records = self.salary_repository.list_payroll_records(year=year, month=month)
        return [self._to_payroll_record_response(item) for item in records]

    def get_salary_slip(self, actor: User, employee_id: int, month: str) -> SalarySlipResponse:
        _ = actor
        parsed_month = self._parse_month_text(month)
        calculation = self._calculate_payroll(employee_id=employee_id, parsed_month=parsed_month)

        employee = calculation["employee"]
        display_name = self._user_display_name(employee)

        deductions = {
            "pf": calculation["pf_deduction"],
            "absent_deduction": calculation["absent_deduction"],
        }

        return SalarySlipResponse(
            employee=display_name,
            month=parsed_month.strftime("%B %Y"),
            earnings=calculation["earnings"],
            deductions=deductions,
            gross_salary=calculation["gross_salary"],
            net_salary=calculation["net_salary"],
        )

    def export_salary_slip_pdf(self, actor: User, employee_id: int, month: str) -> tuple[bytes, str]:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        slip = self.get_salary_slip(actor=actor, employee_id=employee_id, month=month)
        output = io.BytesIO()

        doc = SimpleDocTemplate(
            output,
            pagesize=A4,
            leftMargin=16 * mm,
            rightMargin=16 * mm,
            topMargin=14 * mm,
            bottomMargin=14 * mm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "SlipTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=19,
            textColor=colors.HexColor("#0F172A"),
            spaceAfter=2,
        )
        subtitle_style = ParagraphStyle(
            "SlipSubTitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            textColor=colors.HexColor("#475569"),
            spaceAfter=8,
        )
        section_style = ParagraphStyle(
            "SectionTitle",
            parent=styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=colors.HexColor("#1E293B"),
            spaceAfter=4,
        )

        story: list = []
        generated_on = datetime.now().strftime("%d-%b-%Y %I:%M %p")

        story.append(Paragraph("PAY SLIP", title_style))
        story.append(Paragraph("Payroll Statement", subtitle_style))

        info_left = [
            ["Employee Name", slip.employee],
            ["Employee ID", str(employee_id)],
            ["Pay Period", slip.month],
        ]
        info_right = [
            ["Generated On", generated_on],
            ["Gross Salary", self._fmt_money(slip.gross_salary)],
            ["Net Salary", self._fmt_money(slip.net_salary)],
        ]

        info_table = Table(
            [[
                Table(info_left, colWidths=[26 * mm, 58 * mm]),
                Table(info_right, colWidths=[26 * mm, 58 * mm]),
            ]],
            colWidths=[84 * mm, 84 * mm],
        )
        info_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(info_table)
        story.append(Spacer(1, 10))

        story.append(Paragraph("Earnings And Deductions", section_style))

        earnings_items = [(k.replace("_", " ").title(), v) for k, v in slip.earnings.items()]
        deductions_items = [(k.replace("_", " ").title(), v) for k, v in slip.deductions.items()]
        row_count = max(len(earnings_items), len(deductions_items))

        breakdown_rows = [["Earnings", "Amount", "Deductions", "Amount"]]
        for index in range(row_count):
            e_name, e_val = ("", "")
            d_name, d_val = ("", "")
            if index < len(earnings_items):
                e_name, amount = earnings_items[index]
                e_val = self._fmt_money(amount)
            if index < len(deductions_items):
                d_name, amount = deductions_items[index]
                d_val = self._fmt_money(amount)
            breakdown_rows.append([e_name, e_val, d_name, d_val])

        total_earnings = self._round_money(sum(slip.earnings.values(), Decimal("0.00")))
        total_deductions = self._round_money(sum(slip.deductions.values(), Decimal("0.00")))
        breakdown_rows.append(
            ["Total Earnings", self._fmt_money(total_earnings), "Total Deductions", self._fmt_money(total_deductions)]
        )

        breakdown_table = Table(
            breakdown_rows,
            colWidths=[62 * mm, 22 * mm, 62 * mm, 22 * mm],
            repeatRows=1,
        )
        breakdown_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                    ("FONTNAME", (0, 1), (-1, -2), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                    ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                    ("ALIGN", (3, 1), (3, -1), "RIGHT"),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F1F5F9")),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ]
            )
        )
        story.append(breakdown_table)
        story.append(Spacer(1, 10))

        net_block = Table(
            [["NET PAY", self._fmt_money(slip.net_salary)]],
            colWidths=[110 * mm, 58 * mm],
        )
        net_block.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0F172A")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 12),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(net_block)
        story.append(Spacer(1, 12))
        story.append(
            Paragraph(
                "This is a system-generated salary slip and does not require signature.",
                ParagraphStyle(
                    "FooterNote",
                    parent=styles["Normal"],
                    fontName="Helvetica-Oblique",
                    fontSize=8.5,
                    textColor=colors.HexColor("#64748B"),
                ),
            )
        )

        doc.build(story)
        filename = f"salary_slip_{employee_id}_{month}.pdf"
        return output.getvalue(), filename

    @staticmethod
    def _fmt_money(value: Decimal) -> str:
        rounded = SalaryService._round_money(value)
        return f"INR {rounded:,.2f}"

    def _calculate_payroll(self, employee_id: int, parsed_month: datetime) -> dict[str, object]:
        days_in_month = monthrange(parsed_month.year, parsed_month.month)[1]
        month_end = parsed_month.date().replace(day=days_in_month)

        employee = self.user_repository.get_by_id(employee_id)
        if employee is None:
            raise NotFoundException("Employee not found")

        employee_salary = self.salary_repository.get_effective_employee_salary(employee_id, month_end)
        if employee_salary is None:
            raise NotFoundException("No effective salary assignment found for this month")

        structure = self.salary_repository.get_salary_structure_by_id(employee_salary.salary_structure_id)
        if structure is None:
            raise NotFoundException("Salary structure not found")
        if not structure.components:
            raise BadRequestException("Salary structure has no components")

        gross_salary = self._round_money(Decimal(employee_salary.annual_ctc) / Decimal("12"))
        _, earnings, component_deductions = self._calculate_structure_components(
            structure=structure,
            gross_salary=gross_salary,
        )
        pf_deduction = self._round_money(component_deductions.get("pf", Decimal("0.00")))

        present_days, absent_days, leave_days = self.salary_repository.get_attendance_counts_for_month(
            employee_id=employee_id,
            year=parsed_month.year,
            month=parsed_month.month,
        )
        working_days = present_days + absent_days + leave_days
        if working_days <= 0:
            working_days = self._calendar_working_days(parsed_month.year, parsed_month.month)

        per_day_salary = Decimal("0.00")
        if working_days > 0:
            per_day_salary = self._round_money(gross_salary / Decimal(working_days))
        absent_deduction = self._round_money(per_day_salary * Decimal(absent_days))

        total_component_deduction = self._round_money(sum(component_deductions.values(), Decimal("0.00")))
        net_salary = self._round_money(gross_salary - pf_deduction - absent_deduction)

        return {
            "employee": employee,
            "salary_assignment_id": employee_salary.id,
            "gross_salary": gross_salary,
            "working_days": working_days,
            "present_days": present_days,
            "absent_days": absent_days,
            "leave_days": leave_days,
            "earnings": earnings,
            "component_deductions": component_deductions,
            "total_component_deduction": total_component_deduction,
            "pf_deduction": self._round_money(pf_deduction),
            "absent_deduction": absent_deduction,
            "net_salary": net_salary,
        }

    def _replace_structure_components(self, *, structure: SalaryStructure, component_payloads: list) -> None:
        from app.models.salary import SalaryStructureComponent

        total_percentage = Decimal("0.00")
        resolved_components: list[
            tuple[SalaryComponent, Decimal | None, Decimal | None, SalaryComponentBaseType | None, int | None]
        ] = []
        requested_component_ids = {int(item.component_id) for item in component_payloads}
        dependency_map: dict[int, int | None] = {}

        for item in component_payloads:
            if item.percentage is not None and item.fixed_amount is not None:
                raise BadRequestException("Provide only one of percentage or fixed_amount")
            if item.percentage is None and item.fixed_amount is None:
                raise BadRequestException("Either percentage or fixed_amount is required")

            component = self.salary_repository.get_salary_component_by_id(item.component_id)
            if component is None:
                raise NotFoundException(f"Salary component not found: {item.component_id}")
            if not component.is_active:
                raise BadRequestException(f"Salary component is inactive: {component.id}")
            percentage = Decimal(item.percentage) if item.percentage is not None else None
            fixed_amount = Decimal(item.fixed_amount) if item.fixed_amount is not None else None
            if percentage is not None:
                total_percentage += percentage
            base_type = item.base_type
            base_component_id = int(item.base_component_id) if item.base_component_id is not None else None

            if percentage is not None:
                if base_type is None:
                    raise BadRequestException("base_type is required when percentage is used")
                if base_type == SalaryComponentBaseType.GROSS and base_component_id is not None:
                    raise BadRequestException("base_component_id must be empty when base_type is GROSS")
                if base_type == SalaryComponentBaseType.COMPONENT:
                    if base_component_id is None:
                        raise BadRequestException("base_component_id is required when base_type is COMPONENT")
                    if base_component_id == component.id:
                        raise BadRequestException("Component cannot depend on itself")
                    if base_component_id not in requested_component_ids:
                        raise BadRequestException(
                            f"base_component_id {base_component_id} must be part of the same salary structure"
                        )
                dependency_map[component.id] = base_component_id if base_type == SalaryComponentBaseType.COMPONENT else None
            else:
                if base_type is not None or base_component_id is not None:
                    raise BadRequestException("base_type/base_component_id must be omitted when fixed_amount is used")
                dependency_map[component.id] = None

            resolved_components.append((component, percentage, fixed_amount, base_type, base_component_id))

        if total_percentage <= Decimal("0") and all(item[2] is None for item in resolved_components):
            raise BadRequestException("Total percentage must be greater than zero")
        self._validate_component_dependency_graph(dependency_map)

        # On update, flush deletions first so re-adding same component_ids
        # does not violate uq_salary_structure_components_structure_component.
        had_existing_components = bool(structure.id and structure.components)
        structure.components.clear()
        if had_existing_components:
            self.db.flush()
        for component, percentage, fixed_amount, base_type, base_component_id in resolved_components:
            structure.components.append(
                SalaryStructureComponent(
                    component_id=component.id,
                    percentage=percentage,
                    fixed_amount=fixed_amount,
                    base_type=base_type,
                    base_component_id=base_component_id,
                )
            )

    @staticmethod
    def _raise_structure_integrity_conflict(exc: IntegrityError, *, default_detail: str) -> None:
        message = str(getattr(exc, "orig", exc)).lower()
        if "uq_salary_structures_name" in message or "salary_structures.name" in message:
            raise ConflictException("Salary structure already exists") from exc
        if (
            "uq_salary_structure_components_structure_component" in message
            or "salary_structure_components" in message
        ):
            raise ConflictException("Duplicate component_id in request") from exc
        raise BadRequestException(default_detail) from exc

    @staticmethod
    def _calculate_component_amount(
        percentage: Decimal | None,
        fixed_amount: Decimal | None,
        gross_salary: Decimal,
        base_type: SalaryComponentBaseType | None,
        base_amount: Decimal | None,
    ) -> Decimal:
        if fixed_amount is not None:
            return SalaryService._round_money(Decimal(fixed_amount))
        if percentage is not None:
            base_salary = gross_salary
            if base_type == SalaryComponentBaseType.COMPONENT:
                if base_amount is None:
                    raise BadRequestException("Base component amount not found for COMPONENT-based calculation")
                base_salary = base_amount
            return SalaryService._round_money((base_salary * Decimal(percentage)) / Decimal("100"))
        raise BadRequestException("Salary structure component value is missing")

    def _calculate_structure_components(
        self,
        *,
        structure: SalaryStructure,
        gross_salary: Decimal,
    ) -> tuple[dict[str, Decimal], dict[str, Decimal], dict[str, Decimal]]:
        component_amounts: dict[str, Decimal] = {}
        amount_by_component_id: dict[int, Decimal] = {}
        earnings: dict[str, Decimal] = {}
        deductions: dict[str, Decimal] = {}

        component_map: dict[int, object] = {}
        for item in structure.components:
            if item.component is None:
                raise NotFoundException("Salary component not found")
            component_map[item.component_id] = item

        visiting: set[int] = set()

        def resolve(component_id: int) -> Decimal:
            if component_id in amount_by_component_id:
                return amount_by_component_id[component_id]
            if component_id in visiting:
                raise BadRequestException("Circular component dependency detected in salary structure")
            item = component_map.get(component_id)
            if item is None:
                raise BadRequestException(f"Dependent component not found in structure: {component_id}")
            visiting.add(component_id)

            base_amount: Decimal | None = None
            if item.base_type == SalaryComponentBaseType.COMPONENT:
                if item.base_component_id is None:
                    raise BadRequestException("base_component_id is required when base_type is COMPONENT")
                base_amount = resolve(int(item.base_component_id))

            amount = self._calculate_component_amount(
                percentage=item.percentage,
                fixed_amount=item.fixed_amount,
                gross_salary=gross_salary,
                base_type=item.base_type,
                base_amount=base_amount,
            )
            visiting.remove(component_id)
            amount_by_component_id[component_id] = amount

            key = self._normalize_key(item.component.name)
            component_amounts[key] = amount
            if item.component.type == SalaryComponentType.EARNING:
                earnings[key] = amount
            else:
                deductions[key] = amount
            return amount

        for item in structure.components:
            resolve(int(item.component_id))

        return component_amounts, earnings, deductions

    @staticmethod
    def _validate_component_dependency_graph(dependency_map: dict[int, int | None]) -> None:
        visiting: set[int] = set()
        visited: set[int] = set()

        def dfs(node: int) -> None:
            if node in visited:
                return
            if node in visiting:
                raise BadRequestException("Circular component dependency detected in salary structure")
            visiting.add(node)
            dependency = dependency_map.get(node)
            if dependency is not None:
                dfs(dependency)
            visiting.remove(node)
            visited.add(node)

        for node in dependency_map:
            dfs(node)

    @staticmethod
    def _to_salary_component_response(item: SalaryComponent) -> SalaryComponentResponse:
        return SalaryComponentResponse(
            id=item.id,
            name=item.name,
            type=item.type,
            is_active=item.is_active,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    def _to_salary_structure_response(self, item: SalaryStructure) -> SalaryStructureResponse:
        components = []
        for component_item in item.components:
            if component_item.component is None:
                raise NotFoundException("Salary component not found")
            components.append(
                {
                    "id": component_item.id,
                    "component_id": component_item.component_id,
                    "component_name": component_item.component.name,
                    "component_type": component_item.component.type,
                    "percentage": None if component_item.percentage is None else Decimal(component_item.percentage),
                    "fixed_amount": None
                    if component_item.fixed_amount is None
                    else Decimal(component_item.fixed_amount),
                    "base_type": component_item.base_type,
                    "base_component_id": component_item.base_component_id,
                }
            )
        return SalaryStructureResponse(
            id=item.id,
            name=item.name,
            is_active=item.is_active,
            components=components,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    def _to_employee_salary_response(self, item: EmployeeSalary) -> EmployeeSalaryResponse:
        if item.employee is None:
            raise NotFoundException("Employee not found")
        if item.salary_structure is None:
            raise NotFoundException("Salary structure not found")
        return EmployeeSalaryResponse(
            id=item.id,
            employee_id=item.employee_id,
            employee_name=self._user_display_name(item.employee),
            salary_structure_id=item.salary_structure_id,
            salary_structure_name=item.salary_structure.name,
            annual_ctc=Decimal(item.annual_ctc),
            effective_from=item.effective_from,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    def _to_payroll_record_response(self, item: PayrollRecord) -> PayrollRecordResponse:
        if item.employee is None:
            raise NotFoundException("Employee not found")
        return PayrollRecordResponse(
            id=item.id,
            employee_id=item.employee_id,
            employee_name=self._user_display_name(item.employee),
            year=item.year,
            month=item.month,
            gross_salary=Decimal(item.gross_salary),
            working_days=item.working_days,
            present_days=item.present_days,
            absent_days=item.absent_days,
            leave_days=item.leave_days,
            absent_deduction=Decimal(item.absent_deduction),
            total_component_deduction=Decimal(item.total_component_deduction),
            pf_deduction=Decimal(item.pf_deduction),
            net_salary=Decimal(item.net_salary),
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

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
    def _calendar_working_days(year: int, month: int) -> int:
        days = monthrange(year, month)[1]
        count = 0
        for day in range(1, days + 1):
            if datetime(year, month, day).weekday() < 5:
                count += 1
        return count

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
