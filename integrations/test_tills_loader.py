from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from services.models import DailySales, Outlet, OutletBudget, OutletExpense, StockItem

from .connectors.tills import MockTillConnector
from .loaders.tills import load_tills
from .models import ImportRun, StagedRecord
from .pipeline import run_sync
from .sources import all_sources

PERIOD = {"start": "2026-02-01", "end": "2026-10-17"}
MODELS = (Outlet, DailySales, StockItem, OutletBudget, OutletExpense)


def sync():
    return run_sync(MockTillConnector(), load_tills, "Outlet Tills & Stock")


def test_the_tills_source_is_registered():
    assert "tills" in all_sources()


@pytest.mark.django_db
def test_till_sync_loads_everything_except_the_injected_problems():
    mock = MockTillConnector()
    received = len(list(mock.fetch()))

    run = sync()

    assert run.status == ImportRun.Status.SUCCEEDED
    assert run.received == received
    assert run.rejected == sum(mock.injected.values())
    reasons = " ".join(
        " ".join(errors) for errors in StagedRecord.objects.filter(
            run=run, status=StagedRecord.Status.REJECTED
        ).values_list("errors", flat=True)
    )
    assert "business type 'Car wash' is not recognised" in reasons
    assert "outlet 'KIOSK-9' is not known" in reasons
    assert "takings '-25,000' is negative" in reasons
    assert "stock on hand 'twenty' is not a whole number" in reasons
    assert "duplicate of an earlier record" in reasons


@pytest.mark.django_db
def test_till_values_are_cleaned():
    sync()

    outlets = {o.code: o for o in Outlet.objects.all()}
    assert outlets["shop-b"].name == "Shop B"  # was "SHOP B"
    assert outlets["shop-d"].name == "Shop D"  # was "shop d"
    shops = ("shop-a", "shop-b", "shop-c", "shop-d")
    assert {outlets[code].business_type for code in shops} == {"uniform_shop"}
    assert outlets["minimart"].business_type == "minimart"  # was "Mini-mart"
    assert StockItem.objects.get(name="Girls' skirt (L)").unit_cost == Decimal("32000.00")


@pytest.mark.django_db
def test_till_rerun_updates_instead_of_duplicating():
    first = sync()
    counts = [model.objects.count() for model in MODELS]

    second = sync()

    assert [model.objects.count() for model in MODELS] == counts
    assert second.created == 0
    assert second.updated == first.created


@pytest.mark.django_db
def test_sales_screen_on_synced_data():
    sync()

    body = APIClient().get("/api/services/sales/dashboard/", PERIOD).json()

    assert body["summary"]["total_sales"] == "681000000.00"
    assert body["summary"]["transactions"] == 92100
    # cost is rounded to the shilling each day, so profit lands within a few hundred UGX
    assert abs(Decimal(body["summary"]["gross_profit"]) - 215_140_000) < 2_000
    february = body["monthly_trend"][0]
    assert february["label"] == "Feb"
    assert abs(Decimal(february["revenue"]) - 112_000_000) <= 10


@pytest.mark.django_db
def test_inventory_screen_on_synced_data():
    sync()

    summary = APIClient().get("/api/services/inventory/dashboard/").json()["summary"]

    assert summary == {"stock_value": "13770500.00", "below_minimum": 9, "critical": 2,
                       "outlets": 6}


@pytest.mark.django_db
def test_budget_screen_on_synced_data():
    sync()

    body = APIClient().get("/api/services/budget/dashboard/", {"as_of": "2026-10-17"}).json()

    assert body["summary"]["operating_budget"] == "570000000.00"
    assert body["summary"]["spent"] == "480000000.00"
    assert body["summary"]["budget_used"] == 84.2
    statuses = {row["name"]: row["status_display"] for row in body["outlets"]}
    assert statuses["Shop D"] == "Overspending"
    assert statuses["Shop B"] == "On track"
