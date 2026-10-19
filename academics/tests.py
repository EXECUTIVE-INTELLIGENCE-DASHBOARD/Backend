from datetime import date

import pytest
from rest_framework.test import APIClient

from .models import Application, Enrolment, School, StudentProfile, Term

ENROLLMENT_URL = "/api/academics/enrollment/dashboard/"
RETENTION_URL = "/api/academics/retention/dashboard/"
Status, Reason = Enrolment.Status, Enrolment.WithdrawalReason


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def setup():
    """Three schools (one per campus) and two consecutive terms."""
    kibuli = School.objects.create(
        name="Primary Kibuli", campus=School.Campus.KIBULI, capacity=10, minimum_enrolment=3
    )
    buwaate = School.objects.create(
        name="Nursery Buwaate", campus=School.Campus.BUWAATE, capacity=5, minimum_enrolment=4
    )
    annex = School.objects.create(name="Annex Preschool", campus=School.Campus.ANNEX, capacity=5)
    term2 = Term.objects.create(
        academic_year="2026", number=2, start_date=date(2026, 5, 25), end_date=date(2026, 8, 14)
    )
    term3 = Term.objects.create(
        academic_year="2026", number=3, start_date=date(2026, 9, 14), end_date=date(2026, 12, 4)
    )
    return {"kibuli": kibuli, "buwaate": buwaate, "annex": annex, "term2": term2, "term3": term3}


def student(number, gender="male", nationality="Ugandan"):
    return StudentProfile.objects.create(
        student_number=number, gender=gender, nationality=nationality
    )


def enrol(person, school, term, status=Status.ACTIVE, reason="", at_risk=False):
    return Enrolment.objects.create(
        student=person, school=school, term=term, status=status,
        withdrawal_reason=reason, at_risk=at_risk,
    )


# --- Enrollment dashboard -----------------------------------------------------------

@pytest.fixture
def enrollment(setup):
    """Term 3: 9 active students (4 boys, 5 girls), 1 withdrawal, 10 applications."""
    s, t3 = setup, setup["term3"]
    for i, gender in enumerate(["male", "male", "male", "female", "female"]):
        enrol(student(f"K{i}", gender), s["kibuli"], t3)
    for i, gender in enumerate(["male", "female", "female"]):
        enrol(student(f"B{i}", gender), s["buwaate"], t3)
    enrol(student("A0", "female"), s["annex"], t3)
    enrol(student("W0"), s["kibuli"], t3, Status.WITHDRAWN, Reason.FINANCIAL)
    # 4 reach "accepted", but only 2 of those take up their place
    stages = (
        ["applied"] * 2 + ["qualified"] * 3 + ["interviewed"] * 1
        + ["accepted"] * 2 + ["enrolled"] * 2
    )
    for i, stage in enumerate(stages):
        Application.objects.create(
            reference=f"APP-{i}", school=s["kibuli"], term=t3, stage=stage,
            applied_on=date(2026, 8, 1),
        )
    return setup


@pytest.mark.django_db
def test_enrollment_dashboard_summary_and_funnel(client, enrollment):
    body = client.get(ENROLLMENT_URL, {"term": enrollment["term3"].pk}).json()

    assert body["summary"] == {
        "total_active_enrolment": 9,  # the withdrawn student is left out
        "admissions_conversion": 20.0,  # 2 enrolled of 10 applications
        "capacity": 20,
        "capacity_utilisation": 45.0,  # 9 of 20 places
    }
    assert body["gender"] == {"boys": 4, "girls": 5, "boys_pct": 44.4, "girls_pct": 55.6}
    assert [(p["stage"], p["count"], p["rate"]) for p in body["pipeline"]] == [
        ("applied", 10, 100.0),
        ("qualified", 8, 80.0),
        ("interviewed", 5, 50.0),
        ("accepted", 4, 40.0),
        ("enrolled", 2, 20.0),  # yield: 2 of the 4 accepted enrolled
    ]


@pytest.mark.django_db
def test_enrollment_dashboard_campus_bars_and_school_minimums(client, enrollment):
    body = client.get(ENROLLMENT_URL, {"term": enrollment["term3"].pk}).json()

    assert [(c["campus_display"], c["boys"], c["girls"], c["total"]) for c in body["campuses"]] == [
        ("Kibuli Main", 3, 2, 5),
        ("Buwaate", 1, 2, 3),
        ("Annex Preschool", 0, 1, 1),
    ]
    schools = {s["name"]: s for s in body["schools"]}
    assert schools["Nursery Buwaate"]["enrolled"] == 3
    assert schools["Nursery Buwaate"]["below_minimum"] is True  # minimum is 4
    assert schools["Primary Kibuli"]["below_minimum"] is False


@pytest.mark.django_db
def test_enrollment_dashboard_filters_by_campus(client, enrollment):
    body = client.get(ENROLLMENT_URL, {"term": enrollment["term3"].pk, "campus": "kibuli"}).json()

    assert body["summary"]["total_active_enrolment"] == 5
    assert body["summary"]["capacity_utilisation"] == 50.0
    assert [c["campus"] for c in body["campuses"]] == ["kibuli"]
    assert [s["name"] for s in body["schools"]] == ["Primary Kibuli"]


@pytest.mark.django_db
def test_enrollment_dashboard_defaults_to_latest_started_term(client, enrollment):
    body = client.get(ENROLLMENT_URL).json()

    # both terms have started by 19 Oct 2026, so the latest one is used
    assert body["term"]["id"] == enrollment["term3"].pk


@pytest.mark.django_db
def test_dashboards_return_404_without_terms(client):
    assert client.get(ENROLLMENT_URL).status_code == 404
    assert client.get(RETENTION_URL).status_code == 404


