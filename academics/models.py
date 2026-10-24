from django.contrib.auth import get_user_model
from django.db import models

from integrations.models import SourceTrackedModel, source_record_constraint

"""
The following are the models picked from
the data categories document.
prepared by me and they are intended to be used 
for api development by Caroline
further adjustments and modifications are due
eg transforming this into postgres as done 
by the technical lead
"""
User = get_user_model()
# This model is created by the student data based from the data category meant for student retention
class Student(models.Model):
	name = models.CharField(max_length = 255, default="")
	date_of_birth = models.CharField(max_length = 255, default="")
	gender = models.CharField(max_length = 255, default="")
	created_on = models.DateTimeField(auto_now_add = True, null = True)
	#photo
	nationality = models.CharField(max_length = 255, default="")
	lin= models.CharField(max_length = 255, default="")
	email = models.CharField(max_length = 255, default = "")
	address = models.CharField(max_length = 255, default="")
	phone = models.CharField(max_length = 255, default="")
	guardian_name = models.CharField(max_length = 255, default="")
	relation = models.CharField(max_length = 255, default="")
	guardian_contact = models.CharField(max_length = 255, default="")

#This model is meant for academic performance under the academic domain
class Academic(models.Model):
	name = models.ForeignKey(Student, on_delete = models.CASCADE)
	subjects = models.CharField(max_length = 255, default="")
	syllabus = models.CharField(max_length = 255, default="")
	created_on = models.DateTimeField(auto_now_add = True, null = True)
	outcome = models.CharField(max_length = 255, default="")

#This model is meant for student mapping under the academic domain.
class Section(models.Model):
	name = models.ForeignKey(Student, on_delete = models.CASCADE)
	grade_levels = models.CharField(max_length = 255, default="")
	streams = models.CharField(max_length = 255, default="")
	allocation = models.CharField(max_length = 255, default="")

#this particular model is meant for student grading under the academic domain.
class GradeResult(models.Model):
	name = models.ForeignKey(Student, on_delete = models.CASCADE)
	marks = models.CharField(max_length = 255, default="")
	rankings = models.CharField(max_length = 255, default="")
	transcript = models.CharField(max_length = 255, default="")
	report_cards = models.CharField(max_length = 255, default="")

#this shows the homework done under the academic domain
class Homework(models.Model):
	name = models.ForeignKey(Student, on_delete = models.CASCADE)
	task = models.CharField(max_length = 255, default="")
	grade = models.CharField(max_length = 255, default="")
	submission = models.CharField(max_length = 255, default="")

#this is meant for student attendance under the academic domain
class Attendance(models.Model):
	name = models.ForeignKey(Student, on_delete = models.CASCADE)
	student_attendance = models.CharField(max_length = 255, default="")
	grade = models.CharField(max_length = 255, default="")
	staff_attendance = models.CharField(max_length = 255, default="")
	period = models.CharField(max_length = 255, default="")

#this is meant for non cirricular activities under the academic domain
class Curricular(models.Model):
	name = models.CharField(max_length = 255, default="")
	club = models.CharField(max_length = 255, default="")
	society = models.CharField(max_length = 255, default="")

#This is meant to work with cocirricular activities under the academic domain
class Events(models.Model):
    name = models.ForeignKey(Curricular, on_delete = models.CASCADE)
    competition = models.CharField(max_length = 255, default="")
    achievement = models.CharField(max_length = 255, default="")
    total_female = models.IntegerField(default=0)
    total_male = models.IntegerField(default=0)
    period = models.CharField(max_length = 255, default="")

#this is for staff under the academic domain
class Staff(models.Model):
    name = models.CharField(max_length = 255, default="")
    contact = models.CharField(max_length = 255, default="")
    email = models.CharField(max_length = 255, default="")

#TO DO: create subject model


# --- Enrolment & retention ------------------------------------------------------
# Models behind the Student Enrollment and Student Retention screens. They sit
# alongside the older text-based models above, which are left untouched.

class School(models.Model):
    """A GreenHill school. Lives here until the shared organisation structure exists."""

    class Campus(models.TextChoices):
        KIBULI = "kibuli", "Kibuli Main"
        BUWAATE = "buwaate", "Buwaate"
        ANNEX = "annex", "Annex Preschool"

    class Level(models.TextChoices):
        NURSERY = "nursery", "Nursery"
        PRIMARY = "primary", "Primary"
        SECONDARY = "secondary", "Secondary"

    name = models.CharField(max_length=150, unique=True)
    campus = models.CharField(max_length=20, choices=Campus.choices)
    # the section filter on the academic screens; blank until the source says
    level = models.CharField(max_length=20, choices=Level.choices, blank=True)
    capacity = models.PositiveIntegerField(default=0)  # places available, for capacity utilisation
    # the board is alerted when enrolment falls below this
    minimum_enrolment = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Term(models.Model):
    """One school term, e.g. Term 1 of 2026."""

    academic_year = models.CharField(max_length=9)  # e.g. "2026" or "2025/2026"
    number = models.PositiveSmallIntegerField()  # 1, 2 or 3
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ["start_date"]
        constraints = [
            models.UniqueConstraint(fields=["academic_year", "number"], name="unique_term"),
        ]

    def __str__(self):
        return f"Term {self.number}, {self.academic_year}"


