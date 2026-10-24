
import re

from django.db.models import Avg, Count, Exists, OuterRef, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    GRADE_SCALES,
    PASS_MARK,
    Academic,
    Application,
    Assessment,
    AssessmentResult,
    Attendance,
    Curricular,
    Enrolment,
    Events,
    GradeResult,
    Homework,
    NationalExamResult,
    School,
    Section,
    Staff,
    Student,
    StudentProfile,
    Subject,
    SyllabusCoverage,
    Term,
    grade_for,
)
from .serializers import (
    AcademicDashboardQuerySerializer,
    AcademicSerializer,
    ApplicationSerializer,
    AssessmentResultSerializer,
    AssessmentSerializer,
    AttendanceSerializer,
    CurricularSerializer,
    EnrollmentDashboardSerializer,
    EnrolmentSerializer,
    EventsSerializer,
    GradeResultSerializer,
    HomeworkSerializer,
    NationalExamResultSerializer,
    PerformanceDashboardQuerySerializer,
    PerformanceDashboardSerializer,
    RetentionDashboardSerializer,
    SchoolSerializer,
    SectionSerializer,
    StaffSerializer,
    StudentProfileSerializer,
    StudentSerializer,
    SubjectSerializer,
    SyllabusCoverageSerializer,
    TermSerializer,
)


# Create your views here.
@extend_schema(tags=["Academics - Students"])
class StudentViewSet(viewsets.ModelViewSet):
    serializer_class = StudentSerializer
    queryset = Student.objects.all()


@extend_schema(tags=["Academics - Performance"])
class AcademicViewSet(viewsets.ModelViewSet):
    serializer_class = AcademicSerializer
    queryset = Academic.objects.all()


@extend_schema(tags=["Academics - Students"])
class SectionViewSet(viewsets.ModelViewSet):
    serializer_class = SectionSerializer
    queryset = Section.objects.all()


@extend_schema(tags=["Academics - Performance"])
class GradeResultViewSet(viewsets.ModelViewSet):
    serializer_class = GradeResultSerializer
    queryset = GradeResult.objects.all()


@extend_schema(tags=["Academics - Performance"])
class HomeworkViewSet(viewsets.ModelViewSet):
    serializer_class = HomeworkSerializer
    queryset = Homework.objects.all()


@extend_schema(tags=["Academics - Students"])
class AttendanceViewSet(viewsets.ModelViewSet):
    serializer_class = AttendanceSerializer
    queryset = Attendance.objects.all()


@extend_schema(tags=["Academics - Co-Curricular"])
class CurricularViewSet(viewsets.ModelViewSet):
    serializer_class = CurricularSerializer
    queryset = Curricular.objects.all()


@extend_schema(tags=["Academics - Co-Curricular"])
class EventsViewSet(viewsets.ModelViewSet):
    serializer_class = EventsSerializer
    queryset = Events.objects.all()


@extend_schema(tags=["Academics - Staff"])
class StaffViewSet(viewsets.ModelViewSet):
    serializer_class = StaffSerializer
    queryset = Staff.objects.all()


# --- Enrolment & retention ------------------------------------------------------

STUDENTS_TAG = "Academics - Students"


def _rate(part, whole):
    """Percentage rounded to one decimal place, or None when there is nothing to measure."""
    return round(part * 100 / whole, 1) if whole else None


def _term_summary(term):
    return {"id": term.pk, "label": str(term)} if term else None


def _resolve_term(term_id):
    """The requested term, or the latest term that has started (else the latest term)."""
    if term_id:
        return get_object_or_404(Term, pk=term_id)
    started = Term.objects.filter(
        start_date__lte=timezone.localdate()
    ).order_by("-start_date")
    return started.first() or Term.objects.order_by("-start_date").first()


def _scope(queryset, params, prefix=""):
    """Filter a queryset by the campus, level and school query parameters."""
    if params.get("campus"):
        queryset = queryset.filter(**{f"{prefix}campus": params["campus"]})
    if params.get("level"):
        queryset = queryset.filter(**{f"{prefix}level": params["level"]})
    if params.get("school"):
        field = "pk" if not prefix else "id"
        queryset = queryset.filter(**{f"{prefix}{field}": params["school"]})
    return queryset


