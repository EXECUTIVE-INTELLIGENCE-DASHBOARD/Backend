from drf_spectacular.utils import extend_schema
from rest_framework import viewsets

from .models import (
    Creditor,
    Department,
    DepartmentBudget,
    FiscalYear,
    Liability,
    MonthlyRevenueTarget,
    RevenueRecord,
)
from .serializers import (
    CreditorSerializer,
    DepartmentBudgetSerializer,
    DepartmentSerializer,
    FiscalYearSerializer,
    LiabilitySerializer,
    MonthlyRevenueTargetSerializer,
    RevenueRecordSerializer,
)


# Create your views here.
@extend_schema(tags=["Finance - Liabilities"])
class CreditorViewSet(viewsets.ModelViewSet):
    serializer_class = CreditorSerializer
    queryset = Creditor.objects.all()
@extend_schema(tags=["Finance - Budgets"])
class DepartmentViewSet(viewsets.ModelViewSet):
    serializer_class = DepartmentSerializer
    queryset = Department.objects.all()
@extend_schema(tags=["Finance - Budgets"])
class DepartmentBudgetViewSet(viewsets.ModelViewSet):
    serializer_class = DepartmentBudgetSerializer
    queryset = DepartmentBudget.objects.all()
@extend_schema(tags=["Finance - Budgets"])
class FiscalYearViewSet(viewsets.ModelViewSet):
    serializer_class = FiscalYearSerializer
    queryset = FiscalYear.objects.all()
@extend_schema(tags=["Finance - Liabilities"])
class LiabilityViewSet(viewsets.ModelViewSet):
    serializer_class = LiabilitySerializer
    queryset = Liability.objects.all()
@extend_schema(tags=["Finance - Revenue"])
class MonthlyRevenueTargetViewSet(viewsets.ModelViewSet):
    serializer_class = MonthlyRevenueTargetSerializer
    queryset = MonthlyRevenueTarget.objects.all()
@extend_schema(tags=["Finance - Revenue"])
class RevenueRecordViewSet(viewsets.ModelViewSet):
    serializer_class = RevenueRecordSerializer
    queryset = RevenueRecord.objects.all()

    