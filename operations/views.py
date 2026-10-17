from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Asset, Employee, Facility, StaffAttendance, WorkforceUnit
from .serializers import (
    AssetDashboardQuerySerializer,
    AssetDashboardSerializer,
    AssetSerializer,
    EmployeeSerializer,
    FacilitySerializer,
    HRDashboardQuerySerializer,
    HRDashboardSerializer,
    StaffAttendanceSerializer,
    WorkforceUnitSerializer,
)

# Default look-back window for the HR dashboard when no start date is given.
DEFAULT_DASHBOARD_DAYS = 30


def _rate(part, whole):
    """Percentage rounded to one decimal place, or None when there is nothing to measure."""
    return round(part * 100 / whole, 1) if whole else None


@extend_schema(tags=["Operations - HR & Workforce"])
class WorkforceUnitViewSet(viewsets.ModelViewSet):
    serializer_class = WorkforceUnitSerializer
    queryset = WorkforceUnit.objects.all()

    def get_queryset(self):
        queryset = super().get_queryset()
        campus = self.request.query_params.get("campus")
        if campus:
            queryset = queryset.filter(campus=campus)
        return queryset


@extend_schema(tags=["Operations - HR & Workforce"])
class EmployeeViewSet(viewsets.ModelViewSet):
    serializer_class = EmployeeSerializer
    queryset = Employee.objects.select_related("unit")

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("unit"):
            queryset = queryset.filter(unit_id=params["unit"])
        if params.get("campus"):
            queryset = queryset.filter(unit__campus=params["campus"])
        if params.get("is_active") in {"true", "false"}:
            queryset = queryset.filter(is_active=params["is_active"] == "true")
        return queryset


@extend_schema(tags=["Operations - HR & Workforce"])
class StaffAttendanceViewSet(viewsets.ModelViewSet):
    serializer_class = StaffAttendanceSerializer
    queryset = StaffAttendance.objects.select_related("employee")

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("employee"):
            queryset = queryset.filter(employee_id=params["employee"])
        if params.get("unit"):
            queryset = queryset.filter(employee__unit_id=params["unit"])
        if params.get("date"):
            queryset = queryset.filter(date=params["date"])
        if params.get("start"):
            queryset = queryset.filter(date__gte=params["start"])
        if params.get("end"):
            queryset = queryset.filter(date__lte=params["end"])
        return queryset


@extend_schema(tags=["Operations - HR & Workforce"])
class HRDashboardView(APIView):
    """Workforce distribution and attendance register for the HR & Workforce dashboard.

    Attendance rates cover start..end; the absence counts (on leave, on training, ...)
    are a snapshot of the end date. Only active employees are counted.
    """

    @extend_schema(parameters=[HRDashboardQuerySerializer], responses=HRDashboardSerializer)
    def get(self, request):
        query = HRDashboardQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data

        end = params.get("end") or timezone.localdate()
        start = params.get("start") or end - timedelta(days=DEFAULT_DASHBOARD_DAYS - 1)

        units = WorkforceUnit.objects.all()
        if params.get("campus"):
            units = units.filter(campus=params["campus"])
        if params.get("unit"):
            units = units.filter(pk=params["unit"])

        active = Q(employees__is_active=True)
        in_period = active & Q(employees__attendance_records__date__range=(start, end))
        units = units.annotate(
            headcount=Count("employees", filter=active, distinct=True),
            attendance_days=Count("employees__attendance_records", filter=in_period),
            present_days=Count(
                "employees__attendance_records",
                filter=in_period
                & Q(employees__attendance_records__status=StaffAttendance.Status.PRESENT),
            ),
        )

        absences = {}
        snapshot = (
            StaffAttendance.objects.filter(
                date=end, employee__is_active=True, employee__unit__in=units
            )
            .exclude(status=StaffAttendance.Status.PRESENT)
            .values("employee__unit", "status")
            .annotate(total=Count("id"))
        )
        for row in snapshot:
            absences.setdefault(row["employee__unit"], {})[row["status"]] = row["total"]

        rows, total_staff, teaching_staff, attendance_days, present_days = [], 0, 0, 0, 0
        for unit in units:
            total_staff += unit.headcount
            if unit.staff_category == WorkforceUnit.StaffCategory.TEACHING:
                teaching_staff += unit.headcount
            attendance_days += unit.attendance_days
            present_days += unit.present_days
            rows.append({
                "id": unit.pk,
                "name": unit.name,
                "staff_category": unit.staff_category,
                "staff_category_display": unit.get_staff_category_display(),
                "campus": unit.campus,
                "location": unit.location,
                "headcount": unit.headcount,
                "attendance_rate": _rate(unit.present_days, unit.attendance_days),
                "absences": absences.get(unit.pk, {}),
            })

        # Staffing ratio is teaching : non-teaching staff, expressed as 1 : x.
        non_teaching_staff = total_staff - teaching_staff
        staffing_ratio = round(non_teaching_staff / teaching_staff, 1) if teaching_staff else None

        data = {
            "start": start,
            "end": end,
            "summary": {
                "total_staff": total_staff,
                "teaching_staff": teaching_staff,
                "non_teaching_staff": non_teaching_staff,
                "staffing_ratio": staffing_ratio,
                "staffing_ratio_display": (
                    f"1:{staffing_ratio}" if staffing_ratio is not None else None
                ),
                "workforce_attendance_rate": _rate(present_days, attendance_days),
            },
            "units": rows,
        }
        return Response(HRDashboardSerializer(data).data)


