from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from .models import DailySales, Outlet, OutletBudget, OutletExpense, StockItem

SALES_URL = "/api/services/sales/dashboard/"
INVENTORY_URL = "/api/services/inventory/dashboard/"
BUDGET_URL = "/api/services/budget/dashboard/"
M = 1_000_000

# name, code, business type, revenue (M), margin %, transactions, allocated (M), spent (M)
OUTLETS = [
    ("Shop A", "shop-a", "uniform_shop", 148, 34, 2900, 120, 102),
    ("Shop B", "shop-b", "uniform_shop", 96, 31, 11200, 80, 58),
    ("Shop C", "shop-c", "uniform_shop", 74, 29, 8400, 62, 49),
    ("Shop D", "shop-d", "uniform_shop", 68, 28, 7600, 58, 52),
    ("Café", "cafe", "cafe", 132, 42, 24000, 110, 98),
    ("Minimart", "minimart", "minimart", 163, 24, 38000, 140, 121),
]
# item, outlet code, on hand, minimum level, unit cost
STOCK = [
    ("Boys' shirt (M)", "shop-a", 64, 80, 28000),
    ("Girls' skirt (L)", "shop-a", 12, 40, 32000),
    ("School sweater", "shop-a", 55, 50, 45000),
    ("School socks (pair)", "shop-b", 900, 500, 1800),
    ("Sports T-shirt", "shop-b", 18, 30, 22000),
    ("School tie", "shop-c", 60, 40, 9500),
    ("Tracksuit", "shop-d", 22, 30, 34000),
    ("Coffee beans (1kg)", "cafe", 14, 10, 48000),
    ("Fresh milk (1L)", "cafe", 20, 60, 3200),
    ("Bottled water (24 pack)", "minimart", 35, 50, 17000),
    ("Sugar (1kg)", "minimart", 210, 150, 4800),
    ("Bread loaf", "minimart", 25, 40, 4500),
    ("Exercise books (96pg)", "minimart", 900, 500, 1800),
    ("Pens (box of 50)", "minimart", 18, 30, 22000),
    ("Toiletry pack", "minimart", 60, 40, 9500),
    ("Snacks carton", "minimart", 22, 30, 34000),
]


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def screens():
    """The figures shown on the Sales, Inventory and Budget Utilisation screens."""
    outlets = {}
    for name, code, kind, revenue, margin, transactions, allocated, spent in OUTLETS:
        outlet = Outlet.objects.create(code=code, name=name, business_type=kind)
        outlets[code] = outlet
        DailySales.objects.create(
            outlet=outlet, date=date(2026, 6, 15), revenue=revenue * M,
            cost_of_sales=Decimal(revenue * M) * (100 - margin) / 100, transactions=transactions,
        )
        OutletBudget.objects.create(outlet=outlet, financial_year=2026, allocated=allocated * M)
        OutletExpense.objects.create(outlet=outlet, date=date(2026, 9, 30), amount=spent * M)
    for name, code, on_hand, minimum, cost in STOCK:
        StockItem.objects.create(
            outlet=outlets[code], name=name, on_hand=on_hand, minimum_level=minimum, unit_cost=cost
        )
    return outlets


# --- Sales --------------------------------------------------------------------------

@pytest.mark.django_db
def test_sales_summary_matches_the_screen(client, screens):
    body = client.get(SALES_URL, {"start": "2026-02-01", "end": "2026-10-17"}).json()

    assert body["summary"] == {
        "total_sales": "681000000.00",
        "gross_profit": "215140000.00",
        "gross_margin": 31.6,
        "transactions": 92100,
        "average_sale": "7394.14",
    }


@pytest.mark.django_db
def test_sales_by_outlet_matches_the_screen(client, screens):
    body = client.get(SALES_URL, {"start": "2026-02-01", "end": "2026-10-17"}).json()

    rows = {row["name"]: row for row in body["outlets"]}
    assert rows["Shop A"]["revenue"] == "148000000.00"
    assert rows["Shop A"]["gross_margin"] == 34.0
    assert rows["Shop A"]["average_sale"] == "51034.48"
    assert rows["Shop B"]["business_type_display"] == "Uniform shop"
    assert rows["Minimart"]["transactions"] == 38000