@extend_schema(tags=[STUDENTS_TAG])
class SchoolViewSet(viewsets.ModelViewSet):
    serializer_class = SchoolSerializer
    queryset = School.objects.all()

    def get_queryset(self):
        return _scope(super().get_queryset(), self.request.query_params)


@extend_schema(tags=[STUDENTS_TAG])
class TermViewSet(viewsets.ModelViewSet):
    serializer_class = TermSerializer
    queryset = Term.objects.all()


@extend_schema(tags=[STUDENTS_TAG])
class StudentProfileViewSet(viewsets.ModelViewSet):
    serializer_class = StudentProfileSerializer
    queryset = StudentProfile.objects.all()

    def get_queryset(self):
        queryset = super().get_queryset()
        for field in ("gender", "nationality"):
            if self.request.query_params.get(field):
                queryset = queryset.filter(
                    **{field: self.request.query_params[field]}
                )
        return queryset


@extend_schema(tags=[STUDENTS_TAG])
class EnrolmentViewSet(viewsets.ModelViewSet):
    serializer_class = EnrolmentSerializer
    queryset = Enrolment.objects.select_related("school", "student", "term")

    def get_queryset(self):
        params = self.request.query_params
        queryset = _scope(super().get_queryset(), params, prefix="school__")
        for field in ("term", "status"):
            if params.get(field):
                queryset = queryset.filter(**{field: params[field]})
        return queryset


@extend_schema(tags=[STUDENTS_TAG])
class ApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = ApplicationSerializer
    queryset = Application.objects.select_related("school", "term")

    def get_queryset(self):
        params = self.request.query_params
        queryset = _scope(super().get_queryset(), params, prefix="school__")
        for field in ("term", "stage"):
            if params.get(field):
                queryset = queryset.filter(**{field: params[field]})
        return queryset


@extend_schema(tags=[STUDENTS_TAG])
class EnrollmentDashboardView(APIView):
    """Student Enrollment screen: active enrolment, admissions conversion, capacity
    utilisation, enrolment by campus and gender, per-school minimums, and the
    admissions funnel. Defaults to the latest term that has started.
    """

    @extend_schema(
        parameters=[AcademicDashboardQuerySerializer],
        responses=EnrollmentDashboardSerializer,
    )
    def get(self, request):
        query = AcademicDashboardQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        term = _resolve_term(params.get("term"))
        if term is None:
            return Response(
                {"detail": "No terms have been set up yet."},
                status=404,
            )

        active = _scope(
            Enrolment.objects.filter(
                term=term,
                status=Enrolment.Status.ACTIVE,
            ),
            params,
            prefix="school__",
        )
        total = active.count()

        # Enrolment by campus and gender, for the bar chart.
        Gender = StudentProfile.Gender
        counts = {}
        for row in active.values(
            "school__campus",
            "student__gender",
        ).annotate(n=Count("id")):
            counts[(row["school__campus"], row["student__gender"])] = row["n"]

        # Use campus values from the database to support legacy campus values.
        if params.get("campus"):
            campus_keys = [params["campus"]]
        else:
            campus_keys = list(
                School.objects.order_by()
                .values_list("campus", flat=True)
                .distinct()
                .order_by("campus")
            )

        campuses = []
        for key in campus_keys:
            boys = counts.get((key, Gender.MALE), 0)
            girls = counts.get((key, Gender.FEMALE), 0)
            campuses.append({
                "campus": key,
                "campus_display": key,
                "boys": boys,
                "girls": girls,
                "total": boys + girls,
            })

        boys = sum(campus["boys"] for campus in campuses)
        girls = sum(campus["girls"] for campus in campuses)

        # Per-school enrolment against capacity and the board's minimum.
        schools = _scope(School.objects.all(), params).annotate(
            enrolled=Count(
                "enrolments",
                filter=Q(
                    enrolments__term=term,
                    enrolments__status=Enrolment.Status.ACTIVE,
                ),
            )
        )
        school_rows = [{
            "id": school.pk,
            "name": school.name,
            "campus": school.campus,
            "enrolled": school.enrolled,
            "capacity": school.capacity,
            "minimum_enrolment": school.minimum_enrolment,
            "below_minimum": school.enrolled < school.minimum_enrolment,
        } for school in schools]
        capacity = sum(school.capacity for school in schools)

        # Admissions funnel: each application counts at its stage and every stage before it.
        applications = _scope(
            Application.objects.filter(term=term),
            params,
            prefix="school__",
        )
        stage_counts = dict(
            applications.values_list("stage").annotate(n=Count("id"))
        )
        order = Application.STAGE_ORDER
        applied = sum(stage_counts.values())
        pipeline = []

        for i, stage in enumerate(order):
            reached = sum(stage_counts.get(stage_value, 0) for stage_value in order[i:])
            pipeline.append({
                "stage": stage,
                "label": stage.label,
                "count": reached,
                "rate": _rate(reached, applied),
            })

        data = {
            "term": _term_summary(term),
            "summary": {
                "total_active_enrolment": total,
                # Applicants who became students out of all applications.
                "admissions_conversion": _rate(
                    pipeline[-1]["count"], applied
                ),
                "capacity": capacity,
                "capacity_utilisation": _rate(total, capacity),
            },
            "gender": {
                "boys": boys,
                "girls": girls,
                "boys_pct": _rate(boys, boys + girls),
                "girls_pct": _rate(girls, boys + girls),
            },
            "campuses": campuses,
            "schools": school_rows,
            "pipeline": pipeline,
        }
        return Response(EnrollmentDashboardSerializer(data).data)


