"""Loads staged SMIS records into the academics tables.

Records are processed in dependency order (schools, terms, students, enrolments,
applications). Each one is cleaned; good records are created or updated, matched by
their SMIS ID so a re-run never duplicates rows; bad ones are rejected with reasons.
Writes are done in bulk, because the source sends thousands of rows at a time.
"""
from academics.models import Application, Enrolment, School, StudentProfile, Term

from ..cleaning import (
    CleaningError,
    clean_text,
    map_choice,
    normalise_campus,
    normalise_gender,
    normalise_nationality,
    parse_date,
    parse_term_number,
)
from .base import BaseLoad

STATUSES = {
    "active": ["active"],
    "withdrawn": ["withdrawn", "left"],
    "graduated": ["completed", "graduated"],
}
WITHDRAWAL_REASONS = {
    "financial": ["fees", "financial", "financial constraints", "school fees challenges"],
    "transfer": ["transfer", "transferred", "transfer to another school", "moved school"],
    "death": ["death", "deceased"],
    "academic_performance": ["academic performance", "poor performance"],
}
STAGES = {
    "applied": ["applied", "new application"],
    "qualified": ["qualified", "shortlisted"],
    "interviewed": ["interviewed", "interview done"],
    "accepted": ["accepted", "offer accepted"],
    "enrolled": ["enrolled", "joined"],
}
AT_RISK = {True: ["y", "yes", "1", "true"], False: ["n", "no", "0", "false"]}
LEVELS = {
    "nursery": ["nursery", "pre-primary", "preprimary", "kindergarten", "preschool"],
    "primary": ["primary", "pri"],
    "secondary": ["secondary", "sec", "o & a level", "o and a level"],
}


def _flag(value):
    """'Y', 'Yes', '1' → True; 'N', 'No', '0' or blank → False."""
    if not clean_text(value):
        return False
    return map_choice(value, AT_RISK, "at-risk flag")


def _whole_number(value, field):
    text = clean_text(value).replace(",", "")
    if not text.isdigit():
        raise CleaningError(f"{field} '{clean_text(value)}' is not a whole number")
    return int(text)


