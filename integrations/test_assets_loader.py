from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from operations.models import Asset, Facility

from .cleaning import CleaningError, parse_money
from .connectors.assets import MockAssetRegisterConnector
from .loaders.assets import load_asset_register
from .models import ImportRun, StagedRecord
from .pipeline import run_sync
from .sources import all_sources


def sync():
    return run_sync(MockAssetRegisterConnector(), load_asset_register, "Asset Register")


@pytest.mark.parametrize(
    "raw", ["UGX 1,500,000", "1,500,000", "1500000.00", "Ush 1500000", 1500000]
)
def test_parse_money_reads_common_formats(raw):
    assert parse_money(raw) == Decimal("1500000.00")


@pytest.mark.parametrize("raw", ["", "one million", "-5,000"])
def test_parse_money_rejects_bad_amounts(raw):
    with pytest.raises(CleaningError):
        parse_money(raw, "unit cost")


def test_the_asset_source_is_registered():
    assert "assets" in all_sources()


@pytest.mark.django_db
def test_asset_sync_loads_everything_except_the_injected_problems():
    mock = MockAssetRegisterConnector()
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
    assert "campus 'Entebbe' is not recognised" in reasons
    assert "site 'ZZ-999' is not known" in reasons
    assert "quantity 'two' is not a whole number" in reasons
    assert "condition 'Lost' is not recognised" in reasons


@pytest.mark.django_db
def test_asset_values_are_cleaned():
    sync()

    workstations = Asset.objects.get(name="Dell Student Laboratory Workstations")
    assert workstations.unit_value == Decimal("1500000.00")
    assert workstations.total_value == Decimal("180000000.00")
    assert workstations.facility.campus == "kibuli"
    assert Asset.objects.get(name="250kVA Heavy-Duty Backup Generator").facility.campus == "annex"
    assert Asset.objects.get(name="Old Minibus").condition == "decommissioned"
    assert set(Facility.objects.values_list("campus", flat=True)) == {"kibuli", "buwaate", "annex"}


@pytest.mark.django_db
def test_asset_rerun_updates_instead_of_duplicating():
    first = sync()
    counts = (Facility.objects.count(), Asset.objects.count())

    second = sync()

    assert (Facility.objects.count(), Asset.objects.count()) == counts
    assert second.created == 0
    assert second.updated == first.created


@pytest.mark.django_db
def test_asset_dashboard_matches_the_design():
    sync()

    summary = APIClient().get("/api/operations/assets/dashboard/").json()["summary"]

    assert summary["total_assets"] == 4250  # the old minibus is decommissioned, so left out
    assert summary["operational_rate"] == 88.2
    assert summary["capital_risk"] == 11.8