class StudentProfile(SourceTrackedModel):
    """A student, holding only what the enrolment and retention screens need."""

    class Gender(models.TextChoices):
        MALE = "male", "Boy"
        FEMALE = "female", "Girl"

    student_number = models.CharField(max_length=30, unique=True)
    gender = models.CharField(max_length=10, choices=Gender.choices)
    nationality = models.CharField(max_length=60)  # e.g. "Ugandan", "Kenyan"
    date_of_birth = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["student_number"]
        constraints = [source_record_constraint()]

    def __str__(self):
        return self.student_number


class Enrolment(SourceTrackedModel):
    """A student's place at a school for one term."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        WITHDRAWN = "withdrawn", "Withdrawn"
        GRADUATED = "graduated", "Graduated"  # finished school; not expected to return

    class WithdrawalReason(models.TextChoices):
        FINANCIAL = "financial", "Financial Constraints"
        TRANSFER = "transfer", "Transfer to Another School"
        DEATH = "death", "Death"
        ACADEMIC = "academic_performance", "Academic Performance"
        OTHER = "other", "Other"

    student = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="enrolments"
    )
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="enrolments")
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name="enrolments")
    class_level = models.CharField(max_length=30, blank=True)  # e.g. "P5", "S2"
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    withdrawal_date = models.DateField(null=True, blank=True)
    withdrawal_reason = models.CharField(
        max_length=30, choices=WithdrawalReason.choices, blank=True
    )
    # placeholder until the at-risk rule (fees, attendance, results) is agreed
    at_risk = models.BooleanField(default=False)

    class Meta:
        ordering = ["term", "student"]
        constraints = [
            models.UniqueConstraint(fields=["student", "term"], name="unique_enrolment_per_term"),
            source_record_constraint(),
            # a withdrawal always has a reason, and only withdrawals have one
            models.CheckConstraint(
                condition=(
                    models.Q(status="withdrawn") & ~models.Q(withdrawal_reason="")
                )
                | (~models.Q(status="withdrawn") & models.Q(withdrawal_reason="")),
                name="withdrawal_reason_only_when_withdrawn",
            ),
        ]

    def __str__(self):
        return f"{self.student} - {self.school} ({self.term})"


class Application(SourceTrackedModel):
    """An admissions application, recorded at the furthest stage it has reached."""

    class Stage(models.TextChoices):
        APPLIED = "applied", "Applied"
        QUALIFIED = "qualified", "Qualified"
        INTERVIEWED = "interviewed", "Interviewed"
        ACCEPTED = "accepted", "Accepted"
        ENROLLED = "enrolled", "Enrolled"  # took up the place

    # in funnel order; an application counts at its own stage and every stage before it
    STAGE_ORDER = [
        Stage.APPLIED, Stage.QUALIFIED, Stage.INTERVIEWED, Stage.ACCEPTED, Stage.ENROLLED,
    ]

    reference = models.CharField(max_length=30, unique=True)  # admissions reference number
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="applications")
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name="applications")
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.APPLIED)
    applied_on = models.DateField()

    class Meta:
        ordering = ["-applied_on"]
        constraints = [source_record_constraint()]

    def __str__(self):
        return f"{self.reference} ({self.get_stage_display()})"


# --- Academic performance ---------------------------------------------------------
# Models behind the Academic Performance screen: subjects, assessments (tests and
# end-of-term exams) with each student's mark, syllabus coverage, and national
# examination results (PLE, UCE, UACE).

# A mark of 50% or more counts as a pass at every level. Assumed until the heads of
# school confirm their own rule.
PASS_MARK = 50

# Grade bands per subject level, highest first: (lowest mark in the band, grade).
# Assumed school scales, to be confirmed in the discovery interviews.
GRADE_SCALES = {
    "primary": [(80, "D1"), (70, "D2"), (65, "C3"), (60, "C4"), (55, "C5"), (50, "C6"),
                (45, "P7"), (40, "P8"), (0, "F9")],
    "o_level": [(80, "A"), (70, "B"), (60, "C"), (50, "D"), (40, "E"), (0, "U")],
    "a_level": [(80, "A"), (70, "B"), (60, "C"), (50, "D"), (45, "E"), (35, "O"), (0, "F")],
}


def grade_for(level, mark):
    """The grade a mark (0-100) earns on a subject level's scale."""
    for lowest, grade in GRADE_SCALES[level]:
        if mark >= lowest:
            return grade
    return GRADE_SCALES[level][-1][1]


