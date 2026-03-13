from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session, joinedload

from app.models.salary import (
    EmployeeSalary,
    EmployeeSalaryComponent,
    PayrollRecord,
    SalaryComponent,
    SalaryStructure,
)


class SalaryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_salary_component(self, component: SalaryComponent) -> SalaryComponent:
        self.db.add(component)
        self.db.flush()
        self.db.refresh(component)
        return component

    def get_salary_component_by_id(self, component_id: int) -> SalaryComponent | None:
        return self.db.query(SalaryComponent).filter(SalaryComponent.id == component_id).first()

    def get_salary_component_by_name(self, name: str) -> SalaryComponent | None:
        from sqlalchemy import func

        return self.db.query(SalaryComponent).filter(func.lower(SalaryComponent.name) == name.lower()).first()

    def list_salary_components(self) -> list[SalaryComponent]:
        return self.db.query(SalaryComponent).order_by(SalaryComponent.id.asc()).all()

    def delete_salary_component(self, component: SalaryComponent) -> None:
        self.db.delete(component)
        self.db.flush()

    def is_component_used(self, component_id: int) -> bool:
        return (
            self.db.query(EmployeeSalaryComponent.id)
            .filter(EmployeeSalaryComponent.component_id == component_id)
            .first()
            is not None
            or self.db.query(SalaryStructure.id).join(SalaryStructure.components).filter_by(component_id=component_id).first()
            is not None
        )

    def create_salary_structure(self, structure: SalaryStructure) -> SalaryStructure:
        self.db.add(structure)
        self.db.flush()
        self.db.refresh(structure)
        return structure

    def get_salary_structure_by_id(self, structure_id: int) -> SalaryStructure | None:
        from app.models.salary import SalaryStructureComponent

        return (
            self.db.query(SalaryStructure)
            .options(joinedload(SalaryStructure.components).joinedload(SalaryStructureComponent.component))
            .filter(SalaryStructure.id == structure_id)
            .first()
        )

    def get_salary_structure_by_name(self, name: str) -> SalaryStructure | None:
        from sqlalchemy import func

        return self.db.query(SalaryStructure).filter(func.lower(SalaryStructure.name) == name.lower()).first()

    def list_salary_structures(self) -> list[SalaryStructure]:
        from app.models.salary import SalaryStructureComponent

        return (
            self.db.query(SalaryStructure)
            .options(joinedload(SalaryStructure.components).joinedload(SalaryStructureComponent.component))
            .order_by(SalaryStructure.id.asc())
            .all()
        )

    def create_employee_salary(self, employee_salary: EmployeeSalary) -> EmployeeSalary:
        self.db.add(employee_salary)
        self.db.flush()
        self.db.refresh(employee_salary)
        return employee_salary

    def create_employee_salary_component(self, item: EmployeeSalaryComponent) -> EmployeeSalaryComponent:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def get_employee_salary_assignment_by_id(self, salary_id: int) -> EmployeeSalary | None:
        return (
            self.db.query(EmployeeSalary)
            .options(
                joinedload(EmployeeSalary.employee),
                joinedload(EmployeeSalary.salary_structure),
                joinedload(EmployeeSalary.components).joinedload(EmployeeSalaryComponent.component),
            )
            .filter(EmployeeSalary.id == salary_id)
            .first()
        )

    def list_employee_salaries(self) -> list[EmployeeSalary]:
        return (
            self.db.query(EmployeeSalary)
            .options(
                joinedload(EmployeeSalary.employee),
                joinedload(EmployeeSalary.salary_structure),
                joinedload(EmployeeSalary.components).joinedload(EmployeeSalaryComponent.component),
            )
            .order_by(EmployeeSalary.employee_id.asc(), EmployeeSalary.effective_from.desc(), EmployeeSalary.id.desc())
            .all()
        )

    def get_latest_employee_salary(self, employee_id: int) -> EmployeeSalary | None:
        return (
            self.db.query(EmployeeSalary)
            .options(
                joinedload(EmployeeSalary.employee),
                joinedload(EmployeeSalary.salary_structure),
                joinedload(EmployeeSalary.components).joinedload(EmployeeSalaryComponent.component),
            )
            .filter(EmployeeSalary.employee_id == employee_id)
            .order_by(EmployeeSalary.effective_from.desc(), EmployeeSalary.id.desc())
            .first()
        )

    def get_effective_employee_salary(self, employee_id: int, target_date: date) -> EmployeeSalary | None:
        return (
            self.db.query(EmployeeSalary)
            .options(
                joinedload(EmployeeSalary.employee),
                joinedload(EmployeeSalary.salary_structure),
                joinedload(EmployeeSalary.components).joinedload(EmployeeSalaryComponent.component),
            )
            .filter(
                EmployeeSalary.employee_id == employee_id,
                EmployeeSalary.effective_from <= target_date,
            )
            .order_by(EmployeeSalary.effective_from.desc(), EmployeeSalary.id.desc())
            .first()
        )

    def create_payroll_record(self, record: PayrollRecord) -> PayrollRecord:
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def get_payroll_record(self, employee_id: int, year: int, month: int) -> PayrollRecord | None:
        return (
            self.db.query(PayrollRecord)
            .options(joinedload(PayrollRecord.employee))
            .filter(
                PayrollRecord.employee_id == employee_id,
                PayrollRecord.year == year,
                PayrollRecord.month == month,
            )
            .first()
        )

    def list_payroll_records(self, *, year: int | None = None, month: int | None = None) -> list[PayrollRecord]:
        query = self.db.query(PayrollRecord).options(joinedload(PayrollRecord.employee))
        if year is not None:
            query = query.filter(PayrollRecord.year == year)
        if month is not None:
            query = query.filter(PayrollRecord.month == month)
        return query.order_by(PayrollRecord.year.desc(), PayrollRecord.month.desc(), PayrollRecord.id.desc()).all()
