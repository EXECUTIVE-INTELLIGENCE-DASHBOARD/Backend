"""Finance API views: CRUD endpoints and the executive dashboards."""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, F, Sum
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from academics.models import Enrolment, Term
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
    FinanceQuerySerializer,
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
PROCUREMENT_TAG = "Procurement"

ZERO = Decimal("0.00")

# (id, label, description, minimum days overdue, maximum days overdue)
AGEING_BUCKETS = [
    ("0-30", "0-30 days", "Recently overdue", 1, 30),
    ("31-60", "31-60 days", "Follow-up required", 31, 60),
    ("61-90", "61-90 days", "Priority follow-up", 61, 90),
    ("90-plus", "Over 90 days", "Long-outstanding balances", 91, None),
]

def _get_params(request):
    """Validate the query string and return the cleaned parameters."""
    query = FinanceQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    return query.validated_data


#  Helpers 


def _rate(part, whole):
    """Percentage rounded to one decimal place, or None when whole is zero."""
    return round(float(part) * 100 / float(whole), 1) if whole else None


def _sum(queryset, field):
    """Total of a money column, or zero when there are no rows."""
    return queryset.aggregate(total=Sum(field))["total"] or ZERO


def _filter(queryset, params, fields):
    """Keep only rows matching the filter parameters that were supplied."""
    for field in fields:
        if params.get(field):
            queryset = queryset.filter(**{field: params[field]})
    return queryset


def _in_period(queryset, date_field, params):
    """Keep only rows between start_date and end_date (both optional)."""
    if params.get("start_date"):
        queryset = queryset.filter(**{f"{date_field}__gte": params["start_date"]})
    if params.get("end_date"):
        queryset = queryset.filter(**{f"{date_field}__lte": params["end_date"]})
    return queryset


def _group_sum(queryset, *fields, amount="amount"):
    """Total and row count for each group, ready for a chart."""
    return list(
        queryset.values(*fields)
        .annotate(total=Sum(amount), records=Count("id"))
        .order_by(*fields)
    )


def _monthly(queryset, date_field, **totals):
    """Totals for each year, month and currency, oldest first."""
    year, month = f"{date_field}__year", f"{date_field}__month"
    return list(
        queryset.values(year, month, "currency")
        .annotate(**totals)
        .order_by(year, month)
    )


def _revenue(params):
    """Revenue records for the requested period, school, year and currency."""
    records = _in_period(RevenueRecord.objects.all(), "billing_date", params)
    return _filter(records, params, ["school_id", "fiscal_year_id", "currency"])


def _growth(params):
    """Realized revenue growth against the previous period of the same length."""
    start, end = params.get("start_date"), params.get("end_date")
    if not (start and end):
        return None

    previous_end = start - timedelta(days=1)
    previous_start = previous_end - (end - start)
    previous_params = {
        **params,
        "start_date": previous_start,
        "end_date": previous_end,
    }

    current = _sum(_revenue(params), "realized_amount")
    previous = _sum(_revenue(previous_params), "realized_amount")
    return _rate(current - previous, previous)


def _ageing(params):
    """Overdue fee balances grouped by how long they have been overdue."""
    today = timezone.localdate()
    unpaid = FeeInvoice.objects.exclude(
        status__in=[FeeInvoice.Status.PAID, FeeInvoice.Status.VOID]
    )
    unpaid = _filter(unpaid, params, ["school_id", "currency"])

    buckets = []
    for key, label, note, min_days, max_days in AGEING_BUCKETS:
        invoices = unpaid.filter(due_date__lte=today - timedelta(days=min_days))
        if max_days:
            invoices = invoices.filter(due_date__gte=today - timedelta(days=max_days))

        invoiced = _sum(invoices, "amount")
        paid = _sum(FeePayment.objects.filter(invoice__in=invoices), "amount")
        buckets.append(
            {
                "id": key,
                "period": label,
                "description": note,
                "amount": max(invoiced - paid, ZERO),
                "accounts": invoices.count(),
            }
        )
    return buckets


