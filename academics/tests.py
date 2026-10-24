from datetime import date

import pytest
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from integrations.models import SourceSystem

from .models import (
    Application,
    Assessment,
    AssessmentResult,
    Enrolment,
    NationalExamResult,
    School,
    StudentProfile,
    Subject,
    SyllabusCoverage,
    Term,
    grade_for,
)

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


# --- Source tracking ----------------------------------------------------------------

@pytest.fixture
def smis():
    return SourceSystem.objects.create(code="smis", name="School Management Information System")


@pytest.mark.django_db
def test_a_source_record_can_only_be_stored_once(smis):
    StudentProfile.objects.create(
        student_number="S1", gender="male", nationality="Ugandan",
        source_system=smis, external_id="ADM-001",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        StudentProfile.objects.create(
            student_number="S2", gender="male", nationality="Ugandan",
            source_system=smis, external_id="ADM-001",
        )


@pytest.mark.django_db
def test_the_same_id_is_allowed_in_different_sources(smis):
    other = SourceSystem.objects.create(code="hr", name="HR system")
    for number, source in (("S1", smis), ("S2", other)):
        StudentProfile.objects.create(
            student_number=number, gender="male", nationality="Ugandan",
            source_system=source, external_id="ADM-001",
        )

    assert StudentProfile.objects.filter(external_id="ADM-001").count() == 2


@pytest.mark.django_db
def test_hand_entered_rows_without_an_external_id_never_clash():
    student("H1")
    student("H2")

    assert StudentProfile.objects.filter(external_id="").count() == 2


@pytest.mark.django_db
def test_source_fields_cannot_be_set_through_the_api(client, smis):
    payload = {
        "student_number": "S9", "gender": "female", "nationality": "Kenyan",
        "source_system": smis.pk, "external_id": "ADM-999",
    }
    response = client.post("/api/academics/student-profiles/", payload, format="json")

    assert response.status_code == 201
    saved = StudentProfile.objects.get(student_number="S9")
    assert (saved.source_system, saved.external_id) == (None, "")



@pytest.mark.django_db
def test_schools_can_be_filtered_by_level(client):
    School.objects.create(name="Nursery X", campus=School.Campus.KIBULI, level="nursery")
    School.objects.create(name="Primary X", campus=School.Campus.KIBULI, level="primary")

    body = client.get("/api/academics/schools/", {"level": "primary"}).json()

    assert [s["name"] for s in body] == ["Primary X"]
    assert body[0]["level"] == "primary"


# --- Academic performance models ---------------------------------------------------

@pytest.mark.parametrize("level, mark, grade", [
    ("primary", 85, "D1"), ("primary", 50, "C6"), ("primary", 39.9, "F9"),
    ("o_level", 70, "B"), ("o_level", 40, "E"), ("o_level", 12, "U"),
    ("a_level", 45, "E"), ("a_level", 35, "O"), ("a_level", 34.5, "F"),
])
def test_grade_for_uses_the_subject_levels_scale(level, mark, grade):
    assert grade_for(level, mark) == grade


@pytest.fixture
def maths_test(setup):
    maths = Subject.objects.create(code="MTC", name="Mathematics", level="o_level",
                                   category="science")
    secondary = School.objects.create(name="Secondary Kibuli", campus="kibuli",
                                      level="secondary")
    return Assessment.objects.create(school=secondary, term=setup["term3"], subject=maths,
                                     class_level="S3", kind=Assessment.Kind.TEST_1)


@pytest.mark.django_db
def test_a_mark_must_be_between_0_and_100(maths_test):
    with pytest.raises(IntegrityError), transaction.atomic():
        AssessmentResult.objects.create(assessment=maths_test, student=student("S1"),
                                        mark=101, grade="A")


@pytest.mark.django_db
def test_a_student_has_one_result_per_assessment(maths_test):
    pupil = student("S1")
    result = AssessmentResult.objects.create(assessment=maths_test, student=pupil, mark=50,
                                             grade="D")
    assert result.passed

    with pytest.raises(IntegrityError), transaction.atomic():
        AssessmentResult.objects.create(assessment=maths_test, student=pupil, mark=60,
                                        grade="C")


@pytest.mark.django_db
def test_the_same_assessment_cannot_be_recorded_twice(maths_test):
    with pytest.raises(IntegrityError), transaction.atomic():
        Assessment.objects.create(school=maths_test.school, term=maths_test.term,
                                  subject=maths_test.subject, class_level="S3",
                                  kind=Assessment.Kind.TEST_1)


@pytest.mark.django_db
def test_syllabus_covered_cannot_exceed_planned(maths_test):
    with pytest.raises(IntegrityError), transaction.atomic():
        SyllabusCoverage.objects.create(school=maths_test.school, term=maths_test.term,
                                        subject=maths_test.subject, class_level="S3",
                                        topics_planned=10, topics_covered=11)


@pytest.mark.django_db
def test_a_ple_aggregate_runs_from_4_to_36(setup):
    with pytest.raises(IntegrityError), transaction.atomic():
        NationalExamResult.objects.create(student=student("P7A"), school=setup["kibuli"],
                                          exam="ple", year=2025, division="division_1",
                                          aggregate=3, passed=True)
    ok = NationalExamResult.objects.create(student=student("P7B"), school=setup["kibuli"],
                                           exam="ple", year=2025, division="division_1",
                                           aggregate=4, passed=True)
    assert str(ok) == "P7B - PLE 2025"


# --- Academic performance dashboard ---------------------------------------------------

PERFORMANCE_URL = "/api/academics/performance/dashboard/"


@pytest.fixture
def performance(setup):
    """Term 3: two S3 students sit Maths Test 1 and Test 2 at the secondary school, one
    P7 pupil sits English Test 1 at the primary school. Term 2: the same S3 students'
    Maths end-of-term exam. Plus syllabus coverage and 2025 national exams."""
    t2, t3 = setup["term2"], setup["term3"]
    primary = setup["kibuli"]
    primary.level = School.Level.PRIMARY
    primary.save()
    secondary = School.objects.create(name="Secondary Kibuli", campus="kibuli",
                                      level=School.Level.SECONDARY, capacity=10)
    maths = Subject.objects.create(code="MTC", name="Mathematics", level="o_level",
                                   category="science")
    english = Subject.objects.create(code="ENG", name="English", level="primary",
                                     category="arts")
    s1, s2, p1 = student("S1"), student("S2", "female"), student("P1")

    def sit(school, term, subject, class_level, kind, marks):
        test = Assessment.objects.create(school=school, term=term, subject=subject,
                                         class_level=class_level, kind=kind)
        for pupil, mark in marks:
            AssessmentResult.objects.create(assessment=test, student=pupil, mark=mark,
                                            grade=grade_for(subject.level, mark))

    sit(secondary, t3, maths, "S3", "test_1", [(s1, 80), (s2, 40)])
    sit(secondary, t3, maths, "S3", "test_2", [(s1, 70), (s2, 30)])
    sit(primary, t3, english, "P7", "test_1", [(p1, 55)])
    sit(secondary, t2, maths, "S3", "end_of_term", [(s1, 45), (s2, 30)])
    SyllabusCoverage.objects.create(school=secondary, term=t3, subject=maths, class_level="S3",
                                    topics_planned=10, topics_covered=6)
    SyllabusCoverage.objects.create(school=primary, term=t3, subject=english, class_level="P7",
                                    topics_planned=10, topics_covered=4)

    def exam(name, number, school, year, division="", passes=None, passed=True):
        NationalExamResult.objects.create(student=student(name), school=school, exam=number,
                                          year=year, division=division,
                                          principal_passes=passes, passed=passed)

    exam("X1", "ple", primary, 2025, "division_1")
    exam("X2", "ple", primary, 2025, "division_4")
    exam("X3", "ple", primary, 2025, "ungraded", passed=False)
    exam("X4", "ple", primary, 2024, "ungraded", passed=False)  # an older sitting
    exam("X5", "ple", primary, 2027, "division_1")  # after this academic year
    exam("X6", "uace", secondary, 2025, passes=2)
    return setup


@pytest.mark.django_db
def test_performance_summary(client, performance):
    body = client.get(PERFORMANCE_URL, {"term": performance["term3"].pk}).json()

    assert body["term"]["label"] == "Term 3, 2026"
    assert body["compared_with"]["label"] == "Term 2, 2026"
    assert body["summary"] == {
        "syllabus_coverage": 50.0, "topics_covered": 10, "topics_planned": 20,
        # S1 averages 75 and P1 55 (passing); S2 averages 35
        "student_performance": 66.7, "students_passing": 2, "students_assessed": 3,
        "average_mark": 55.0,
        "average_grade": None,  # no section chosen, so no single scale applies
    }


@pytest.mark.django_db
def test_performance_section_filter_and_average_grade(client, performance):
    body = client.get(PERFORMANCE_URL, {"term": performance["term3"].pk,
                                        "level": "secondary"}).json()

    summary = body["summary"]
    assert (summary["students_assessed"], summary["students_passing"]) == (2, 1)
    assert summary["syllabus_coverage"] == 60.0
    assert (summary["average_mark"], summary["average_grade"]) == (55.0, "D")
    assert [e["exam"] for e in body["national_exams"]] == ["uace"]


@pytest.mark.django_db
def test_performance_grade_distribution(client, performance):
    body = client.get(PERFORMANCE_URL, {"term": performance["term3"].pk}).json()
    levels = {d["level"]: d for d in body["grade_distribution"]}

    assert set(levels) == {"primary", "o_level"}  # no A-level results this term
    o_level = levels["o_level"]
    assert o_level["students"] == 2
    assert [g["grade"] for g in o_level["grades"]] == ["A", "B", "C", "D", "E", "U"]
    counts = {g["grade"]: g["students"] for g in o_level["grades"]}
    assert counts == {"A": 0, "B": 1, "C": 0, "D": 0, "E": 0, "U": 1}
    primary = {g["grade"]: g["students"] for g in levels["primary"]["grades"]}
    assert primary["C5"] == 1


@pytest.mark.django_db
def test_performance_subjects_against_previous_term(client, performance):
    body = client.get(PERFORMANCE_URL, {"term": performance["term3"].pk}).json()
    subjects = {s["code"]: s for s in body["subjects"]}

    maths = subjects["MTC"]
    assert (maths["average_mark"], maths["pass_rate"], maths["results"]) == (55.0, 50.0, 4)
    assert maths["previous_pass_rate"] == 0.0  # 45 and 30 in Term 2
    english = subjects["ENG"]
    assert (english["pass_rate"], english["previous_pass_rate"]) == (100.0, None)


@pytest.mark.django_db
def test_performance_test_results(client, performance):
    body = client.get(PERFORMANCE_URL, {"term": performance["term3"].pk}).json()
    tests = {t["subject"]: t for t in body["tests"]}

    assert tests["Mathematics"] == {
        "id": tests["Mathematics"]["id"], "subject": "Mathematics", "level": "o_level",
        "level_display": "O Level", "test_1_average": 60.0, "test_2_average": 50.0,
        "test_1_pass_rate": 50.0, "test_2_pass_rate": 50.0, "students_assessed": 2,
    }
    assert tests["English"]["test_2_average"] is None


@pytest.mark.django_db
def test_performance_national_exam_pass_rates(client, performance):
    body = client.get(PERFORMANCE_URL, {"term": performance["term3"].pk}).json()
    exams = {e["exam"]: e for e in body["national_exams"]}

    assert set(exams) == {"ple", "uace"}  # no UCE results recorded
    ple = exams["ple"]
    # the 2025 sitting: not the older 2024 one, nor 2027, which is after this year
    assert (ple["year"], ple["sat"], ple["passed"], ple["pass_rate"]) == (2025, 3, 2, 66.7)
    assert {d["division"]: d["candidates"] for d in ple["divisions"]} == \
        {"division_1": 1, "division_4": 1, "ungraded": 1}
    assert (exams["uace"]["pass_rate"], exams["uace"]["divisions"]) == (100.0, [])


@pytest.mark.django_db
def test_performance_campus_with_no_results(client, performance):
    body = client.get(PERFORMANCE_URL, {"term": performance["term3"].pk,
                                        "campus": "buwaate"}).json()

    assert body["summary"]["students_assessed"] == 0
    assert body["summary"]["student_performance"] is None
    assert body["summary"]["syllabus_coverage"] is None
    assert body["subjects"] == body["tests"] == body["grade_distribution"] == []


@pytest.mark.django_db
def test_performance_rejects_an_unknown_section(client, performance):
    response = client.get(PERFORMANCE_URL, {"level": "university"})

    assert response.status_code == 400
    assert "level" in response.json()


@pytest.mark.django_db
def test_performance_returns_404_without_terms(client):
    assert client.get(PERFORMANCE_URL).status_code == 404


@pytest.mark.django_db
def test_result_api_sets_the_grade_from_the_mark(client, maths_test):
    pupil = student("S7")
    response = client.post("/api/academics/assessment-results/", {
        "assessment": maths_test.pk, "student": pupil.pk, "mark": "72.5", "grade": "U",
    }, format="json")

    assert response.status_code == 201
    assert response.json()["grade"] == "B"  # worked out from 72.5, not taken as sent
    assert response.json()["passed"] is True


@pytest.mark.django_db
def test_syllabus_api_rejects_more_topics_covered_than_planned(client, maths_test):
    response = client.post("/api/academics/syllabus-coverage/", {
        "school": maths_test.school.pk, "term": maths_test.term.pk,
        "subject": maths_test.subject.pk, "class_level": "S3",
        "topics_planned": 8, "topics_covered": 9,
    }, format="json")

    assert response.status_code == 400
    assert "topics_covered" in response.json()
