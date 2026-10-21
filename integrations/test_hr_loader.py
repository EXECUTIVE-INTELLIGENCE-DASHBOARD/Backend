from datetime import date

import pytest
from rest_framework.test import APIClient

from operations.models import Employee, StaffAttendance, WorkforceUnit

from .connectors.hr import MockHRConnector
from .loaders.hr import load_hr
from .models import ImportRun, StagedRecord
from .pipeline import run_sync
from .sources import all_sources

AS_OF = date(2026, 10, 20)


def connector():
    return MockHRConnector(scale=0.1, as_of=AS_OF)


def sync():
    return run_sync(connector(), load_hr, "HR System")


def test_the_hr_source_is_registered():
    assert "hr" in all_sources()


@pytest.mark.django_db
def test_hr_sync_loads_everything_except_the_injected_problems():
    mock = connector()
    received = len(list(mock.fetch()))

    run = sync()

    assert run.status == ImportRun.Status.SUCCEEDED
    assert run.received == received
    assert run.rejected == sum(mock.injected.values())
    assert run.created == received - run.rejected
    reasons = " ".join(
        " ".join(errors) for errors in StagedRecord.objects.filter(
            run=run, status=StagedRecord.Status.REJECTED
        ).values_list("errors", flat=True)
    )
    assert "department 'Library Services' is not known" in reasons
    assert "hire date '30/02/2018' is not a recognised date" in reasons
    assert "attendance code 'WFH' is not recognised" in reasons


@pytest.mark.django_db
def test_hr_values_are_cleaned():
    sync()

    assert WorkforceUnit.objects.count() == 5
    assert set(WorkforceUnit.objects.values_list("campus", flat=True)) == {"kibuli", "multi_campus"}
    assert set(Employee.objects.values_list("employment_type", flat=True)) <= {
        "full_time", "contract", "part_time"
    }
    assert Employee.objects.filter(is_active=False).exists()  # leavers kept, but inactive
    assert set(StaffAttendance.objects.values_list("status", flat=True)) <= {
        "present", "absent", "on_leave", "on_training", "on_field"
    }


@pytest.mark.django_db
def test_hr_rerun_updates_instead_of_duplicating():
    first = sync()
    counts = [m.objects.count() for m in (WorkforceUnit, Employee, StaffAttendance)]

    second = sync()

    assert [m.objects.count() for m in (WorkforceUnit, Employee, StaffAttendance)] == counts
    assert second.created == 0
    assert second.updated == first.created


@pytest.mark.django_db
def test_hr_dashboard_works_on_synced_data():
    sync()
    active = Employee.objects.filter(is_active=True).count()

    body = APIClient().get(
        "/api/operations/hr/dashboard/", {"start": date(2026, 9, 21), "end": AS_OF}
    ).json()

    assert body["summary"]["total_staff"] == active
    assert body["summary"]["workforce_attendance_rate"] > 90
    units = {unit["name"]: unit for unit in body["units"]}
    # the design's "4 on Leave" for teaching staff, on the last day
    assert units["Academic & Curriculum Instruction"]["absences"] == {"on_leave": 4}
