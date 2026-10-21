from datetime import date
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DailySales, Outlet, OutletBudget, OutletExpense, StockItem
from .serializers import (
    BudgetDashboardQuerySerializer,
    BudgetDashboardSerializer,
    DailySalesSerializer,
    InventoryDashboardQuerySerializer,
    InventoryDashboardSerializer,
    OutletBudgetSerializer,
    OutletExpenseSerializer,
    OutletSerializer,
    SalesDashboardQuerySerializer,
    SalesDashboardSerializer,
    StockItemSerializer,
)

SALES_TAG = "Services - Sales"
INVENTORY_TAG = "Services - Inventory"
BUDGET_TAG = "Services - Budget Utilisation"
# An outlet is overspending when its budget is being used more than 10% faster than
# the year is passing (e.g. 89% used when 79% of the year has gone).
OVERSPEND_PACE = 1.10
ZERO = Decimal("0.00")


def _rate(part, whole):
    """Percentage rounded to one decimal place, or None when there is nothing to measure."""
    return round(float(part) * 100 / float(whole), 1) if whole else None


def _filter(queryset, params, *fields):
    """Apply simple equality filters from the query string."""
    for field in fields:
        if params.get(field):
            queryset = queryset.filter(**{field: params[field]})
    return queryset


def _dated(queryset, params):
    if params.get("start"):
        queryset = queryset.filter(date__gte=params["start"])
    if params.get("end"):
        queryset = queryset.filter(date__lte=params["end"])
    return queryset


@extend_schema(tags=[SALES_TAG])
class OutletViewSet(viewsets.ModelViewSet):
    serializer_class = OutletSerializer
    queryset = Outlet.objects.all()

    def get_queryset(self):
        return _filter(super().get_queryset(), self.request.query_params, "business_type")


@extend_schema(tags=[SALES_TAG])
class DailySalesViewSet(viewsets.ModelViewSet):
    serializer_class = DailySalesSerializer
    queryset = DailySales.objects.select_related("outlet")

    def get_queryset(self):
        params = self.request.query_params
        return _dated(_filter(super().get_queryset(), params, "outlet"), params)


@extend_schema(tags=[INVENTORY_TAG])
class StockItemViewSet(viewsets.ModelViewSet):
    serializer_class = StockItemSerializer
    queryset = StockItem.objects.select_related("outlet")

    def get_queryset(self):
        return _filter(super().get_queryset(), self.request.query_params, "outlet")


@extend_schema(tags=[BUDGET_TAG])
class OutletBudgetViewSet(viewsets.ModelViewSet):
    serializer_class = OutletBudgetSerializer
    queryset = OutletBudget.objects.select_related("outlet")

    def get_queryset(self):
        return _filter(
            super().get_queryset(), self.request.query_params, "outlet", "financial_year"
        )


@extend_schema(tags=[BUDGET_TAG])
class OutletExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = OutletExpenseSerializer
    queryset = OutletExpense.objects.select_related("outlet")

    def get_queryset(self):
        params = self.request.query_params
        return _dated(_filter(super().get_queryset(), params, "outlet"), params)


@extend_schema(tags=[SALES_TAG])
class SalesDashboardView(APIView):
    """Sales screen: total sales, gross profit and transactions, the monthly trend, and
    sales by outlet. Defaults to the year so far."""

    @extend_schema(parameters=[SalesDashboardQuerySerializer], responses=SalesDashboardSerializer)
    def get(self, request):
        query = SalesDashboardQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        end = params.get("end") or timezone.localdate()
        start = params.get("start") or date(end.year, 1, 1)

        sales = DailySales.objects.filter(date__range=(start, end))
        outlets = Outlet.objects.all()
        if params.get("outlet"):
            sales = sales.filter(outlet_id=params["outlet"])
            outlets = outlets.filter(pk=params["outlet"])

        totals = sales.aggregate(
            revenue=Sum("revenue"), cost=Sum("cost_of_sales"), transactions=Sum("transactions")
        )
        revenue = totals["revenue"] or ZERO
        profit = revenue - (totals["cost"] or ZERO)
        transactions = totals["transactions"] or 0

        trend = [
            {"month": row["month"].strftime("%Y-%m"), "label": row["month"].strftime("%b"),
             "revenue": row["revenue"]}
            for row in sales.annotate(month=TruncMonth("date")).values("month")
            .annotate(revenue=Sum("revenue")).order_by("month")
        ]

        in_period = Q(daily_sales__date__range=(start, end))
        rows = []
        for outlet in outlets.annotate(
            revenue=Sum("daily_sales__revenue", filter=in_period),
            cost=Sum("daily_sales__cost_of_sales", filter=in_period),
            transactions=Sum("daily_sales__transactions", filter=in_period),
        ).order_by("name"):
            outlet_revenue = outlet.revenue or ZERO
            outlet_transactions = outlet.transactions or 0
            rows.append({
                "id": outlet.pk, "name": outlet.name, "business_type": outlet.business_type,
                "business_type_display": outlet.get_business_type_display(),
                "revenue": outlet_revenue,
                "gross_margin": _rate(outlet_revenue - (outlet.cost or ZERO), outlet_revenue),
                "transactions": outlet_transactions,
                "average_sale": (outlet_revenue / outlet_transactions).quantize(ZERO)
                if outlet_transactions else None,
            })

        data = {
            "start": start,
            "end": end,
            "summary": {
                "total_sales": revenue,
                "gross_profit": profit,
                "gross_margin": _rate(profit, revenue),
                "transactions": transactions,
                "average_sale": (revenue / transactions).quantize(ZERO) if transactions else None,
            },
            "monthly_trend": trend,
            "outlets": rows,
        }
        return Response(SalesDashboardSerializer(data).data)