def _enrolment_by_school():
    """Active enrolment per school in the latest term that has started."""
    term = (
        Term.objects.filter(start_date__lte=timezone.localdate())
        .order_by("-start_date")
        .first()
    )
    if term is None:
        return {}

    rows = (
        Enrolment.objects.filter(term=term, status=Enrolment.Status.ACTIVE)
        .values("school_id")
        .annotate(n=Count("id"))
    )
    return {row["school_id"]: row["n"] for row in rows}


def _liabilities():
    """Liabilities that are not fully paid, with the unpaid amount as `balance`."""
    return Liability.objects.annotate(balance=F("amount") - F("paid_amount")).filter(
        balance__gt=ZERO
    )


# Budgets and expenses 


@extend_schema(tags=[BUDGET_TAG])
class FiscalYearViewSet(viewsets.ModelViewSet):
    serializer_class = FiscalYearSerializer
    queryset = FiscalYear.objects.all()


@extend_schema(tags=[BUDGET_TAG])
class DepartmentViewSet(viewsets.ModelViewSet):
    serializer_class = DepartmentSerializer
    queryset = Department.objects.all()


@extend_schema(tags=[BUDGET_TAG])
class DepartmentBudgetViewSet(viewsets.ModelViewSet):
    serializer_class = DepartmentBudgetSerializer
    queryset = DepartmentBudget.objects.select_related("department", "fiscal_year")


@extend_schema(tags=[BUDGET_TAG])
class MonthlyDepartmentBudgetViewSet(viewsets.ModelViewSet):
    serializer_class = MonthlyDepartmentBudgetSerializer
    queryset = MonthlyDepartmentBudget.objects.select_related(
        "department", "fiscal_year"
    )


@extend_schema(tags=[BUDGET_TAG])
class ExpenseTransactionViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseTransactionSerializer
    queryset = ExpenseTransaction.objects.select_related("department", "school")


@extend_schema(tags=[BUDGET_TAG])
class BankAccountViewSet(viewsets.ModelViewSet):
    serializer_class = BankAccountSerializer
    queryset = BankAccount.objects.select_related("school")


@extend_schema(tags=[BUDGET_TAG])
class CashMovementViewSet(viewsets.ModelViewSet):
    serializer_class = CashMovementSerializer
    queryset = CashMovement.objects.select_related("account")


@extend_schema(tags=[BUDGET_TAG])
class CashForecastViewSet(viewsets.ModelViewSet):
    serializer_class = CashForecastSerializer
    queryset = CashForecast.objects.select_related("school")


@extend_schema(tags=[BUDGET_TAG])
class ExpenseDashboardView(APIView):
    """Spending, budget usage and monthly trend. Defaults to this year so far."""

    @extend_schema(
        parameters=[FinanceQuerySerializer],
        responses=FinanceDashboardResponseSerializer,
    )
    def get(self, request):
        params = _get_params(request)
        today = timezone.localdate()
        start = params.get("start_date", today.replace(month=1, day=1))
        end = params.get("end_date", today)

        expenses = ExpenseTransaction.objects.filter(
            expense_date__gte=start, expense_date__lte=end
        )
        expenses = _filter(expenses, params, ["school_id", "department_id", "currency"])
        budgets = _filter(
            DepartmentBudget.objects.all(),
            params,
            ["department_id", "fiscal_year_id", "currency"],
        )

        total_spend = _sum(expenses, "amount")
        count = expenses.count()
        budget_total = _sum(budgets, "budget_amount")

        data = {
            "period": {"start_date": str(start), "end_date": str(end)},
            "summary": {
                "total_spend": total_spend,
                "transaction_count": count,
                "average_transaction": round(total_spend / count, 2) if count else ZERO,
                "budget_total": budget_total,
                "budget_remaining": budget_total - total_spend,
                "budget_used_percent": _rate(total_spend, budget_total),
                "over_budget": total_spend > budget_total,
            },
            "spending_by_category": _group_sum(expenses, "category", "currency"),
            "spending_by_department": _group_sum(
                expenses, "department__name", "currency"
            ),
            "department_budgets": _group_sum(
                budgets, "department__name", "currency", amount="budget_amount"
            ),
            "monthly_spending": _monthly(
                expenses, "expense_date", total=Sum("amount"), transactions=Count("id")
            ),
        }
        return Response(data)


