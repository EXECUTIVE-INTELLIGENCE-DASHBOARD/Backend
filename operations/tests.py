from datetime import date

import pytest
from rest_framework.test import APIClient

from .models import Asset, Employee, Facility, StaffAttendance, WorkforceUnit

DASHBOARD_URL = "/api/operations/hr/dashboard/"
DAY_1 = date(2026, 10, 15)
DAY_2 = date(2026, 10, 16)


@pytest.fixture
def client():
    return APIClient()


def make_unit(name, category, campus=WorkforceUnit.Campus.KIBULI):
    return WorkforceUnit.objects.create(name=name, staff_category=category, campus=campus)


def make_staff(unit, count, prefix, is_active=True):
    return [
        Employee.objects.create(
            staff_number=f"{prefix}-{i}",
            full_name=f"Test {prefix} {i}",
            unit=unit,
            is_active=is_active,
        )
        for i in range(count)
    ]


@pytest.fixture
def workforce():
    """Synthetic register: 2 teaching staff, 3 non-teaching (one on another campus)."""
    teaching = make_unit("Academic Instruction", WorkforceUnit.StaffCategory.TEACHING)
    support = make_unit("Boarding & Catering", WorkforceUnit.StaffCategory.NON_TEACHING_SUPPORT)
    transport = make_unit(
        "Transport & Fleet",
        WorkforceUnit.StaffCategory.DRIVERS_TECHNICIANS,
        WorkforceUnit.Campus.BUWAATE,
    )
    teachers = make_staff(teaching, 2, "T")
    cooks = make_staff(support, 2, "S")
    drivers = make_staff(transport, 1, "D")
    make_staff(teaching, 1, "LEFT", is_active=False)  # a leaver must not count

    Status = StaffAttendance.Status
    for employee in teachers + cooks + drivers:
        StaffAttendance.objects.create(employee=employee, date=DAY_1, status=Status.PRESENT)
    StaffAttendance.objects.create(employee=teachers[0], date=DAY_2, status=Status.PRESENT)
    StaffAttendance.objects.create(employee=teachers[1], date=DAY_2, status=Status.ON_LEAVE)
    StaffAttendance.objects.create(employee=cooks[0], date=DAY_2, status=Status.PRESENT)
    StaffAttendance.objects.create(employee=cooks[1], date=DAY_2, status=Status.ON_TRAINING)
    StaffAttendance.objects.create(employee=drivers[0], date=DAY_2, status=Status.PRESENT)
    return {"teaching": teaching, "support": support, "transport": transport}


@pytest.mark.django_db
def test_dashboard_summarises_headcount_ratio_and_attendance(client, workforce):
    response = client.get(DASHBOARD_URL, {"start": DAY_1, "end": DAY_2})

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == {
        "total_staff": 5,
        "teaching_staff": 2,
        "non_teaching_staff": 3,
        "staffing_ratio": 1.5,
        "staffing_ratio_display": "1:1.5",
        "workforce_attendance_rate": 80.0,  # 8 present out of 10 staff-days
    }
    units = {unit["name"]: unit for unit in body["units"]}
    assert units["Academic Instruction"]["headcount"] == 2
    assert units["Academic Instruction"]["attendance_rate"] == 75.0
    assert units["Academic Instruction"]["absences"] == {"on_leave": 1}
    assert units["Boarding & Catering"]["absences"] == {"on_training": 1}
    assert units["Transport & Fleet"]["attendance_rate"] == 100.0
    assert units["Transport & Fleet"]["absences"] == {}


@pytest.mark.django_db
def test_dashboard_absences_are_a_snapshot_of_the_end_date(client, workforce):
    body = client.get(DASHBOARD_URL, {"start": DAY_1, "end": DAY_1}).json()

    assert all(unit["absences"] == {} for unit in body["units"])
    assert body["summary"]["workforce_attendance_rate"] == 100.0


