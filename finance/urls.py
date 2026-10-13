from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CreditorViewSet,
    DepartmentBudgetViewSet,
    DepartmentViewSet,
    FiscalYearViewSet,
    LiabilityViewSet,
    MonthlyRevenueTargetViewSet,
    RevenueRecordViewSet,
)

router = DefaultRouter()
router.register('creditors', CreditorViewSet)
router.register('departments', DepartmentViewSet)
router.register('department-budgets', DepartmentBudgetViewSet)
router.register('fiscal-years', FiscalYearViewSet)
router.register('liabilities', LiabilityViewSet)
router.register('monthly-revenue-targets', MonthlyRevenueTargetViewSet)
router.register('revenue-records', RevenueRecordViewSet)
urlpatterns=[
    path('finance/', include(router.urls)),
   
]