@extend_schema(tags=["Operations - Facilities & Maintenance"])
class FacilityViewSet(viewsets.ModelViewSet):
    serializer_class = FacilitySerializer
    queryset = Facility.objects.all()

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        for field in ("campus", "facility_type", "status"):
            if params.get(field):
                queryset = queryset.filter(**{field: params[field]})
        return queryset


@extend_schema(tags=["Operations - Assets & Equipment"])
class AssetViewSet(viewsets.ModelViewSet):
    serializer_class = AssetSerializer
    queryset = Asset.objects.select_related("facility")

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if params.get("campus"):
            queryset = queryset.filter(facility__campus=params["campus"])
        if params.get("facility"):
            queryset = queryset.filter(facility_id=params["facility"])
        for field in ("category", "condition"):
            if params.get(field):
                queryset = queryset.filter(**{field: params[field]})
        return queryset


@extend_schema(tags=["Operations - Assets & Equipment"])
class AssetDashboardView(APIView):
    """Institutional asset register and condition summary for the Assets & Equipment dashboard.

    The register is a current snapshot, not a date range. Decommissioned assets are left
    out of every figure. Total assets and operational rate count units (quantity);
    capital risk is the share of register value that needs servicing or is critical.
    """

    @extend_schema(parameters=[AssetDashboardQuerySerializer], responses=AssetDashboardSerializer)
    def get(self, request):
        query = AssetDashboardQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data

        assets = (
            Asset.objects.select_related("facility")
            .exclude(condition=Asset.Condition.DECOMMISSIONED)
            .order_by("name")
        )
        if params.get("campus"):
            assets = assets.filter(facility__campus=params["campus"])
        if params.get("category"):
            assets = assets.filter(category=params["category"])
        if params.get("facility"):
            assets = assets.filter(facility_id=params["facility"])

        line_value = ExpressionWrapper(
            F("quantity") * F("unit_value"),
            output_field=DecimalField(max_digits=20, decimal_places=2),
        )
        by_condition = {
            row["condition"]: row
            for row in assets.order_by()
            .values("condition")
            .annotate(units=Sum("quantity"), value=Sum(line_value))
        }

        total_assets = sum(row["units"] for row in by_condition.values())
        total_value = sum((row["value"] for row in by_condition.values()), Decimal(0))
        operational = by_condition.get(Asset.Condition.OPERATIONAL)
        operational_units = operational["units"] if operational else 0
        at_risk_value = sum(
            (
                by_condition[condition]["value"]
                for condition in (Asset.Condition.SERVICING_REQUIRED, Asset.Condition.CRITICAL)
                if condition in by_condition
            ),
            Decimal(0),
        )

        data = {
            "summary": {
                "total_assets": total_assets,
                "total_value": total_value,
                "operational_rate": _rate(operational_units, total_assets),
                "capital_risk": _rate(at_risk_value, total_value),
                "capital_at_risk_value": at_risk_value,
                "units_by_condition": {
                    condition: row["units"] for condition, row in by_condition.items()
                },
            },
            "assets": assets,
        }
        return Response(AssetDashboardSerializer(data).data)