@pytest.mark.django_db
def test_dashboard_filters_by_campus(client, workforce):
    body = client.get(DASHBOARD_URL, {"start": DAY_1, "end": DAY_2, "campus": "buwaate"}).json()

    assert [unit["name"] for unit in body["units"]] == ["Transport & Fleet"]
    assert body["summary"]["total_staff"] == 1
    assert body["summary"]["staffing_ratio"] is None  # no teaching staff in the selection


@pytest.mark.django_db
def test_dashboard_with_no_attendance_returns_null_rates(client):
    make_unit("Empty Unit", WorkforceUnit.StaffCategory.ADMINISTRATIVE)

    body = client.get(DASHBOARD_URL, {"start": DAY_1, "end": DAY_2}).json()

    assert body["summary"]["workforce_attendance_rate"] is None
    assert body["units"][0]["attendance_rate"] is None


@pytest.mark.django_db
def test_dashboard_rejects_start_after_end(client):
    response = client.get(DASHBOARD_URL, {"start": DAY_2, "end": DAY_1})

    assert response.status_code == 400


@pytest.mark.django_db
def test_employee_list_filters_by_unit(client, workforce):
    response = client.get("/api/operations/hr/employees/", {"unit": workforce["support"].pk})

    assert response.status_code == 200
    assert {row["unit_name"] for row in response.json()} == {"Boarding & Catering"}
    assert len(response.json()) == 2


