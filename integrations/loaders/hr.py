"""Loads staged HR-system records into the HR & Workforce tables.

The operations models don't have source fields yet, so rows are matched on their
natural keys instead: units by name, staff by staff number, attendance by staff and
date. A re-run still updates rows rather than duplicating them.
"""
from operations.models import Employee, StaffAttendance, WorkforceUnit

from ..cleaning import CAMPUSES, CleaningError, clean_text, map_choice, parse_date
from .base import BaseLoad

CATEGORIES = {
    "teaching": ["teaching", "teachers", "teaching staff (full-time & contract)"],
    "non_teaching_support": ["non-teaching support", "support staff"],
    "drivers_technicians": ["drivers & mechanical technicians", "drivers", "transport"],
    "administrative": ["administrative & clerical", "administration", "admin"],
    "technical_security": ["technical, security & groundskeeping", "security", "grounds"],
}
UNIT_CAMPUSES = {
    **CAMPUSES,
    "multi_campus": ["multi-campus", "multi campus", "all campuses", "kibuli main & buwaate"],
}
EMPLOYMENT_TYPES = {
    "full_time": ["full time", "full-time", "ft", "permanent"],
    "contract": ["contract", "ct"],
    "part_time": ["part-time", "part time", "pt"],
}
EMPLOYMENT_STATUS = {True: ["active", "current"], False: ["inactive", "left", "exited"]}
ATTENDANCE = {
    "present": ["p", "present"],
    "absent": ["a", "absent"],
    "on_leave": ["l", "leave", "on leave"],
    "on_training": ["t", "training", "on training"],
    "on_field": ["f", "field", "field duty", "on field"],
}


class HRLoad(BaseLoad):
    record_order = ["unit", "employee", "attendance"]

    def units(self):
        existing = {u.name: u for u in WorkforceUnit.objects.all()}
        self.unit_by_name = dict(existing)
        to_create, to_update = [], []
        for record in self.unique(self.by_type["unit"]):
            p = record.payload
            try:
                name = clean_text(p.get("DeptName"))
                if not name:
                    raise CleaningError("department name is missing")
                category = map_choice(p.get("StaffCategory"), CATEGORIES, "staff category")
                campus = map_choice(p.get("Campus"), UNIT_CAMPUSES, "campus")
            except CleaningError as exc:
                self.reject(record, str(exc))
                continue
            location = clean_text(p.get("Location"))[:150]
            unit = existing.get(name)
            if unit is None:
                unit = WorkforceUnit(name=name, staff_category=category, campus=campus,
                                     location=location)
                to_create.append(unit)
                existing[name] = unit
            else:
                unit.staff_category, unit.campus, unit.location = category, campus, location
                to_update.append(unit)
            self.unit_by_name[name] = unit
            self.loaded(record)
        self.save(WorkforceUnit, to_create, to_update, ["staff_category", "campus", "location"])

    def employees(self):
        existing = {e.staff_number: e for e in Employee.objects.all()}
        self.employee_by_number = dict(existing)
        to_create, to_update = [], []
        fields = ["full_name", "unit", "job_title", "employment_type", "hire_date", "is_active"]
        for record in self.unique(self.by_type["employee"]):
            p = record.payload
            errors = []
            number = clean_text(p.get("StaffNo"))
            name = clean_text(p.get("FullName"))
            unit = self.unit_by_name.get(clean_text(p.get("Department")))
            if not number:
                errors.append("staff number is missing")
            if not name:
                errors.append("full name is missing")
            if unit is None:
                errors.append(f"department '{clean_text(p.get('Department'))}' is not known")
            try:
                employment = map_choice(p.get("EmploymentType"), EMPLOYMENT_TYPES,
                                        "employment type")
                hired = (parse_date(p["HireDate"], "hire date")
                         if clean_text(p.get("HireDate")) else None)
                active = map_choice(p.get("Status"), EMPLOYMENT_STATUS, "employment status")
            except CleaningError as exc:
                errors.append(str(exc))
            if errors:
                self.reject(record, *errors)
                continue
            values = {"full_name": name[:150], "unit": unit,
                      "job_title": clean_text(p.get("JobTitle"))[:100],
                      "employment_type": employment, "hire_date": hired, "is_active": active}
            employee = existing.get(number)
            if employee is None:
                employee = Employee(staff_number=number, **values)
                to_create.append(employee)
                existing[number] = employee
            else:
                for field, value in values.items():
                    setattr(employee, field, value)
                to_update.append(employee)
            self.employee_by_number[number] = employee
            self.loaded(record)
        self.save(Employee, to_create, to_update, fields)

    def attendance(self):
        employee_ids = [e.pk for e in self.employee_by_number.values()]
        existing = {(a.employee_id, a.date): a
                    for a in StaffAttendance.objects.filter(employee_id__in=employee_ids)}
        to_create, to_update = [], []
        seen = set()  # staff and day pairs already handled in this sync
        for record in self.unique(self.by_type["attendance"]):
            p = record.payload
            errors = []
            employee = self.employee_by_number.get(clean_text(p.get("StaffNo")))
            if employee is None:
                errors.append(f"staff member '{clean_text(p.get('StaffNo'))}' is not known")
            try:
                day = parse_date(p.get("Date"), "attendance date")
                status = map_choice(p.get("Status"), ATTENDANCE, "attendance code")
            except CleaningError as exc:
                errors.append(str(exc))
            if errors:
                self.reject(record, *errors)
                continue
            key = (employee.pk, day)
            if key in seen:
                self.reject(record, "this staff member already has attendance for that day")
                continue
            seen.add(key)
            row = existing.get(key)
            if row is None:
                to_create.append(StaffAttendance(employee=employee, date=day, status=status))
            else:
                row.status = status
                to_update.append(row)
            self.loaded(record)
        self.save(StaffAttendance, to_create, to_update, ["status"])


def load_hr(source, records):
    """Loader for the HR source; see integrations.pipeline for the contract."""
    load = HRLoad(source, records)
    load.units()
    load.employees()
    load.attendance()
    return load.created, load.updated