@pytest.mark.django_db
def test_sales_monthly_trend_and_outlet_filter(client, screens):
    shop_a = screens["shop-a"]
    DailySales.objects.create(outlet=shop_a, date=date(2026, 2, 3), revenue=2 * M,
                              cost_of_sales=M, transactions=40)
    DailySales.objects.create(outlet=shop_a, date=date(2026, 2, 4), revenue=3 * M,
                              cost_of_sales=M, transactions=60)

    body = client.get(SALES_URL, {"start": "2026-02-01", "end": "2026-10-17",
                                  "outlet": shop_a.pk}).json()

    assert body["monthly_trend"] == [
        {"month": "2026-02", "label": "Feb", "revenue": "5000000.00"},
        {"month": "2026-06", "label": "Jun", "revenue": "148000000.00"},
    ]
    assert [row["name"] for row in body["outlets"]] == ["Shop A"]
    assert body["summary"]["transactions"] == 3000


@pytest.mark.django_db
def test_sales_outside_the_period_are_left_out(client, screens):
    body = client.get(SALES_URL, {"start": "2026-07-01", "end": "2026-10-17"}).json()

    assert body["summary"]["total_sales"] == "0.00"
    assert body["summary"]["average_sale"] is None


@pytest.mark.django_db
def test_sales_rejects_start_after_end(client):
    assert client.get(SALES_URL, {"start": "2026-10-17", "end": "2026-02-01"}).status_code == 400


# --- Inventory ----------------------------------------------------------------------

@pytest.mark.django_db
def test_inventory_summary(client, screens):
    body = client.get(INVENTORY_URL).json()

    assert body["summary"] == {
        "stock_value": "13770500.00", "below_minimum": 9, "critical": 2, "outlets": 6,
    }
    assert len(body["items"]) == 16


@pytest.mark.django_db
def test_inventory_statuses_match_the_screen(client, screens):
    items = {item["name"]: item for item in client.get(INVENTORY_URL).json()["items"]}

    assert items["Girls' skirt (L)"]["status_display"] == "Critical"  # 12 of 40
    assert items["Boys' shirt (M)"]["status_display"] == "Reorder soon"  # 64 of 80
    assert items["School sweater"]["status_display"] == "In stock"  # 55 of 50
    assert items["Fresh milk (1L)"]["stock_value"] == "64000.00"


@pytest.mark.django_db
def test_inventory_filters_by_outlet_and_status(client, screens):
    by_outlet = client.get(INVENTORY_URL, {"outlet": screens["cafe"].pk}).json()
    critical = client.get(INVENTORY_URL, {"status": "critical"}).json()

    assert [item["name"] for item in by_outlet["items"]] == ["Coffee beans (1kg)",
                                                             "Fresh milk (1L)"]
    assert by_outlet["summary"]["outlets"] == 1
    assert {item["name"] for item in critical["items"]} == {"Girls' skirt (L)", "Fresh milk (1L)"}


# --- Budget utilisation -------------------------------------------------------------

@pytest.mark.django_db
def test_budget_summary_matches_the_screen(client, screens):
    body = client.get(BUDGET_URL, {"as_of": "2026-10-17"}).json()

    assert body["financial_year"] == 2026
    assert body["summary"] == {
        "operating_budget": "570000000.00",
        "spent": "480000000.00",
        "budget_used": 84.2,
        "time_elapsed": 79.5,  # 290 of 365 days
    }


@pytest.mark.django_db
def test_budget_statuses_match_the_screen(client, screens):
    rows = {row["name"]: row for row in client.get(BUDGET_URL, {"as_of": "2026-10-17"}).json()
            ["outlets"]}

    assert {name: row["status_display"] for name, row in rows.items()} == {
        "Shop A": "Slightly ahead", "Shop B": "On track", "Shop C": "On track",
        "Shop D": "Overspending", "Café": "Overspending", "Minimart": "Slightly ahead",
    }
    assert rows["Shop D"]["used"] == 89.7


@pytest.mark.django_db
def test_budget_counts_only_this_years_spending_up_to_the_date(client, screens):
    shop_b = screens["shop-b"]
    OutletExpense.objects.create(outlet=shop_b, date=date(2025, 12, 20), amount=50 * M)
    OutletExpense.objects.create(outlet=shop_b, date=date(2026, 11, 2), amount=50 * M)

    rows = {row["name"]: row for row in client.get(BUDGET_URL, {"as_of": "2026-10-17"}).json()
            ["outlets"]}

    assert rows["Shop B"]["spent"] == "58000000.00"