class Subject(models.Model):
    """A subject taught at one level, e.g. Mathematics at O Level."""

    class Level(models.TextChoices):
        PRIMARY = "primary", "Primary"
        O_LEVEL = "o_level", "O Level"  # S1-S4
        A_LEVEL = "a_level", "A Level"  # S5-S6

    class Category(models.TextChoices):
        SCIENCE = "science", "Science"
        ARTS = "arts", "Arts"

    code = models.CharField(max_length=20)  # the SMIS subject code, e.g. "MTC"
    name = models.CharField(max_length=100)
    level = models.CharField(max_length=10, choices=Level.choices)
    category = models.CharField(max_length=10, choices=Category.choices)

    class Meta:
        ordering = ["level", "name"]
        constraints = [
            models.UniqueConstraint(fields=["code", "level"], name="unique_subject_code_per_level"),
            models.UniqueConstraint(fields=["name", "level"], name="unique_subject_name_per_level"),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_level_display()})"


class Assessment(SourceTrackedModel):
    """One test or exam in one subject, sat by one class at one school in one term."""

    class Kind(models.TextChoices):
        TEST_1 = "test_1", "Test 1"
        TEST_2 = "test_2", "Test 2"
        END_OF_TERM = "end_of_term", "End of term"

    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="assessments")
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name="assessments")
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="assessments")
    class_level = models.CharField(max_length=30)  # e.g. "P7", "S3"
    kind = models.CharField(max_length=20, choices=Kind.choices)
    held_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["term", "school", "class_level", "subject", "kind"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "term", "class_level", "subject", "kind"],
                name="unique_assessment",
            ),
            source_record_constraint(),
        ]

    def __str__(self):
        return f"{self.subject.name} {self.get_kind_display()}, {self.class_level} ({self.term})"


class AssessmentResult(SourceTrackedModel):
    """One student's mark in one assessment, as a percentage, with the grade it earned."""

    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="results")
    student = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="assessment_results"
    )
    mark = models.DecimalField(max_digits=4, decimal_places=1)  # 0.0 to 100.0
    grade = models.CharField(max_length=3)  # on the subject level's scale, e.g. "B" or "D2"

    class Meta:
        ordering = ["assessment", "student"]
        constraints = [
            models.UniqueConstraint(fields=["assessment", "student"], name="unique_result"),
            models.CheckConstraint(
                condition=models.Q(mark__gte=0, mark__lte=100), name="result_mark_0_to_100"
            ),
            source_record_constraint(),
        ]

    @property
    def passed(self):
        return self.mark >= PASS_MARK

    def __str__(self):
        return f"{self.student} - {self.assessment}: {self.mark}% ({self.grade})"


class SyllabusCoverage(SourceTrackedModel):
    """How much of a subject's syllabus a class has covered so far in a term."""

    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="syllabus")
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name="syllabus")
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="syllabus")
    class_level = models.CharField(max_length=30)
    topics_planned = models.PositiveSmallIntegerField()  # topics scheduled for the term
    topics_covered = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["term", "school", "class_level", "subject"]
        verbose_name_plural = "syllabus coverage"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "term", "class_level", "subject"],
                name="unique_syllabus_coverage",
            ),
            models.CheckConstraint(
                condition=models.Q(topics_covered__lte=models.F("topics_planned")),
                name="covered_within_planned",
            ),
            source_record_constraint(),
        ]

    def __str__(self):
        return f"{self.subject.name}, {self.class_level}: " \
            f"{self.topics_covered}/{self.topics_planned}"


class NationalExamResult(SourceTrackedModel):
    """A candidate's overall result in a national examination: PLE at the end of P7, UCE
    at the end of S4, UACE at the end of S6."""

    class Exam(models.TextChoices):
        PLE = "ple", "PLE"
        UCE = "uce", "UCE"
        UACE = "uace", "UACE"

    class Division(models.TextChoices):
        DIVISION_1 = "division_1", "Division 1"
        DIVISION_2 = "division_2", "Division 2"
        DIVISION_3 = "division_3", "Division 3"
        DIVISION_4 = "division_4", "Division 4"
        UNGRADED = "ungraded", "Ungraded (U)"

    student = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="national_exam_results"
    )
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="national_exams")
    exam = models.CharField(max_length=10, choices=Exam.choices)
    year = models.PositiveSmallIntegerField()  # the year the exam was sat
    # PLE and UCE: the division; blank for UACE
    division = models.CharField(max_length=20, choices=Division.choices, blank=True)
    aggregate = models.PositiveSmallIntegerField(null=True, blank=True)  # PLE only, 4 to 36
    principal_passes = models.PositiveSmallIntegerField(null=True, blank=True)  # UACE only
    # Worked out when the result is loaded. PLE and UCE: Division 1 to 4. UACE: at least
    # two principal passes. Assumed rules, to be confirmed in the discovery interviews.
    passed = models.BooleanField()

    class Meta:
        ordering = ["-year", "exam", "student"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "exam", "year"], name="unique_national_exam_result"
            ),
            models.CheckConstraint(
                condition=models.Q(aggregate__isnull=True)
                | models.Q(aggregate__gte=4, aggregate__lte=36),
                name="ple_aggregate_4_to_36",
            ),
            source_record_constraint(),
        ]

    def __str__(self):
        return f"{self.student} - {self.get_exam_display()} {self.year}"