# Liabilities and loans 


@extend_schema(tags=[LIABILITY_TAG])
class CreditorViewSet(viewsets.ModelViewSet):
    serializer_class = CreditorSerializer
    queryset = Creditor.objects.all()


@extend_schema(tags=[LIABILITY_TAG])
class LiabilityViewSet(viewsets.ModelViewSet):
    serializer_class = LiabilitySerializer
    queryset = Liability.objects.select_related("creditor")


@extend_schema(tags=[LIABILITY_TAG])
class LoanViewSet(viewsets.ModelViewSet):
    serializer_class = LoanSerializer
    queryset = Loan.objects.select_related("school", "creditor")


@extend_schema(tags=[LIABILITY_TAG])
class LoanRepaymentViewSet(viewsets.ModelViewSet):
    serializer_class = LoanRepaymentSerializer
    queryset = LoanRepayment.objects.select_related("loan")


@extend_schema(tags=[LIABILITY_TAG])
class LiabilityDashboardView(APIView):
    """Outstanding, due-soon and overdue liabilities."""

    @extend_schema(
        parameters=[FinanceQuerySerializer],
        responses=FinanceDashboardResponseSerializer,
    )
    def get(self, request):
        params = _get_params(request)
        today = timezone.localdate()

        liabilities = _filter(_liabilities(), params, ["currency"])
        due_soon = liabilities.filter(
            due_date__gte=today, due_date__lte=today + timedelta(days=30)
        )
        overdue = liabilities.filter(due_date__lt=today)

        top_creditors = (
            liabilities.values("creditor_id", "creditor__name", "currency")
            .annotate(outstanding=Sum("balance"), liability_count=Count("id"))
            .order_by("-outstanding")[:10]
        )

        data = {
            "summary": {
                "total_outstanding": _sum(liabilities, "balance"),
                "due_within_30_days": _sum(due_soon, "balance"),
                "overdue": _sum(overdue, "balance"),
                "liability_count": liabilities.count(),
                "overdue_count": overdue.count(),
            },
            "by_category": _group_sum(
                liabilities, "category", "currency", amount="balance"
            ),
            "by_status": _group_sum(liabilities, "status", "currency", amount="balance"),
            "top_creditors": list(top_creditors),
            "as_of_date": str(today),
        }
        return Response(data)


# Revenue 


@extend_schema(tags=[REVENUE_TAG])
class RevenueRecordViewSet(viewsets.ModelViewSet):
    serializer_class = RevenueRecordSerializer
    queryset = RevenueRecord.objects.select_related("fiscal_year", "school")


@extend_schema(tags=[REVENUE_TAG])
class MonthlyRevenueTargetViewSet(viewsets.ModelViewSet):
    serializer_class = MonthlyRevenueTargetSerializer
    queryset = MonthlyRevenueTarget.objects.select_related("fiscal_year", "school")


@extend_schema(tags=[REVENUE_TAG])
class FeeInvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = FeeInvoiceSerializer
    queryset = FeeInvoice.objects.select_related("school", "fiscal_year")


@extend_schema(tags=[REVENUE_TAG])
class FeePaymentViewSet(viewsets.ModelViewSet):
    serializer_class = FeePaymentSerializer
    queryset = FeePayment.objects.select_related("invoice")