@extend_schema(tags=[STUDENTS_TAG])
class RetentionDashboardView(APIView):
    """Student Retention screen, measured year to year. Students in the last term of the
    previous academic year (excluding those who graduated) are eligible to return; those
    enrolled in any term of the current academic year, up to the selected term, count as
    re-enrolled, whichever school they moved to. Withdrawals are for the current year to
    date; the at-risk count is for the selected term.
    """

    @extend_schema(
        parameters=[AcademicDashboardQuerySerializer],
        responses=RetentionDashboardSerializer,
    )
    def get(self, request):
        query = AcademicDashboardQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        term = _resolve_term(params.get("term"))
        if term is None:
            return Response(
                {"detail": "No terms have been set up yet."},
                status=404,
            )

        # This academic year so far, and the last term of the year before it.
        year_terms = Term.objects.filter(
            academic_year=term.academic_year,
            start_date__lte=term.start_date,
        )
        first_term = year_terms.order_by("start_date").first()
        if first_term is None:
            return Response(
                {"detail": "No terms have been set up for this academic year."},
                status=404,
            )
        year_start = first_term.start_date
        baseline = (
            Term.objects.filter(start_date__lt=year_start)
            .order_by("-start_date")
            .first()
        )

        # Who could have come back, and who did.
        eligible = _scope(
            Enrolment.objects.filter(term=baseline).exclude(
                status=Enrolment.Status.GRADUATED
            ),
            params,
            prefix="school__",
        ).annotate(
            returned=Exists(
                Enrolment.objects.filter(
                    term__in=year_terms,
                    student=OuterRef("student"),
                )
            )
        )
        rows = (
            eligible.values("student__nationality", "school__campus")
            .annotate(
                eligible=Count("id"),
                re_enrolled=Count("id", filter=Q(returned=True)),
            )
            .order_by("-eligible", "student__nationality")
        )
        by_nationality = [{
            "nationality": row["student__nationality"],
            "campus": row["school__campus"],
            "campus_display": row["school__campus"],
            "eligible": row["eligible"],
            "re_enrolled": row["re_enrolled"],
            "retention_rate": _rate(
                row["re_enrolled"], row["eligible"]
            ),
        } for row in rows]

        eligible_total = sum(row["eligible"] for row in by_nationality)
        re_enrolled_total = sum(
            row["re_enrolled"] for row in by_nationality
        )

        current = _scope(
            Enrolment.objects.filter(term=term),
            params,
            prefix="school__",
        )
        at_risk = current.filter(
            status=Enrolment.Status.ACTIVE,
            at_risk=True,
        ).count()

        # Withdrawals this year so far, by reason, largest first.
        year_enrolments = _scope(
            Enrolment.objects.filter(term__in=year_terms),
            params,
            prefix="school__",
        )
        reasons = (
            year_enrolments.filter(status=Enrolment.Status.WITHDRAWN)
            .values("withdrawal_reason")
            .annotate(n=Count("id"))
            .order_by("-n")
        )
        withdrawals_total = sum(row["n"] for row in reasons)
        withdrawal_reasons = [{
            "reason": row["withdrawal_reason"],
            "label": Enrolment.WithdrawalReason(
                row["withdrawal_reason"]
            ).label,
            "count": row["n"],
            "share": _rate(row["n"], withdrawals_total),
        } for row in reasons]

        data = {
            "term": _term_summary(term),
            "academic_year": term.academic_year,
            "compared_with": _term_summary(baseline),
            "summary": {
                "eligible_to_return": eligible_total,
                "total_re_enrolled": re_enrolled_total,
                "re_enrolment_rate": _rate(
                    re_enrolled_total, eligible_total
                ),
                "at_risk": at_risk,
            },
            "by_nationality": by_nationality,
            "withdrawals_total": withdrawals_total,
            "withdrawal_reasons": withdrawal_reasons,
        }
        return Response(RetentionDashboardSerializer(data).data)


