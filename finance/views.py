
"""Finance API views for CRUD operations and executive dashboard calculations."""

from datetime import timedelta
from decimal import Decimal

from django.db.models import (
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from procurement.models import ProcurementTransaction

from .models import (
    BankAccount,
    CashForecast,
    CashMovement,
    Creditor,
    Department,
    DepartmentBudget,
    ExpenseTransaction,
    FeeInvoice,
    FeePayment,
    FiscalYear,
    Liability,
    Loan,
    LoanRepayment,
    MonthlyDepartmentBudget,
    MonthlyRevenueTarget,
    RevenueRecord,
)
from .serializers import (
    BankAccountSerializer,
    CashForecastSerializer,
    CashMovementSerializer,
    CreditorSerializer,
    DepartmentBudgetSerializer,
    DepartmentSerializer,
    ExpenseTransactionSerializer,
    FeeInvoiceSerializer,
    FeePaymentSerializer,
    FinanceDashboardResponseSerializer,
    FiscalYearSerializer,
    LiabilitySerializer,
    LoanRepaymentSerializer,
    LoanSerializer,
    MonthlyDepartmentBudgetSerializer,
    MonthlyRevenueTargetSerializer,
    RevenueRecordSerializer,
)

BUDGET_TAG = "Finance - Budgets"
LIABILITY_TAG = "Finance - Liabilities"
REVENUE_TAG = "Finance - Revenue"

ZERO = Decimal("0.00")
MONEY_FIELD = DecimalField(max_digits=20, decimal_places=2)


def _sum(queryset, field):
    """Return a monetary total, using zero when no records match."""
    return queryset.aggregate(total=Sum(field))["total"] or ZERO


def _percentage(part, whole):
    """Calculate a percentage without dividing by zero."""
    return round(float(part) * 100 / float(whole), 2) if whole else 0


def _filters(queryset, params, fields):
    """Apply supplied query parameters as exact field filters."""
    filters = {
        field: params[field]
        for field in fields
        if params.get(field) not in (None, "")
    }
    return queryset.filter(**filters)


def _date_filters(queryset, params, field):
    """Apply optional inclusive start and end date filters."""
    start_date = params.get("start_date")
    end_date = params.get("end_date")

    if start_date:
        queryset = queryset.filter(**{f"{field}__gte": start_date})

    if end_date:
        queryset = queryset.filter(**{f"{field}__lte": end_date})

    return queryset


def _group_sum(queryset, *fields, amount_field="amount"):
    """Group records and return totals and record counts for dashboard charts."""
    return list(
        queryset.values(*fields)
        .annotate(
            total=Coalesce(
                Sum(amount_field),
                Value(ZERO),
                output_field=MONEY_FIELD,
            ),
            records=Count("id"),
        )
        .order_by(*fields)
    )


def _today():
    """Return today's date in the configured Django timezone."""
    return timezone.localdate()


def _liabilities():
    """Annotate liabilities with the unpaid amount."""
    return (
        Liability.objects.annotate(
            outstanding=ExpressionWrapper(
                F("amount") - F("paid_amount"),
                output_field=MONEY_FIELD,
            )
        )
        .filter(outstanding__gt=ZERO)
    )


# CRUD viewsets.

@extend_schema(tags=[BUDGET_TAG])
class FiscalYearViewSet(viewsets.ModelViewSet):
    queryset = FiscalYear.objects.all()
    serializer_class = FiscalYearSerializer


@extend_schema(tags=[BUDGET_TAG])
class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer


@extend_schema(tags=[BUDGET_TAG])
class DepartmentBudgetViewSet(viewsets.ModelViewSet):
    queryset = DepartmentBudget.objects.select_related(
        "department",
        "fiscal_year",
    ).all()
    serializer_class = DepartmentBudgetSerializer


@extend_schema(tags=[BUDGET_TAG])
class MonthlyDepartmentBudgetViewSet(viewsets.ModelViewSet):
    queryset = MonthlyDepartmentBudget.objects.select_related(
        "department",
        "fiscal_year",
    ).all()
    serializer_class = MonthlyDepartmentBudgetSerializer


@extend_schema(tags=[BUDGET_TAG])
class ExpenseTransactionViewSet(viewsets.ModelViewSet):
    queryset = ExpenseTransaction.objects.select_related(
        "department",
        "school",
    ).all()
    serializer_class = ExpenseTransactionSerializer


@extend_schema(tags=[LIABILITY_TAG])
class CreditorViewSet(viewsets.ModelViewSet):
    queryset = Creditor.objects.all()
    serializer_class = CreditorSerializer


@extend_schema(tags=[LIABILITY_TAG])
class LiabilityViewSet(viewsets.ModelViewSet):
    queryset = Liability.objects.select_related("creditor").all()
    serializer_class = LiabilitySerializer


@extend_schema(tags=[REVENUE_TAG])
class RevenueRecordViewSet(viewsets.ModelViewSet):
    queryset = RevenueRecord.objects.select_related(
        "fiscal_year",
        "school",
    ).all()
    serializer_class = RevenueRecordSerializer


@extend_schema(tags=[REVENUE_TAG])
class MonthlyRevenueTargetViewSet(viewsets.ModelViewSet):
    queryset = MonthlyRevenueTarget.objects.select_related(
        "fiscal_year",
        "school",
    ).all()
    serializer_class = MonthlyRevenueTargetSerializer


@extend_schema(tags=[REVENUE_TAG])
class FeeInvoiceViewSet(viewsets.ModelViewSet):
    queryset = FeeInvoice.objects.select_related(
        "school",
        "fiscal_year",
    ).all()
    serializer_class = FeeInvoiceSerializer


@extend_schema(tags=[REVENUE_TAG])
class FeePaymentViewSet(viewsets.ModelViewSet):
    queryset = FeePayment.objects.select_related("invoice").all()
    serializer_class = FeePaymentSerializer


@extend_schema(tags=[BUDGET_TAG])
class BankAccountViewSet(viewsets.ModelViewSet):
    queryset = BankAccount.objects.select_related("school").all()
    serializer_class = BankAccountSerializer


@extend_schema(tags=[BUDGET_TAG])
class CashMovementViewSet(viewsets.ModelViewSet):
    queryset = CashMovement.objects.select_related("account").all()
    serializer_class = CashMovementSerializer


@extend_schema(tags=[BUDGET_TAG])
class CashForecastViewSet(viewsets.ModelViewSet):
    queryset = CashForecast.objects.select_related("school").all()
    serializer_class = CashForecastSerializer


@extend_schema(tags=[LIABILITY_TAG])
class LoanViewSet(viewsets.ModelViewSet):
    queryset = Loan.objects.select_related("school", "creditor").all()
    serializer_class = LoanSerializer


@extend_schema(tags=[LIABILITY_TAG])
class LoanRepaymentViewSet(viewsets.ModelViewSet):
    queryset = LoanRepayment.objects.select_related("loan").all()
    serializer_class = LoanRepaymentSerializer


@extend_schema(
    tags=[BUDGET_TAG],
    responses=FinanceDashboardResponseSerializer,
)
class ExpenseDashboardView(APIView):
    def get(self, request):
        today = _today()
        params = request.query_params
        start_date = params.get(
            "start_date",
            today.replace(month=1, day=1),
        )
        end_date = params.get("end_date", today)

        expenses = ExpenseTransaction.objects.filter(
            expense_date__gte=start_date,
            expense_date__lte=end_date,
        )
        expenses = _filters(
            expenses,
            params,
            ("school_id", "department_id", "currency"),
        )

        budgets = DepartmentBudget.objects.select_related(
            "department",
            "fiscal_year",
        )
        budgets = _filters(
            budgets,
            params,
            ("department_id", "fiscal_year_id", "currency"),
        )

        total_spend = _sum(expenses, "amount")
        transaction_count = expenses.count()
        budget_total = _sum(budgets, "budget_amount")

        return Response(
            {
                "period": {
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                },
                "summary": {
                    "total_spend": total_spend,
                    "transaction_count": transaction_count,
                    "average_transaction": (
                        round(total_spend / transaction_count, 2)
                        if transaction_count
                        else ZERO
                    ),
                    "budget_total": budget_total,
                    "budget_remaining": budget_total - total_spend,
                    "budget_used_percent": _percentage(
                        total_spend,
                        budget_total,
                    ),
                    "over_budget": total_spend > budget_total,
                },
                "spending_by_category": _group_sum(
                    expenses,
                    "category",
                    "currency",
                ),
                "spending_by_department": _group_sum(
                    expenses,
                    "department__name",
                    "currency",
                ),
                "department_budgets": _group_sum(
                    budgets,
                    "department__name",
                    "currency",
                    amount_field="budget_amount",
                ),
                "monthly_spending": list(
                    expenses.values(
                        "expense_date__year",
                        "expense_date__month",
                        "currency",
                    )
                    .annotate(
                        total=Sum("amount"),
                        transactions=Count("id"),
                    )
                    .order_by(
                        "expense_date__year",
                        "expense_date__month",
                    )
                ),
            }
        )


@extend_schema(
    tags=[REVENUE_TAG],
    responses=FinanceDashboardResponseSerializer,
)
class RevenueDashboardView(APIView):
    def get(self, request):
        params = request.query_params

        records = RevenueRecord.objects.select_related(
            "school",
            "fiscal_year",
        )
        records = _date_filters(records, params, "billing_date")
        records = _filters(
            records,
            params,
            ("school_id", "fiscal_year_id", "currency"),
        )

        targets = _filters(
            MonthlyRevenueTarget.objects.all(),
            params,
            ("school_id", "fiscal_year_id", "currency"),
        )

        billed = _sum(records, "billed_amount")
        realized = _sum(records, "realized_amount")
        arrears = max(billed - realized, ZERO)

        monthly_targets = list(
            targets.values("month", "currency")
            .annotate(
                target=Coalesce(
                    Sum("target_amount"),
                    Value(ZERO),
                    output_field=MONEY_FIELD,
                ),
                realized=Coalesce(
                    Sum("realized_amount"),
                    Value(ZERO),
                    output_field=MONEY_FIELD,
                ),
            )
            .order_by("month")
        )

        for item in monthly_targets:
            item["achievement_percent"] = _percentage(
                item["realized"],
                item["target"],
            )
            item["variance"] = item["realized"] - item["target"]

        return Response(
            {
                "summary": {
                    "billed": billed,
                    "realized": realized,
                    "arrears": arrears,
                    "collection_rate": _percentage(realized, billed),
                    "revenue_records": records.count(),
                    "target_total": _sum(targets, "target_amount"),
                    "target_realized": _sum(targets, "realized_amount"),
                },
                "revenue_by_stream": _group_sum(
                    records,
                    "stream",
                    "currency",
                    amount_field="realized_amount",
                ),
                "billed_by_stream": _group_sum(
                    records,
                    "stream",
                    "currency",
                    amount_field="billed_amount",
                ),
                "revenue_by_school": _group_sum(
                    records,
                    "school_id",
                    "currency",
                    amount_field="realized_amount",
                ),
                "monthly_targets": monthly_targets,
                "monthly_revenue": list(
                    records.values(
                        "billing_date__year",
                        "billing_date__month",
                        "currency",
                    )
                    .annotate(
                        billed=Sum("billed_amount"),
                        realized=Sum("realized_amount"),
                    )
                    .order_by(
                        "billing_date__year",
                        "billing_date__month",
                    )
                ),
            }
        )


@extend_schema(
    tags=[LIABILITY_TAG],
    responses=FinanceDashboardResponseSerializer,
)
class LiabilityDashboardView(APIView):
    def get(self, request):
        today = _today()
        liabilities = _filters(
            _liabilities(),
            request.query_params,
            ("currency",),
        )
        due_soon = liabilities.filter(
            due_date__gte=today,
            due_date__lte=today + timedelta(days=30),
        )
        overdue = liabilities.filter(due_date__lt=today)

        return Response(
            {
                "summary": {
                    "total_outstanding": _sum(liabilities, "outstanding"),
                    "due_within_30_days": _sum(due_soon, "outstanding"),
                    "overdue": _sum(overdue, "outstanding"),
                    "liability_count": liabilities.count(),
                    "overdue_count": overdue.count(),
                },
                "by_category": _group_sum(
                    liabilities,
                    "category",
                    "currency",
                    amount_field="outstanding",
                ),
                "by_status": _group_sum(
                    liabilities,
                    "status",
                    "currency",
                    amount_field="outstanding",
                ),
                "top_creditors": list(
                    liabilities.values(
                        "creditor_id",
                        "creditor__name",
                        "currency",
                    )
                    .annotate(
                        outstanding=Sum("outstanding"),
                        liability_count=Count("id"),
                    )
                    .order_by("-outstanding")[:10]
                ),
                "as_of_date": str(today),
            }
        )


@extend_schema(
    tags=["Procurement"],
    responses=FinanceDashboardResponseSerializer,
)
class ProcurementDashboardView(APIView):
    def get(self, request):
        params = request.query_params

        transactions = ProcurementTransaction.objects.select_related(
            "vendor",
            "fiscal_year",
        )
        transactions = _date_filters(
            transactions,
            params,
            "transaction_date",
        )
        transactions = _filters(
            transactions,
            params,
            ("fiscal_year_id", "currency"),
        )

        paid = transactions.filter(status="paid")
        committed = transactions.filter(status="committed")
        outstanding = transactions.filter(status="outstanding")

        return Response(
            {
                "summary": {
                    "total_spend": _sum(transactions, "amount"),
                    "transaction_count": transactions.count(),
                    "paid": _sum(paid, "amount"),
                    "committed": _sum(committed, "amount"),
                    "outstanding": _sum(outstanding, "amount"),
                },
                "spend_by_category": _group_sum(
                    transactions,
                    "category",
                    "currency",
                ),
                "spend_by_status": _group_sum(
                    transactions,
                    "status",
                    "currency",
                ),
                "top_vendors": list(
                    transactions.values(
                        "vendor_id",
                        "vendor__name",
                        "currency",
                    )
                    .annotate(
                        total_spend=Sum("amount"),
                        transaction_count=Count("id"),
                    )
                    .order_by("-total_spend")[:10]
                ),
                "monthly_spending": list(
                    transactions.values(
                        "transaction_date__year",
                        "transaction_date__month",
                        "currency",
                    )
                    .annotate(
                        total=Sum("amount"),
                        transactions=Count("id"),
                    )
                    .order_by(
                        "transaction_date__year",
                        "transaction_date__month",
                    )
                ),
            }
        )