@pytest.mark.django_db
def test_attendance_rejects_duplicate_day_for_same_employee(client, workforce):
    employee = Employee.objects.get(staff_number="D-0")

    response = client.post(
        "/api/operations/hr/attendance/",
        {"employee": employee.pk, "date": DAY_1, "status": "present"},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_unit_can_be_created_through_the_api(client):
    response = client.post(
        "/api/operations/hr/units/",
        {
            "name": "Facilities & Maintenance",
            "staff_category": "technical_security",
            "campus": "multi_campus",
            "location": "Multi-Campus Grounds",
        },
        format="json",
    )

    assert response.status_code == 201
    assert WorkforceUnit.objects.filter(name="Facilities & Maintenance").exists()


# --- Asset register -------------------------------------------------------------

ASSET_DASHBOARD_URL = "/api/operations/assets/dashboard/"


@pytest.fixture
def register():
    """Synthetic register worth UGX 200M across 142 active units, plus one decommissioned line."""
    suite = Facility.objects.create(
        name="Computer Suite B",
        campus=Facility.Campus.KIBULI,
        facility_type=Facility.FacilityType.LABORATORY,
    )
    lab = Facility.objects.create(
        name="Chemistry Lab 1",
        campus=Facility.Campus.BUWAATE,
        facility_type=Facility.FacilityType.LABORATORY,
    )
    Condition, Category = Asset.Condition, Asset.Category
    Asset.objects.create(
        name="Student Laboratory Workstations", category=Category.COMPUTER_EQUIPMENT,
        facility=suite, quantity=100, unit_value=1_000_000, condition=Condition.OPERATIONAL,
    )
    Asset.objects.create(
        name="Spectrophotometers", category=Category.LABORATORY_EQUIPMENT,
        facility=lab, quantity=40, unit_value=2_000_000, condition=Condition.SERVICING_REQUIRED,
    )
    Asset.objects.create(
        name="Backup Generator", category=Category.MACHINERY,
        facility=suite, quantity=2, unit_value=10_000_000, condition=Condition.CRITICAL,
    )
    Asset.objects.create(
        name="Retired Bus", category=Category.VEHICLE,
        facility=suite, quantity=3, unit_value=50_000_000, condition=Condition.DECOMMISSIONED,
    )
    return {"suite": suite, "lab": lab}


@pytest.mark.django_db
def test_asset_dashboard_summarises_units_value_and_risk(client, register):
    response = client.get(ASSET_DASHBOARD_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == {
        "total_assets": 142,
        "total_value": "200000000.00",
        "operational_rate": 70.4,  # 100 of 142 units are operational
        "capital_risk": 50.0,  # UGX 100M of 200M needs servicing or is critical
        "capital_at_risk_value": "100000000.00",
        "units_by_condition": {"operational": 100, "servicing_required": 40, "critical": 2},
    }
    assert [asset["name"] for asset in body["assets"]] == [
        "Backup Generator",
        "Spectrophotometers",
        "Student Laboratory Workstations",
    ]  # decommissioned lines are left out


@pytest.mark.django_db
def test_asset_dashboard_rows_carry_location_value_and_labels(client, register):
    body = client.get(ASSET_DASHBOARD_URL).json()

    spectrometers = next(a for a in body["assets"] if a["name"] == "Spectrophotometers")
    assert spectrometers["facility_name"] == "Chemistry Lab 1"
    assert spectrometers["campus_display"] == "Buwaate"
    assert spectrometers["category_display"] == "Science Laboratory Equipment"
    assert spectrometers["condition_display"] == "Servicing Required"
    assert spectrometers["total_value"] == "80000000.00"


@pytest.mark.django_db
def test_asset_dashboard_filters_by_campus(client, register):
    body = client.get(ASSET_DASHBOARD_URL, {"campus": "kibuli"}).json()

    assert body["summary"]["total_assets"] == 102
    assert body["summary"]["operational_rate"] == 98.0
    assert body["summary"]["capital_risk"] == 16.7  # UGX 20M of 120M


@pytest.mark.django_db
def test_asset_dashboard_with_empty_register_returns_null_rates(client):
    body = client.get(ASSET_DASHBOARD_URL).json()

    assert body["summary"]["total_assets"] == 0
    assert body["summary"]["total_value"] == "0.00"
    assert body["summary"]["operational_rate"] is None
    assert body["summary"]["capital_risk"] is None
    assert body["assets"] == []


@pytest.mark.django_db
def test_asset_dashboard_rejects_unknown_campus(client):
    assert client.get(ASSET_DASHBOARD_URL, {"campus": "nowhere"}).status_code == 400


@pytest.mark.django_db
def test_asset_can_be_registered_and_filtered_by_condition(client, register):
    response = client.post(
        "/api/operations/assets/",
        {
            "name": "Ergonomic Office Desks",
            "category": "furniture",
            "facility": register["suite"].pk,
            "quantity": 65,
            "unit_value": "1000000.00",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["condition"] == "operational"
    assert response.json()["total_value"] == "65000000.00"
    critical = client.get("/api/operations/assets/", {"condition": "critical"}).json()
    assert [asset["name"] for asset in critical] == ["Backup Generator"]


# --- Annex Preschool campus ---------------------------------------------------------

@pytest.mark.django_db
def test_hr_dashboard_filters_by_annex_campus(client, workforce):
    make_unit("Annex Teaching", WorkforceUnit.StaffCategory.TEACHING, WorkforceUnit.Campus.ANNEX)

    body = client.get(DASHBOARD_URL, {"start": DAY_1, "end": DAY_2, "campus": "annex"}).json()

    assert [unit["name"] for unit in body["units"]] == ["Annex Teaching"]


@pytest.mark.django_db
def test_asset_dashboard_filters_by_annex_campus(client, register):
    power_house = Facility.objects.create(
        name="Annex Power House",
        campus=Facility.Campus.ANNEX,
        facility_type=Facility.FacilityType.OTHER,
    )
    Asset.objects.create(
        name="Backup Generator", category=Asset.Category.MACHINERY, facility=power_house,
        quantity=1, unit_value=50_000_000,
    )

    body = client.get(ASSET_DASHBOARD_URL, {"campus": "annex"}).json()

    assert [asset["campus_display"] for asset in body["assets"]] == ["Annex Preschool"]
    assert body["summary"]["total_assets"] == 1