# --- Academic performance -----------------------------------------------------------

PERFORMANCE_TAG = "Academics - Performance"
# The scale the overall average grade is read on when one section is chosen.
SECTION_SCALE = {
    School.Level.PRIMARY: "primary",
    School.Level.SECONDARY: "o_level",
}
TESTS = [Assessment.Kind.TEST_1, Assessment.Kind.TEST_2]


def _one_decimal(value):
    return round(float(value), 1) if value is not None else None


def _latest_year(academic_year):
    """'2026' gives 2026; '2025/2026' gives 2026."""
    years = re.findall(r"\d{4}", academic_year)
    return int(years[-1]) if years else None


@extend_schema(tags=[PERFORMANCE_TAG])
class SubjectViewSet(viewsets.ModelViewSet):
    serializer_class = SubjectSerializer
    queryset = Subject.objects.all()

    def get_queryset(self):
        queryset = super().get_queryset()
        for field in ("level", "category"):
            if self.request.query_params.get(field):
                queryset = queryset.filter(
                    **{field: self.request.query_params[field]}
                )
        return queryset


@extend_schema(tags=[PERFORMANCE_TAG])
class AssessmentViewSet(viewsets.ModelViewSet):
    serializer_class = AssessmentSerializer
    queryset = Assessment.objects.select_related("subject", "school", "term")

    def get_queryset(self):
        params = self.request.query_params
        queryset = _scope(
            super().get_queryset(), params, prefix="school__"
        )
        for field in ("term", "subject", "kind", "class_level"):
            if params.get(field):
                queryset = queryset.filter(**{field: params[field]})
        return queryset


@extend_schema(tags=[PERFORMANCE_TAG])
class AssessmentResultViewSet(viewsets.ModelViewSet):
    serializer_class = AssessmentResultSerializer
    queryset = AssessmentResult.objects.select_related(
        "assessment__subject", "assessment__school", "student"
    )

    def get_queryset(self):
        params = self.request.query_params
        queryset = _scope(
            super().get_queryset(),
            params,
            prefix="assessment__school__",
        )
        for param, field in (
            ("assessment", "assessment"),
            ("student", "student"),
            ("term", "assessment__term"),
        ):
            if params.get(param):
                queryset = queryset.filter(**{field: params[param]})
        return queryset


