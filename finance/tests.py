
# Create your tests here.

"""Tests for the four executive finance dashboards."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from finance.models import (
    Creditor,
    Department,
    ExpenseTransaction,
    FiscalYear,
    Liability,
    MonthlyRevenueTarget,
    RevenueRecord,
)
from procurement.models import ProcurementTransaction, Vendor

LIABILITY_URL = "/api/finance/liability/dashboard/"
REVENUE_URL = "/api/finance/revenue/dashboard/"
PROCUREMENT_URL = "/api/finance/procurement/dashboard/"
EXPENSE_URL = "/api/finance/expense/dashboard/"


@pytest.fixture
def client():
    # Use this client to send requests to our API endpoints.
    return APIClient()


@pytest.fixture
def setup():
    # Create shared records that the dashboard tests can use.
    fiscal_year = FiscalYear.objects.create(year="2026-2027", quarter=1)
    department = Department.objects.create(name="Administration")
    creditor = Creditor.objects.create(
        name="Office Supplies Ltd",
        reference_number="CR-001",
        creditor_type="trade_payable",
    )

    return {
        "fiscal_year": fiscal_year,
        "department": department,
        "creditor": creditor,
    }


def create_expense(
        department, reference, amount, expense_date=None, category="utilities_maintenance"):
    # Create an expense using the details supplied by each test.
    return ExpenseTransaction.objects.create(
        department=department,
        category=category,
        expense_date=expense_date or date(2026, 10, 10),
        description=f"Test expense {reference}",
        reference_number=reference,
        amount=Decimal(str(amount)),
        currency="UGX",
    )


def create_revenue(fiscal_year, billed, realized, stream="tuition", billing_date=None):
    # Create a revenue record with the amount billed and collected.
    return RevenueRecord.objects.create(
        fiscal_year=fiscal_year,
        stream=stream,
        billed_amount=Decimal(str(billed)),
        realized_amount=Decimal(str(realized)),
        currency="UGX",
        billing_date=billing_date or date(2026, 10, 1),
    )


# Liability management dashboard tests.

@pytest.mark.django_db
def test_liability_dashboard_returns_expected_sections(client):
    # Make sure the dashboard returns the sections defined in the view.
    response = client.get(LIABILITY_URL)

    assert response.status_code == 200
    body = response.json()

    assert "summary" in body
    assert "by_category" in body
    assert "by_status" in body
    assert "top_creditors" in body
    assert "as_of_date" in body

    assert "total_outstanding" in body["summary"]
    assert "due_within_30_days" in body["summary"]
    assert "overdue" in body["summary"]
    assert "liability_count" in body["summary"]
    assert "overdue_count" in body["summary"]


@pytest.mark.django_db
def test_liability_dashboard_calculates_outstanding(client, setup):
    # Check that the dashboard subtracts payments already made.
    today = date.today()

    Liability.objects.create(
        creditor=setup["creditor"],
        category="current_payables",
        status="current",
        amount=Decimal("100000.00"),
        paid_amount=Decimal("25000.00"),
        currency="UGX",
        issued_date=today - timedelta(days=10),
        due_date=today + timedelta(days=10),
        description="Partially paid supplier invoice",
    )

    body = client.get(LIABILITY_URL, {"currency": "UGX"}).json()

    assert body["summary"]["total_outstanding"] == 75000
    assert body["summary"]["due_within_30_days"] == 75000
    assert body["summary"]["liability_count"] == 1
    assert body["summary"]["overdue_count"] == 0
    assert body["top_creditors"][0]["creditor__name"] == "Office Supplies Ltd"


@pytest.mark.django_db
def test_liability_dashboard_calculates_overdue_amount(client, setup):
    # Check that unpaid amounts past their due date count as overdue.
    today = date.today()

    Liability.objects.create(
        creditor=setup["creditor"],
        category="current_payables",
        status="overdue",
        amount=Decimal("90000.00"),
        paid_amount=Decimal("20000.00"),
        currency="UGX",
        issued_date=today - timedelta(days=60),
        due_date=today - timedelta(days=10),
        description="Overdue supplier invoice",
    )

    body = client.get(LIABILITY_URL, {"currency": "UGX"}).json()

    assert body["summary"]["overdue"] == 70000
    assert body["summary"]["overdue_count"] == 1


# Revenue dashboard tests.

@pytest.mark.django_db
def test_revenue_dashboard_returns_expected_sections(client):
    # Check that all revenue dashboard sections are present.
    response = client.get(REVENUE_URL)

    assert response.status_code == 200
    body = response.json()

    assert "summary" in body
    assert "revenue_by_stream" in body
    assert "billed_by_stream" in body
    assert "revenue_by_school" in body
    assert "monthly_targets" in body
    assert "monthly_revenue" in body

    assert "billed" in body["summary"]
    assert "realized" in body["summary"]
    assert "arrears" in body["summary"]
    assert "collection_rate" in body["summary"]
    assert "revenue_records" in body["summary"]
    assert "target_total" in body["summary"]
    assert "target_realized" in body["summary"]


@pytest.mark.django_db
def test_revenue_dashboard_calculates_collection_rate(client, setup):
    # Check that the dashboard calculates collections against billed revenue.
    create_revenue(setup["fiscal_year"], 500000, 400000, "tuition")
    create_revenue(setup["fiscal_year"], 300000, 200000, "transport")

    body = client.get(REVENUE_URL, {"currency": "UGX"}).json()

    assert body["summary"]["billed"] == 800000
    assert body["summary"]["realized"] == 600000
    assert body["summary"]["arrears"] == 200000
    assert body["summary"]["collection_rate"] == 75.0
    assert body["summary"]["revenue_records"] == 2
    assert len(body["revenue_by_stream"]) == 2


@pytest.mark.django_db
def test_revenue_dashboard_calculates_monthly_targets(client, setup):
    # Check whether the dashboard reports target achievement correctly.
    MonthlyRevenueTarget.objects.create(
        fiscal_year=setup["fiscal_year"],
        month=date(2026, 10, 1),
        target_amount=Decimal("700000.00"),
        realized_amount=Decimal("600000.00"),
        currency="UGX",
    )

    body = client.get(REVENUE_URL, {"currency": "UGX"}).json()

    assert len(body["monthly_targets"]) == 1

    target = body["monthly_targets"][0]

    assert target["target"] == 700000
    assert target["realized"] == 600000
    assert target["achievement_percent"] == pytest.approx(85.71)
    assert target["variance"] == -100000
    assert body["summary"]["target_total"] == 700000
    assert body["summary"]["target_realized"] == 600000


@pytest.mark.django_db
def test_revenue_dashboard_filters_by_billing_date(client, setup):
    # Check that records outside the selected billing period are excluded.
    create_revenue(
        setup["fiscal_year"],
        500000,
        400000,
        billing_date=date(2026, 9, 1),
    )
    create_revenue(
        setup["fiscal_year"],
        300000,
        200000,
        billing_date=date(2026, 10, 1),
    )

    body = client.get(
        REVENUE_URL,
        {"start_date": "2026-10-01", "end_date": "2026-10-31"},
    ).json()

    assert body["summary"]["billed"] == 300000
    assert body["summary"]["realized"] == 200000
    assert body["summary"]["revenue_records"] == 1


# Procurement financials dashboard tests.

@pytest.mark.django_db
def test_procurement_dashboard_returns_expected_sections(client):
    # Check that the response matches the procurement dashboard view.
    response = client.get(PROCUREMENT_URL)

    assert response.status_code == 200
    body = response.json()

    assert "summary" in body
    assert "spend_by_category" in body
    assert "spend_by_status" in body
    assert "top_vendors" in body
    assert "monthly_spending" in body

    assert "total_spend" in body["summary"]
    assert "transaction_count" in body["summary"]
    assert "paid" in body["summary"]
    assert "committed" in body["summary"]
    assert "outstanding" in body["summary"]


@pytest.mark.django_db
def test_procurement_dashboard_calculates_spending(client, setup):
    # Check total spending and the amounts in each payment status.
    vendor = Vendor.objects.create(
        name="Green Supplies Ltd",
        primary_category="goods",
    )

    transactions = [
        ("goods", "paid", "100000.00", "PROC-001"),
        ("services", "committed", "50000.00", "PROC-002"),
        ("works", "outstanding", "25000.00", "PROC-003"),
    ]

    for category, status, amount, reference in transactions:
        ProcurementTransaction.objects.create(
            vendor=vendor,
            fiscal_year=setup["fiscal_year"],
            category=category,
            status=status,
            amount=Decimal(amount),
            currency="UGX",
            transaction_date=date(2026, 10, 5),
            reference_number=reference,
            description="Test procurement transaction",
        )

    body = client.get(PROCUREMENT_URL, {"currency": "UGX"}).json()

    assert body["summary"]["total_spend"] == 175000
    assert body["summary"]["transaction_count"] == 3
    assert body["summary"]["paid"] == 100000
    assert body["summary"]["committed"] == 50000
    assert body["summary"]["outstanding"] == 25000
    assert len(body["spend_by_category"]) == 3
    assert len(body["spend_by_status"]) == 3
    assert body["top_vendors"][0]["vendor__name"] == "Green Supplies Ltd"
    assert body["top_vendors"][0]["total_spend"] == 175000


@pytest.mark.django_db
def test_procurement_dashboard_filters_by_transaction_date(client, setup):
    # Check that only transactions within the selected dates are counted.
    vendor = Vendor.objects.create(
        name="Green Supplies Ltd",
        primary_category="goods",
    )

    for reference, amount, transaction_date in [
        ("PROC-004", "100000.00", date(2026, 9, 5)),
        ("PROC-005", "50000.00", date(2026, 10, 5)),
    ]:
        ProcurementTransaction.objects.create(
            vendor=vendor,
            fiscal_year=setup["fiscal_year"],
            category="goods",
            status="paid",
            amount=Decimal(amount),
            currency="UGX",
            transaction_date=transaction_date,
            reference_number=reference,
            description="Test procurement transaction",
        )

    body = client.get(
        PROCUREMENT_URL,
        {"start_date": "2026-10-01", "end_date": "2026-10-31"},
    ).json()

    assert body["summary"]["total_spend"] == 50000
    assert body["summary"]["transaction_count"] == 1


# Expense management dashboard tests.

@pytest.mark.django_db
def test_expense_dashboard_returns_expected_sections(client):
    # Check that all expense dashboard response sections are present.
    response = client.get(EXPENSE_URL)

    assert response.status_code == 200
    body = response.json()

    assert "period" in body
    assert "summary" in body
    assert "spending_by_category" in body
    assert "spending_by_department" in body
    assert "department_budgets" in body
    assert "monthly_spending" in body

    assert "total_spend" in body["summary"]
    assert "transaction_count" in body["summary"]
    assert "average_transaction" in body["summary"]
    assert "budget_total" in body["summary"]
    assert "budget_remaining" in body["summary"]
    assert "budget_used_percent" in body["summary"]
    assert "over_budget" in body["summary"]


@pytest.mark.django_db
def test_expense_dashboard_calculates_total_spending(client, setup):
    # Check the total, average transaction amount, and spending groups.
    create_expense(setup["department"], "EXP-001", 100000, category="salaries")
    create_expense(setup["department"], "EXP-002", 50000, category="utilities_maintenance")

    body = client.get(EXPENSE_URL, {"currency": "UGX"}).json()

    assert body["summary"]["total_spend"] == 150000
    assert body["summary"]["transaction_count"] == 2
    assert body["summary"]["average_transaction"] == 75000
    assert len(body["spending_by_category"]) == 2
    assert len(body["spending_by_department"]) == 1
    assert body["spending_by_department"][0]["total"] == 150000


@pytest.mark.django_db
def test_expense_dashboard_filters_by_department(client, setup):
    # Check that selecting a department excludes other departments' expenses.
    other_department = Department.objects.create(name="Transport")

    create_expense(setup["department"], "EXP-003", 100000)
    create_expense(other_department, "EXP-004", 50000)

    body = client.get(
        EXPENSE_URL,
        {"department_id": setup["department"].pk, "currency": "UGX"},
    ).json()

    assert body["summary"]["total_spend"] == 100000
    assert body["summary"]["transaction_count"] == 1


@pytest.mark.django_db
def test_expense_dashboard_filters_by_date(client, setup):
    # Check that expenses outside the selected dates are not included.
    create_expense(
        setup["department"],
        "EXP-005",
        80000,
        expense_date=date(2026, 9, 10),
    )
    create_expense(
        setup["department"],
        "EXP-006",
        40000,
        expense_date=date(2026, 10, 10),
    )

    body = client.get(
        EXPENSE_URL,
        {"start_date": "2026-10-01", "end_date": "2026-10-31"},
    ).json()

    assert body["summary"]["total_spend"] == 40000
    assert body["summary"]["transaction_count"] == 1
