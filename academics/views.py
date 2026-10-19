from django.db.models import Count, Exists, OuterRef, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Academic,
    Application,
    Attendance,
    Curricular,
    Enrolment,
    Events,
    GradeResult,
    Homework,
    School,
    Section,
    Staff,
    Student,
    StudentProfile,
    Term,
)
from .serializers import (
    AcademicDashboardQuerySerializer,
    AcademicSerializer,
    ApplicationSerializer,
    AttendanceSerializer,
    CurricularSerializer,
    EnrollmentDashboardSerializer,
    EnrolmentSerializer,
    EventsSerializer,
    GradeResultSerializer,
    HomeworkSerializer,
    RetentionDashboardSerializer,
    SchoolSerializer,
    SectionSerializer,
    StaffSerializer,
    StudentProfileSerializer,
    StudentSerializer,
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
    started = Term.objects.filter(start_date__lte=timezone.localdate()).order_by("-start_date")
    return started.first() or Term.objects.order_by("-start_date").first()


def _scope(queryset, params, prefix=""):
    """Filter a queryset by the campus and school query parameters."""
    if params.get("campus"):
        queryset = queryset.filter(**{f"{prefix}campus": params["campus"]})
    if params.get("school"):
        queryset = queryset.filter(**{f"{prefix}{'pk' if not prefix else 'id'}": params["school"]})
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
                queryset = queryset.filter(**{field: self.request.query_params[field]})
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
        parameters=[AcademicDashboardQuerySerializer], responses=EnrollmentDashboardSerializer
    )
    def get(self, request):
        query = AcademicDashboardQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        term = _resolve_term(params.get("term"))
        if term is None:
            return Response({"detail": "No terms have been set up yet."}, status=404)

        active = _scope(
            Enrolment.objects.filter(term=term, status=Enrolment.Status.ACTIVE),
            params, prefix="school__",
        )
        total = active.count()

        # Enrolment by campus and gender, for the bar chart.
        Gender = StudentProfile.Gender
        counts = {}
        for row in active.values("school__campus", "student__gender").annotate(n=Count("id")):
            counts[(row["school__campus"], row["student__gender"])] = row["n"]
        campus_keys = [params["campus"]] if params.get("campus") else School.Campus.values
        campuses = []
        for key in campus_keys:
            boys = counts.get((key, Gender.MALE), 0)
            girls = counts.get((key, Gender.FEMALE), 0)
            campuses.append({
                "campus": key, "campus_display": School.Campus(key).label,
                "boys": boys, "girls": girls, "total": boys + girls,
            })
        boys = sum(c["boys"] for c in campuses)
        girls = sum(c["girls"] for c in campuses)

        # Per-school enrolment against capacity and the board's minimum.
        schools = _scope(School.objects.all(), params).annotate(
            enrolled=Count(
                "enrolments",
                filter=Q(enrolments__term=term, enrolments__status=Enrolment.Status.ACTIVE),
            )
        )
        school_rows = [{
            "id": s.pk, "name": s.name, "campus": s.campus, "enrolled": s.enrolled,
            "capacity": s.capacity, "minimum_enrolment": s.minimum_enrolment,
            "below_minimum": s.enrolled < s.minimum_enrolment,
        } for s in schools]
        capacity = sum(s.capacity for s in schools)

        # Admissions funnel: each application counts at its stage and every stage before it.
        applications = _scope(Application.objects.filter(term=term), params, prefix="school__")
        stage_counts = dict(applications.values_list("stage").annotate(n=Count("id")))
        order = Application.STAGE_ORDER
        applied = sum(stage_counts.values())
        pipeline = []
        for i, stage in enumerate(order):
            reached = sum(stage_counts.get(s, 0) for s in order[i:])
            pipeline.append({
                "stage": stage, "label": stage.label, "count": reached,
                "rate": _rate(reached, applied),
            })

        data = {
            "term": _term_summary(term),
            "summary": {
                "total_active_enrolment": total,
                # applicants who became students (the last funnel stage) out of all applications
                "admissions_conversion": _rate(pipeline[-1]["count"], applied),
                "capacity": capacity,
                "capacity_utilisation": _rate(total, capacity),
            },
            "gender": {
                "boys": boys, "girls": girls,
                "boys_pct": _rate(boys, boys + girls), "girls_pct": _rate(girls, boys + girls),
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
        parameters=[AcademicDashboardQuerySerializer], responses=RetentionDashboardSerializer
    )
    def get(self, request):
        query = AcademicDashboardQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        term = _resolve_term(params.get("term"))
        if term is None:
            return Response({"detail": "No terms have been set up yet."}, status=404)
        # This academic year so far, and the last term of the year before it.
        year_terms = Term.objects.filter(
            academic_year=term.academic_year, start_date__lte=term.start_date
        )
        year_start = year_terms.order_by("start_date").first().start_date
        baseline = (
            Term.objects.filter(start_date__lt=year_start).order_by("-start_date").first()
        )

        # Who could have come back, and who did.
        eligible = _scope(
            Enrolment.objects.filter(term=baseline).exclude(status=Enrolment.Status.GRADUATED),
            params, prefix="school__",
        ).annotate(
            returned=Exists(
                Enrolment.objects.filter(term__in=year_terms, student=OuterRef("student"))
            )
        )
        rows = (
            eligible.values("student__nationality", "school__campus")
            .annotate(eligible=Count("id"), re_enrolled=Count("id", filter=Q(returned=True)))
            .order_by("-eligible", "student__nationality")
        )
        by_nationality = [{
            "nationality": r["student__nationality"], "campus": r["school__campus"],
            "campus_display": School.Campus(r["school__campus"]).label,
            "eligible": r["eligible"], "re_enrolled": r["re_enrolled"],
            "retention_rate": _rate(r["re_enrolled"], r["eligible"]),
        } for r in rows]
        eligible_total = sum(r["eligible"] for r in by_nationality)
        re_enrolled_total = sum(r["re_enrolled"] for r in by_nationality)

        current = _scope(Enrolment.objects.filter(term=term), params, prefix="school__")
        at_risk = current.filter(status=Enrolment.Status.ACTIVE, at_risk=True).count()

        # Withdrawals this year so far, by reason, largest first.
        year_enrolments = _scope(
            Enrolment.objects.filter(term__in=year_terms), params, prefix="school__"
        )
        reasons = (
            year_enrolments.filter(status=Enrolment.Status.WITHDRAWN)
            .values("withdrawal_reason").annotate(n=Count("id")).order_by("-n")
        )
        withdrawals_total = sum(r["n"] for r in reasons)
        withdrawal_reasons = [{
            "reason": r["withdrawal_reason"],
            "label": Enrolment.WithdrawalReason(r["withdrawal_reason"]).label,
            "count": r["n"], "share": _rate(r["n"], withdrawals_total),
        } for r in reasons]

        data = {
            "term": _term_summary(term),
            "academic_year": term.academic_year,
            "compared_with": _term_summary(baseline),
            "summary": {
                "eligible_to_return": eligible_total,
                "total_re_enrolled": re_enrolled_total,
                "re_enrolment_rate": _rate(re_enrolled_total, eligible_total),
                "at_risk": at_risk,
            },
            "by_nationality": by_nationality,
            "withdrawals_total": withdrawals_total,
            "withdrawal_reasons": withdrawal_reasons,
        }
        return Response(RetentionDashboardSerializer(data).data)