@extend_schema(tags=[PERFORMANCE_TAG])
class SyllabusCoverageViewSet(viewsets.ModelViewSet):
    serializer_class = SyllabusCoverageSerializer
    queryset = SyllabusCoverage.objects.select_related("subject")

    def get_queryset(self):
        params = self.request.query_params
        queryset = _scope(
            super().get_queryset(), params, prefix="school__"
        )
        for field in ("term", "subject", "class_level"):
            if params.get(field):
                queryset = queryset.filter(**{field: params[field]})
        return queryset


@extend_schema(tags=[PERFORMANCE_TAG])
class NationalExamResultViewSet(viewsets.ModelViewSet):
    serializer_class = NationalExamResultSerializer
    queryset = NationalExamResult.objects.all()

    def get_queryset(self):
        params = self.request.query_params
        queryset = _scope(
            super().get_queryset(), params, prefix="school__"
        )
        for field in ("exam", "year", "passed"):
            if params.get(field):
                queryset = queryset.filter(**{field: params[field]})
        return queryset


def _subject_figures(results):
    """Average mark, result count and passes per subject."""
    rows = results.values("assessment__subject").annotate(
        avg=Avg("mark"),
        n=Count("id"),
        passes=Count("id", filter=Q(mark__gte=PASS_MARK)),
    )
    return {row["assessment__subject"]: row for row in rows}