@extend_schema(tags=[INVENTORY_TAG])
class InventoryDashboardView(APIView):
    """Inventory screen: stock value, items below their minimum level, and every item with
    its status (critical below half the minimum, reorder soon below the minimum)."""

    @extend_schema(
        parameters=[InventoryDashboardQuerySerializer], responses=InventoryDashboardSerializer
    )
    def get(self, request):
        query = InventoryDashboardQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data

        items = StockItem.objects.select_related("outlet").order_by("outlet__name", "name")
        if params.get("outlet"):
            items = items.filter(outlet_id=params["outlet"])
        value = ExpressionWrapper(
            F("on_hand") * F("unit_cost"),
            output_field=DecimalField(max_digits=16, decimal_places=2),
        )
        totals = items.aggregate(
            stock_value=Sum(value),
            below_minimum=Count("id", filter=Q(on_hand__lt=F("minimum_level"))),
            outlets=Count("outlet", distinct=True),
        )
        rows = list(items)
        critical = sum(1 for item in rows if item.status == StockItem.Status.CRITICAL)
        if params.get("status"):
            rows = [item for item in rows if item.status == params["status"]]

        data = {
            "summary": {
                "stock_value": totals["stock_value"] or ZERO,
                "below_minimum": totals["below_minimum"],
                "critical": critical,
                "outlets": totals["outlets"],
            },
            "items": rows,
        }
        return Response(InventoryDashboardSerializer(data).data)


@extend_schema(tags=[BUDGET_TAG])
class BudgetDashboardView(APIView):
    """Budget Utilisation screen: each outlet's budget used so far against how much of the
    financial year (January to December) has passed."""

    STATUS_LABELS = {
        "on_track": "On track",
        "slightly_ahead": "Slightly ahead",
        "overspending": "Overspending",
    }

    @extend_schema(parameters=[BudgetDashboardQuerySerializer], responses=BudgetDashboardSerializer)
    def get(self, request):
        query = BudgetDashboardQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        as_of = params.get("as_of") or timezone.localdate()
        year_start, year_end = date(as_of.year, 1, 1), date(as_of.year, 12, 31)
        time_elapsed = ((as_of - year_start).days + 1) * 100 / ((year_end - year_start).days + 1)

        budgets = OutletBudget.objects.filter(financial_year=as_of.year).select_related("outlet")
        if params.get("outlet"):
            budgets = budgets.filter(outlet_id=params["outlet"])
        spent_by_outlet = dict(
            OutletExpense.objects.filter(date__range=(year_start, as_of))
            .values_list("outlet").annotate(total=Sum("amount"))
        )

        rows, allocated_total, spent_total = [], ZERO, ZERO
        for budget in budgets.order_by("outlet__name"):
            spent = spent_by_outlet.get(budget.outlet_id, ZERO)
            used = _rate(spent, budget.allocated)
            pace = (used or 0) / time_elapsed
            status = ("overspending" if pace > OVERSPEND_PACE
                      else "slightly_ahead" if pace > 1 else "on_track")
            rows.append({
                "id": budget.outlet_id, "name": budget.outlet.name,
                "business_type_display": budget.outlet.get_business_type_display(),
                "allocated": budget.allocated, "spent": spent, "used": used,
                "status": status, "status_display": self.STATUS_LABELS[status],
            })
            allocated_total += budget.allocated
            spent_total += spent

        data = {
            "financial_year": as_of.year,
            "as_of": as_of,
            "summary": {
                "operating_budget": allocated_total,
                "spent": spent_total,
                "budget_used": _rate(spent_total, allocated_total),
                "time_elapsed": round(time_elapsed, 1),
            },
            "outlets": rows,
        }
        return Response(BudgetDashboardSerializer(data).data)