@pytest.mark.django_db
def test_dashboards_reject_unknown_campus(client, setup):
    assert client.get(ENROLLMENT_URL, {"campus": "nowhere"}).status_code == 400


# --- Retention dashboard ------------------------------------------------------------

@pytest.fixture
def retention(setup):
    """Term 3 of 2025 has 5 students eligible to return (plus 1 graduate); 3 come back
    at some point in 2026."""
    s, t3 = setup, setup["term3"]
    last_year = Term.objects.create(
        academic_year="2025", number=3, start_date=date(2025, 9, 15), end_date=date(2025, 12, 5)
    )
    t1 = Term.objects.create(
        academic_year="2026", number=1, start_date=date(2026, 2, 2), end_date=date(2026, 4, 30)
    )
    s1, s2 = student("S1", nationality="Ugandan"), student("S2", nationality="Ugandan")
    s3, s4 = student("S3", nationality="Kenyan"), student("S4", nationality="Ugandan")
    s5, s6 = student("S5", nationality="Kenyan"), student("S6", nationality="Rwandese")
    for person in (s1, s2, s3):
        enrol(person, s["kibuli"], last_year)
    enrol(s4, s["kibuli"], last_year, Status.GRADUATED)  # not expected back
    enrol(s5, s["buwaate"], last_year)
    enrol(s6, s["buwaate"], last_year)

    enrol(s1, s["kibuli"], t1)  # back in term 1 only, still counts for the year
    enrol(s2, s["buwaate"], t3, at_risk=True)  # moved campus, still retained
    enrol(s5, s["buwaate"], setup["term2"])
    enrol(student("S7"), s["kibuli"], t3, at_risk=True)  # new this year
    enrol(student("S8"), s["kibuli"], t3, Status.WITHDRAWN, Reason.FINANCIAL)
    enrol(student("S9"), s["kibuli"], t3, Status.WITHDRAWN, Reason.FINANCIAL)
    enrol(student("S10"), s["kibuli"], t1, Status.WITHDRAWN, Reason.TRANSFER)  # earlier in the year
    return {**setup, "last_year": last_year, "term1": t1}


@pytest.mark.django_db
def test_retention_dashboard_summary(client, retention):
    body = client.get(RETENTION_URL, {"term": retention["term3"].pk}).json()

    assert body["academic_year"] == "2026"
    assert body["compared_with"]["id"] == retention["last_year"].pk
    assert body["summary"] == {
        "eligible_to_return": 5,  # the graduate is left out
        "total_re_enrolled": 3,
        "re_enrolment_rate": 60.0,
        "at_risk": 2,
    }


@pytest.mark.django_db
def test_retention_by_nationality_and_campus(client, retention):
    body = client.get(RETENTION_URL, {"term": retention["term3"].pk}).json()

    rows = {(r["nationality"], r["campus"]): r for r in body["by_nationality"]}
    ugandan_kibuli = rows[("Ugandan", "kibuli")]
    assert (ugandan_kibuli["eligible"], ugandan_kibuli["re_enrolled"]) == (2, 2)
    assert rows[("Ugandan", "kibuli")]["retention_rate"] == 100.0
    assert rows[("Kenyan", "kibuli")]["retention_rate"] == 0.0
    assert rows[("Kenyan", "buwaate")]["retention_rate"] == 100.0
    assert rows[("Rwandese", "buwaate")]["retention_rate"] == 0.0
    assert body["by_nationality"][0]["nationality"] == "Ugandan"  # largest group first


@pytest.mark.django_db
def test_retention_withdrawal_reasons(client, retention):
    body = client.get(RETENTION_URL, {"term": retention["term3"].pk}).json()

    assert body["withdrawals_total"] == 3
    assert [(r["label"], r["count"], r["share"]) for r in body["withdrawal_reasons"]] == [
        ("Financial Constraints", 2, 66.7),
        ("Transfer to Another School", 1, 33.3),
    ]


@pytest.mark.django_db
def test_retention_filters_by_campus(client, retention):
    body = client.get(RETENTION_URL, {"term": retention["term3"].pk, "campus": "kibuli"}).json()

    assert body["summary"]["eligible_to_return"] == 3
    assert body["summary"]["total_re_enrolled"] == 2  # S2 counts even though she moved
    assert body["summary"]["re_enrolment_rate"] == 66.7


@pytest.mark.django_db
def test_retention_without_previous_year_has_no_rate(client, retention):
    body = client.get(RETENTION_URL, {"term": retention["last_year"].pk}).json()

    assert body["compared_with"] is None
    assert body["summary"]["re_enrolment_rate"] is None


# --- Data rules ---------------------------------------------------------------------

@pytest.mark.django_db
def test_withdrawn_enrolment_needs_a_reason(client, setup):
    person = student("X1")
    payload = {
        "student": person.pk, "school": setup["kibuli"].pk, "term": setup["term3"].pk,
        "status": "withdrawn",
    }
    response = client.post("/api/academics/enrolments/", payload, format="json")

    assert response.status_code == 400
    assert "withdrawal_reason" in response.json()


@pytest.mark.django_db
def test_only_withdrawn_enrolments_have_a_reason(client, setup):
    person = student("X2")
    payload = {
        "student": person.pk, "school": setup["kibuli"].pk, "term": setup["term3"].pk,
        "status": "active", "withdrawal_reason": "financial",
    }

    assert client.post("/api/academics/enrolments/", payload, format="json").status_code == 400


@pytest.mark.django_db
def test_one_enrolment_per_student_per_term(client, setup):
    person = student("X3")
    enrol(person, setup["kibuli"], setup["term3"])
    payload = {"student": person.pk, "school": setup["buwaate"].pk, "term": setup["term3"].pk}

    assert client.post("/api/academics/enrolments/", payload, format="json").status_code == 400