@extend_schema(tags=[PERFORMANCE_TAG])
class PerformanceDashboardView(APIView):
    """Academic Performance screen for one term: syllabus coverage, the share of
    students passing (average mark of 50% or more across their assessments), the
    average grade, each level's grade distribution, results per subject against the
    previous term, Test 1 and Test 2 results, and the latest PLE, UCE and UACE pass
    rates. Defaults to the latest term that has started; filter by campus, section
    (`level`) or school.
    """

    @extend_schema(
        parameters=[PerformanceDashboardQuerySerializer],
        responses=PerformanceDashboardSerializer,
    )
    def get(self, request):
        query = PerformanceDashboardQuerySerializer(
            data=request.query_params
        )
        query.is_valid(raise_exception=True)
        params = query.validated_data
        term = _resolve_term(params.get("term"))
        if term is None:
            return Response(
                {"detail": "No terms have been set up yet."},
                status=404,
            )

        previous = (
            Term.objects.filter(start_date__lt=term.start_date)
            .order_by("-start_date")
            .first()
        )

        def term_results(of_term):
            return _scope(
                AssessmentResult.objects.filter(
                    assessment__term=of_term
                ),
                params,
                prefix="assessment__school__",
            )

        results = term_results(term)

        # Summary: each student's average across all their assessments this term.
        averages = [
            row["avg"]
            for row in results.values("student").annotate(avg=Avg("mark"))
        ]
        passing = sum(1 for average in averages if average >= PASS_MARK)
        overall = results.aggregate(avg=Avg("mark"))["avg"]
        scale = SECTION_SCALE.get(params.get("level"))
        syllabus = _scope(
            SyllabusCoverage.objects.filter(term=term),
            params,
            prefix="school__",
        ).aggregate(
            planned=Sum("topics_planned"),
            covered=Sum("topics_covered"),
        )
        planned = syllabus["planned"] or 0
        covered = syllabus["covered"] or 0

        # Grade distribution: each student's average per subject level, on that level's scale.
        counts = {level: {} for level in GRADE_SCALES}
        per_level = results.values(
            "student", "assessment__subject__level"
        ).annotate(avg=Avg("mark"))

        for row in per_level:
            level = row["assessment__subject__level"]
            grade = grade_for(level, row["avg"])
            counts[level][grade] = counts[level].get(grade, 0) + 1

        grade_distribution = []
        for level, bands in GRADE_SCALES.items():
            students = sum(counts[level].values())
            if not students:
                continue

            # Best grade first, every grade listed even when nobody got it.
            grade_distribution.append({
                "level": level,
                "level_display": Subject.Level(level).label,
                "students": students,
                "grades": [{
                    "grade": grade,
                    "students": counts[level].get(grade, 0),
                    "share": _rate(
                        counts[level].get(grade, 0), students
                    ),
                } for _, grade in bands],
            })

        # Subjects this term against the previous term.
        now = _subject_figures(results)
        before = _subject_figures(term_results(previous)) if previous else {}
        subjects = sorted(
            Subject.objects.in_bulk(list(now)).values(),
            key=lambda subject: (subject.level, subject.name),
        )
        subject_rows = []

        for subject in subjects:
            row = now[subject.pk]
            old = before.get(subject.pk)
            subject_rows.append({
                "id": subject.pk,
                "subject": subject.name,
                "code": subject.code,
                "level": subject.level,
                "level_display": subject.get_level_display(),
                "category": subject.category,
                "average_mark": _one_decimal(row["avg"]),
                "pass_rate": _rate(row["passes"], row["n"]),
                "previous_pass_rate": (
                    _rate(old["passes"], old["n"]) if old else None
                ),
                "results": row["n"],
            })

        # Test 1 and Test 2, per subject.
        tests = results.filter(assessment__kind__in=TESTS)
        by_kind = {}

        for row in tests.values(
            "assessment__subject", "assessment__kind"
        ).annotate(
            avg=Avg("mark"),
            n=Count("id"),
            passes=Count("id", filter=Q(mark__gte=PASS_MARK)),
        ):
            by_kind[
                (row["assessment__subject"], row["assessment__kind"])
            ] = row

        assessed = dict(
            tests.values_list("assessment__subject").annotate(
                n=Count("student", distinct=True)
            )
        )
        test_rows = []

        for subject in subjects:
            if subject.pk not in assessed:
                continue

            first = by_kind.get(
                (subject.pk, Assessment.Kind.TEST_1)
            )
            second = by_kind.get(
                (subject.pk, Assessment.Kind.TEST_2)
            )
            test_rows.append({
                "id": subject.pk,
                "subject": subject.name,
                "level": subject.level,
                "level_display": subject.get_level_display(),
                "test_1_average": (
                    _one_decimal(first["avg"]) if first else None
                ),
                "test_2_average": (
                    _one_decimal(second["avg"]) if second else None
                ),
                "test_1_pass_rate": (
                    _rate(first["passes"], first["n"]) if first else None
                ),
                "test_2_pass_rate": (
                    _rate(second["passes"], second["n"]) if second else None
                ),
                "students_assessed": assessed[subject.pk],
            })

        # National exams: the latest sitting up to this academic year.
        exams = _scope(
            NationalExamResult.objects.all(),
            params,
            prefix="school__",
        )
        cap = _latest_year(term.academic_year)
        if cap is not None:
            exams = exams.filter(year__lte=cap)

        national_exams = []
        for exam in NationalExamResult.Exam:
            sittings = exams.filter(exam=exam)
            year = (
                sittings.order_by("-year")
                .values_list("year", flat=True)
                .first()
            )
            if year is None:
                continue

            sitting = sittings.filter(year=year)
            divisions = (
                sitting.exclude(division="")
                .values("division")
                .annotate(n=Count("id"))
                .order_by("division")
            )
            total = sitting.count()
            passed = sitting.filter(passed=True).count()
            national_exams.append({
                "exam": exam,
                "label": exam.label,
                "year": year,
                "sat": total,
                "passed": passed,
                "pass_rate": _rate(passed, total),
                "divisions": [{
                    "division": division["division"],
                    "label": NationalExamResult.Division(
                        division["division"]
                    ).label,
                    "candidates": division["n"],
                } for division in divisions],
            })

        data = {
            "term": _term_summary(term),
            "compared_with": _term_summary(previous),
            "summary": {
                "syllabus_coverage": _rate(covered, planned),
                "topics_covered": covered,
                "topics_planned": planned,
                "student_performance": _rate(passing, len(averages)),
                "students_passing": passing,
                "students_assessed": len(averages),
                "average_mark": _one_decimal(overall),
                "average_grade": (
                    grade_for(scale, overall)
                    if scale and overall is not None
                    else None
                ),
            },
            "grade_distribution": grade_distribution,
            "national_exams": national_exams,
            "subjects": subject_rows,
            "tests": test_rows,
        }
        return Response(PerformanceDashboardSerializer(data).data)