@extend_schema(tags=[REVENUE_TAG])
class RevenueDashboardView(APIView):
    """Billing, collections, arrears, campus table, ageing and growth."""

    @extend_schema(
        parameters=[FinanceQuerySerializer],
        responses=FinanceDashboardResponseSerializer,
    )
    def get(self, request):
        params = _get_params(request)

        records = _revenue(params)
        targets = _filter(
            MonthlyRevenueTarget.objects.all(),
            params,
            ["school_id", "fiscal_year_id", "currency"],
        )

        billed = _sum(records, "billed_amount")
        realized = _sum(records, "realized_amount")

        # Monthly targets against what was collected.
        monthly_targets = _monthly_targets(targets)

        # One row per campus, with its active enrolment.
        enrolment = _enrolment_by_school()
        campuses = list(
            records.filter(school__isnull=False)
            .values("school_id", "school__name", "currency")
            .annotate(billed=Sum("billed_amount"), realized=Sum("realized_amount"))
            .order_by("school__name")
        )
        for campus in campuses:
            campus["enrolment"] = enrolment.get(campus["school_id"], 0)

        data = {
            "summary": {
                "billed": billed,
                "realized": realized,
                "arrears": max(billed - realized, ZERO),
                "collection_rate": _rate(realized, billed),
                "revenue_records": records.count(),
                "target_total": _sum(targets, "target_amount"),
                "target_realized": _sum(targets, "realized_amount"),
            },
            "revenue_by_stream": _group_sum(
                records, "stream", "currency", amount="realized_amount"
            ),
            "billed_by_stream": _group_sum(
                records, "stream", "currency", amount="billed_amount"
            ),
            "campuses": campuses,
            "ageing": _ageing(params),
            "growth_percent": _growth(params),
            "monthly_targets": monthly_targets,
            "monthly_revenue": _monthly(
                records,
                "billing_date",
                billed=Sum("billed_amount"),
                realized=Sum("realized_amount"),
            ),
        }
        return Response(data)


def _monthly_targets(targets):
    """Target, collected amount, achievement and variance for each month."""
    rows = list(
        targets.values("month", "currency")
        .annotate(target=Sum("target_amount"), realized=Sum("realized_amount"))
        .order_by("month")
    )
    for row in rows:
        row["realized"] = row["realized"] or ZERO
        row["achievement_percent"] = _rate(row["realized"], row["target"])
        row["variance"] = row["realized"] - row["target"]
    return rows


# Procurement


@extend_schema(tags=[PROCUREMENT_TAG])
class ProcurementDashboardView(APIView):
    """Procurement spend by status, category, vendor and month."""

    @extend_schema(
        parameters=[FinanceQuerySerializer],
        responses=FinanceDashboardResponseSerializer,
    )
    def get(self, request):
        params = _get_params(request)

        transactions = _in_period(
            ProcurementTransaction.objects.all(), "transaction_date", params
        )
        transactions = _filter(transactions, params, ["fiscal_year_id", "currency"])

        top_vendors = (
            transactions.values("vendor_id", "vendor__name", "currency")
            .annotate(total_spend=Sum("amount"), transaction_count=Count("id"))
            .order_by("-total_spend")[:10]
        )

        data = {
            "summary": {
                "total_spend": _sum(transactions, "amount"),
                "transaction_count": transactions.count(),
                "paid": _sum(transactions.filter(status="paid"), "amount"),
                "committed": _sum(transactions.filter(status="committed"), "amount"),
                "outstanding": _sum(transactions.filter(status="outstanding"), "amount"),
            },
            "spend_by_category": _group_sum(transactions, "category", "currency"),
            "spend_by_status": _group_sum(transactions, "status", "currency"),
            "top_vendors": list(top_vendors),
            "monthly_spending": _monthly(
                transactions,
                "transaction_date",
                total=Sum("amount"),
                transactions=Count("id"),
            ),
        }
        return Response(data)