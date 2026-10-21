import pytest
from rest_framework.test import APIClient

from academics.models import Application, Enrolment, School, StudentProfile, Term

from .cleaning import CleaningError, normalise_gender, normalise_nationality, parse_date
from .connectors.smis import MockSMISConnector
from .loaders.smis import load_smis
from .models import ImportRun, StagedRecord
from .pipeline import run_sync

SMIS_NAME = "School Management Information System"
PERFORMANCE_TYPES = {"subject", "assessment", "result", "syllabus", "exam_result"}


def sync(scale=0.05):
    return run_sync(MockSMISConnector(scale=scale), load_smis, SMIS_NAME)


def expected_rejections():
    """Work out, from the mock's own output, which records the loader should reject."""
    records = list(MockSMISConnector(scale=0.05).fetch())
    students, broken, seen, duplicates = {}, set(), set(), 0
    for kind, external_id, payload in records:
        if kind != "student":
            continue
        if external_id in seen:
            duplicates += 1
            continue
        seen.add(external_id)
        try:
            normalise_gender(payload["Sex"])
            normalise_nationality(payload["Nationality"])
            parse_date(payload["DOB"])
            students[external_id] = payload
        except CleaningError:
            broken.add(external_id)
    orphans = sum(1 for kind, _, p in records
                  if kind == "enrolment" and p["AdmissionNo"] not in students)
    unknown_stage = sum(1 for kind, _, p in records
                        if kind == "application" and p["Stage"] == "Waitlisted")
    # performance records: the loader does not handle these yet
    performance = sum(1 for kind, _, _ in records if kind in PERFORMANCE_TYPES)
    return duplicates + len(broken) + orphans + unknown_stage + performance, len(records)


@pytest.mark.django_db
def test_sync_succeeds_and_every_record_is_accounted_for():
    run = sync()
    rejected, received = expected_rejections()

    assert run.status == ImportRun.Status.SUCCEEDED
    assert run.received == received
    assert run.rejected == rejected
    assert run.created == received - rejected  # first run: everything loaded is new
    assert run.updated == 0
    assert run.source.last_synced_at is not None


@pytest.mark.django_db
def test_rejected_records_keep_their_reasons():
    run = sync()
    rejected = StagedRecord.objects.filter(run=run, status=StagedRecord.Status.REJECTED)

    assert rejected.exists()
    assert all(record.errors for record in rejected)
    reasons = " ".join(" ".join(record.errors) for record in rejected)
    assert "duplicate of an earlier record" in reasons
    assert "is not known" in reasons  # enrolments for students SMIS doesn't list
    assert "stage 'Waitlisted' is not recognised" in reasons


@pytest.mark.django_db
def test_loaded_rows_are_clean_and_traceable():
    run = sync()

    assert set(School.objects.values_list("campus", flat=True)) <= {"kibuli", "buwaate", "annex"}
    # "Pre-primary", "Sec", "O & A Level" and the like were mapped onto our levels
    assert set(School.objects.values_list("level", flat=True)) == \
        {"nursery", "primary", "secondary"}
    assert set(StudentProfile.objects.values_list("gender", flat=True)) == {"male", "female"}
    assert not StudentProfile.objects.filter(nationality__in=["UG", "uganda", "KE"]).exists()
    assert Term.objects.count() == 4
    for model in (StudentProfile, Enrolment, Application):
        assert not model.objects.exclude(source_system=run.source).exists()
        assert not model.objects.filter(external_id="").exists()
    # free-text reasons were mapped; the unclear one became "other"
    reasons = set(Enrolment.objects.filter(status="withdrawn")
                  .values_list("withdrawal_reason", flat=True))
    assert reasons <= {"financial", "transfer", "death", "academic_performance", "other"}
    assert "other" in reasons


@pytest.mark.django_db
def test_running_again_updates_instead_of_duplicating():
    first = sync()
    counts = [m.objects.count() for m in (School, Term, StudentProfile, Enrolment, Application)]

    second = sync()

    assert [m.objects.count() for m in (School, Term, StudentProfile, Enrolment, Application)] \
        == counts
    assert second.created == 0
    assert second.updated == first.created


@pytest.mark.django_db
def test_a_hand_entered_student_is_taken_over_by_smis():
    admission_no = next(
        external_id for kind, external_id, p in MockSMISConnector(scale=0.05).fetch()
        if kind == "student" and p["Sex"]
    )
    by_hand = StudentProfile.objects.create(
        student_number=admission_no, gender="male", nationality="Ugandan"
    )

    run = sync()

    by_hand.refresh_from_db()
    assert by_hand.source_system == run.source
    assert by_hand.external_id == admission_no
    assert StudentProfile.objects.filter(student_number=admission_no).count() == 1


@pytest.mark.django_db
def test_a_failed_run_leaves_the_tables_untouched():
    def broken_loader(source, records):
        load_smis(source, records)
        raise RuntimeError("something went wrong part-way")

    with pytest.raises(RuntimeError):
        run_sync(MockSMISConnector(scale=0.05), broken_loader, SMIS_NAME)

    run = ImportRun.objects.get()
    assert run.status == ImportRun.Status.FAILED
    assert "something went wrong" in run.error_message
    assert StudentProfile.objects.count() == 0
    assert Enrolment.objects.count() == 0


@pytest.mark.django_db
def test_dashboards_work_on_synced_data():
    sync()
    client = APIClient()

    enrollment = client.get("/api/academics/enrollment/dashboard/").json()
    retention = client.get("/api/academics/retention/dashboard/").json()

    current = Term.objects.get(academic_year="2026", number=3)
    active = Enrolment.objects.filter(term=current, status="active").count()
    assert enrollment["term"]["id"] == current.pk
    assert enrollment["summary"]["total_active_enrolment"] == active
    assert retention["academic_year"] == "2026"
    assert retention["summary"]["re_enrolment_rate"] is not None


def test_mock_smis_produces_performance_records():
    connector = MockSMISConnector(scale=0.05)
    records = list(connector.fetch())
    by_kind = {}
    for kind, _, payload in records:
        by_kind.setdefault(kind, []).append(payload)

    assert PERFORMANCE_TYPES <= set(by_kind)
    assert len(by_kind["subject"]) == 20  # 4 primary, 7 O level, 9 A level
    # only P4-P7 and S1-S6 sit graded subjects; nursery and P1-P3 do not
    classes = {p["Class"] for p in by_kind["assessment"]}
    assert classes <= {"P4", "P5", "P6", "P7", "S1", "S2", "S3", "S4", "S5", "S6"}
    # every result points at an assessment that exists
    assessments = {p["AssessmentID"] for p in by_kind["assessment"]}
    assert all(p["AssessmentID"] in assessments for p in by_kind["result"])
    # national exams are sat by last year's P7, S4 and S6
    exams = {p["Exam"].upper().replace(".", "") for p in by_kind["exam_result"]}
    assert exams <= {"PLE", "UCE", "UACE", "O LEVEL", "A LEVEL"}


def test_performance_records_leave_the_earlier_records_unchanged():
    """Adding performance data must not shift the enrolment numbers already on Neon."""
    records = list(MockSMISConnector(scale=0.05).fetch())
    first_performance = next(i for i, (kind, _, _) in enumerate(records)
                             if kind in PERFORMANCE_TYPES)

    assert all(kind not in PERFORMANCE_TYPES for kind, _, _ in records[:first_performance])
    assert {kind for kind, _, _ in records[:first_performance]} == \
        {"school", "term", "student", "enrolment", "application"}