class SmisLoad(BaseLoad):
    record_order = ["school", "term", "student", "enrolment", "application"]

    # --- record types ---

    def schools(self):
        existing = {s.name: s for s in School.objects.all()}
        self.school_by_code = {}
        to_create, to_update = [], []
        for record in self.unique(self.by_type["school"]):
            p = record.payload
            try:
                name = clean_text(p.get("SchoolName"))
                if not name:
                    raise CleaningError("school name is missing")
                campus = normalise_campus(p.get("Campus"))
                capacity = _whole_number(p.get("Capacity"), "capacity")
                # an older export may not say; the school then stays without a level
                level = map_choice(p["Section"], LEVELS, "section") \
                    if clean_text(p.get("Section")) else ""
            except CleaningError as exc:
                self.reject(record, str(exc))
                continue
            school = existing.get(name)
            if school is None:  # the board's minimum is set later, in the admin
                school = School(name=name, campus=campus, capacity=capacity, level=level)
                to_create.append(school)
                existing[name] = school
            else:
                school.campus, school.capacity = campus, capacity
                if level:
                    school.level = level
                to_update.append(school)
            self.school_by_code[record.external_id] = school
            self.loaded(record)
        self.save(School, to_create, to_update, ["campus", "capacity", "level"])

    def terms(self):
        existing = {(t.academic_year, t.number): t for t in Term.objects.all()}
        self.term_by_code = {}
        to_create, to_update = [], []
        for record in self.unique(self.by_type["term"]):
            p = record.payload
            try:
                year = clean_text(p.get("AcademicYear"))
                if not year:
                    raise CleaningError("academic year is missing")
                number = parse_term_number(p.get("Term"))
                start = parse_date(p.get("StartDate"), "start date")
                end = parse_date(p.get("EndDate"), "end date")
                if start > end:
                    raise CleaningError("term starts after it ends")
            except CleaningError as exc:
                self.reject(record, str(exc))
                continue
            term = existing.get((year, number))
            if term is None:
                term = Term(academic_year=year, number=number, start_date=start, end_date=end)
                to_create.append(term)
                existing[(year, number)] = term
            else:
                term.start_date, term.end_date = start, end
                to_update.append(term)
            self.term_by_code[record.external_id] = term
            self.loaded(record)
        self.save(Term, to_create, to_update, ["start_date", "end_date"])

    def students(self):
        by_external = {
            s.external_id: s for s in StudentProfile.objects.filter(source_system=self.source)
        }
        by_number = {s.student_number: s for s in StudentProfile.objects.all()}
        self.student_by_admission = dict(by_external)
        to_create, to_update = [], []
        fields = ["student_number", "gender", "nationality", "date_of_birth",
                  "source_system", "external_id", "last_synced_at"]
        for record in self.unique(self.by_type["student"]):
            p = record.payload
            try:
                number = clean_text(p.get("AdmissionNo"))
                if not number:
                    raise CleaningError("admission number is missing")
                gender = normalise_gender(p.get("Sex"))
                nationality = normalise_nationality(p.get("Nationality"))
                dob = parse_date(p["DOB"], "date of birth") if clean_text(p.get("DOB")) else None
            except CleaningError as exc:
                self.reject(record, str(exc))
                continue
            student = by_external.get(record.external_id)
            if student is None:
                student = by_number.get(number)
                if student is not None and student.source_system_id not in (None, self.source.pk):
                    self.reject(record, f"student number {number} belongs to another source")
                    continue
            values = {"student_number": number, "gender": gender, "nationality": nationality,
                      "date_of_birth": dob, "external_id": record.external_id}
            if student is None:
                student = StudentProfile(**values)
                to_create.append(student)
            else:  # a known student, or one entered by hand that SMIS now takes over
                for field, value in values.items():
                    setattr(student, field, value)
                to_update.append(student)
            self.track(student)
            by_number[number] = student
            self.student_by_admission[record.external_id] = student
            self.loaded(record)
        self.save(StudentProfile, to_create, to_update, fields)

    def enrolments(self):
        student_ids = [s.pk for s in self.student_by_admission.values()]
        existing = list(Enrolment.objects.filter(student_id__in=student_ids))
        by_external = {e.external_id: e for e in existing if e.source_system_id == self.source.pk}
        by_place = {(e.student_id, e.term_id): e for e in existing}
        to_create, to_update = [], []
        fields = ["student", "school", "term", "class_level", "status", "withdrawal_date",
                  "withdrawal_reason", "at_risk", "source_system", "external_id",
                  "last_synced_at"]
        for record in self.unique(self.by_type["enrolment"]):
            p = record.payload
            errors = []
            student = self.student_by_admission.get(clean_text(p.get("AdmissionNo")))
            school = self.school_by_code.get(clean_text(p.get("SchoolCode")))
            term = self.term_by_code.get(clean_text(p.get("TermCode")))
            if student is None:
                errors.append(f"student '{clean_text(p.get('AdmissionNo'))}' is not known")
            if school is None:
                errors.append(f"school '{clean_text(p.get('SchoolCode'))}' is not known")
            if term is None:
                errors.append(f"term '{clean_text(p.get('TermCode'))}' is not known")
            try:
                status = map_choice(p.get("Status"), STATUSES, "status")
                reason, left_on = "", None
                if status == Enrolment.Status.WITHDRAWN:
                    reason = map_choice(p.get("WithdrawalReason"), WITHDRAWAL_REASONS,
                                        "withdrawal reason", default="other")
                    if clean_text(p.get("WithdrawalDate")):
                        left_on = parse_date(p["WithdrawalDate"], "withdrawal date")
                at_risk = _flag(p.get("AtRisk"))
            except CleaningError as exc:
                errors.append(str(exc))
            if errors:
                self.reject(record, *errors)
                continue
            if (student.pk, term.pk) in by_place and (
                by_place[(student.pk, term.pk)].external_id not in ("", record.external_id)
            ):
                self.reject(record, "this student already has an enrolment for that term")
                continue
            enrolment = by_external.get(record.external_id) or by_place.get((student.pk, term.pk))
            values = {"student": student, "school": school, "term": term,
                      "class_level": clean_text(p.get("Class"))[:30], "status": status,
                      "withdrawal_date": left_on, "withdrawal_reason": reason,
                      "at_risk": at_risk, "external_id": record.external_id}
            if enrolment is None:
                enrolment = Enrolment(**values)
                to_create.append(enrolment)
            else:
                for field, value in values.items():
                    setattr(enrolment, field, value)
                to_update.append(enrolment)
            self.track(enrolment)
            by_place[(student.pk, term.pk)] = enrolment
            self.loaded(record)
        self.save(Enrolment, to_create, to_update, fields)

    def applications(self):
        existing = list(Application.objects.all())
        by_external = {a.external_id: a for a in existing if a.source_system_id == self.source.pk}
        by_reference = {a.reference: a for a in existing}
        to_create, to_update = [], []
        fields = ["reference", "school", "term", "stage", "applied_on", "source_system",
                  "external_id", "last_synced_at"]
        for record in self.unique(self.by_type["application"]):
            p = record.payload
            errors = []
            reference = clean_text(p.get("ApplicationNo"))
            school = self.school_by_code.get(clean_text(p.get("SchoolCode")))
            term = self.term_by_code.get(clean_text(p.get("TermCode")))
            if not reference:
                errors.append("application number is missing")
            if school is None:
                errors.append(f"school '{clean_text(p.get('SchoolCode'))}' is not known")
            if term is None:
                errors.append(f"term '{clean_text(p.get('TermCode'))}' is not known")
            try:
                stage = map_choice(p.get("Stage"), STAGES, "stage")
                applied_on = parse_date(p.get("DateApplied"), "application date")
            except CleaningError as exc:
                errors.append(str(exc))
            if errors:
                self.reject(record, *errors)
                continue
            application = by_external.get(record.external_id) or by_reference.get(reference)
            values = {"reference": reference, "school": school, "term": term, "stage": stage,
                      "applied_on": applied_on, "external_id": record.external_id}
            if application is None:
                application = Application(**values)
                to_create.append(application)
            else:
                for field, value in values.items():
                    setattr(application, field, value)
                to_update.append(application)
            self.track(application)
            by_reference[reference] = application
            self.loaded(record)
        self.save(Application, to_create, to_update, fields)


def load_smis(source, records):
    """Loader for the SMIS source; see integrations.pipeline for the contract."""
    load = SmisLoad(source, records)
    load.schools()
    load.terms()
    load.students()
    load.enrolments()
    load.applications()
    return load.created, load.updated
