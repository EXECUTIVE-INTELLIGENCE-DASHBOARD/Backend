#URL configuration for finance APIs and executive dashboards.

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()

router.register("fiscal-years", views.FiscalYearViewSet)
router.register("departments", views.DepartmentViewSet)
router.register("department-budgets", views.DepartmentBudgetViewSet)
router.register("monthly-department-budgets", views.MonthlyDepartmentBudgetViewSet)
router.register("expenses", views.ExpenseTransactionViewSet)
router.register("creditors", views.CreditorViewSet)
router.register("liabilities", views.LiabilityViewSet)
router.register("revenue-records", views.RevenueRecordViewSet)
router.register("monthly-revenue-targets", views.MonthlyRevenueTargetViewSet)
router.register("fee-invoices", views.FeeInvoiceViewSet)
router.register("fee-payments", views.FeePaymentViewSet)
router.register("bank-accounts", views.BankAccountViewSet)
router.register("cash-movements", views.CashMovementViewSet)
router.register("cash-forecasts", views.CashForecastViewSet)
router.register("loans", views.LoanViewSet)
router.register("loan-repayments", views.LoanRepaymentViewSet)


urlpatterns = [
    path("", include(router.urls)),
    path("finance/liability/dashboard/",views.LiabilityDashboardView
         .as_view(), name="dashboard-liability",),
    path("finance/revenue/dashboard/", views.RevenueDashboardView
         .as_view(),name="dashboard-revenue",),
    path("finance/procurement/dashboard/",views.ProcurementDashboardView
         .as_view(), name="dashboard-procurement",),
    path("finance/expense/dashboard/", views.ExpenseDashboardView
         .as_view(), name="dashboard-expense",),
]
