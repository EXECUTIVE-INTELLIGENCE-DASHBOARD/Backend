import pytest
from rest_framework.test import APIClient

from academics.models import (
    GRADE_SCALES,
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
)

from .cleaning import CleaningError, normalise_gender, normalise_nationality, parse_date
from .connectors.smis import MockSMISConnector
from .loaders.smis import load_smis
from .models import ImportRun, StagedRecord
from .pipeline import run_sync

SMIS_NAME = "School Management Information System"
PERFORMANCE_TYPES = {"subject", "assessment", "result", "syllabus", "exam_result"}
ALL_MODELS = (School, Term, StudentProfile, Enrolment, Application, Subject, Assessment,
              AssessmentResult, SyllabusCoverage, NationalExamResult)


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
    # performance: repeated results, absent or impossible marks, results and exams for
    # students that were rejected, too many topics covered, PLE aggregate 41, division X
    results_seen, performance = set(), 0
    for kind, external_id, p in records:
        if kind == "result":
            if external_id in results_seen:
                performance += 1
                continue
            results_seen.add(external_id)
            if p["Mark"] in ("ABS", "105") or p["AdmissionNo"] not in students:
                performance += 1
        elif kind == "syllabus":
            performance += int(p["TopicsCovered"]) > int(p["TopicsPlanned"])
        elif kind == "exam_result":
            performance += (p["AdmissionNo"] not in students or p["Division"] == "X"
                            or p["Aggregate"] == "41")
    return (duplicates + len(broken) + orphans + unknown_stage + performance,
            len(records))


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
    # performance: subject levels and categories mapped, every mark graded on its scale
    assert Subject.objects.count() == 20
    for level, scale in GRADE_SCALES.items():
        grades = set(AssessmentResult.objects.filter(assessment__subject__level=level)
                     .values_list("grade", flat=True))
        assert grades and grades <= {grade for _, grade in scale}
    assert set(Assessment.objects.values_list("kind", flat=True)) == \
        {"test_1", "test_2", "end_of_term"}
    assert SyllabusCoverage.objects.exists()
    for model in (Assessment, AssessmentResult, SyllabusCoverage, NationalExamResult):
        assert not model.objects.exclude(source_system=run.source).exists()


@pytest.mark.django_db
def test_running_again_updates_instead_of_duplicating():
    first = sync()
    counts = [m.objects.count() for m in ALL_MODELS]

    second = sync()

    assert [m.objects.count() for m in ALL_MODELS] == counts
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


class TinySMIS:
    """A hand-written SMIS export: one good record of each performance kind plus the
    problems the loader must catch."""

    source_code = "smis"

    def fetch(self):
        yield "school", "SEC", {"SchoolCode": "SEC", "SchoolName": "Secondary", "Campus": "Kibuli",
                                "Capacity": "100", "Section": "Sec"}
        yield "term", "2026-T3", {"TermCode": "2026-T3", "AcademicYear": "2026", "Term": "T3",
                                  "StartDate": "14/09/2026", "EndDate": "04/12/2026"}
        for number in ("A1", "A2", "A3"):
            yield "student", number, {"AdmissionNo": number, "Sex": "F", "Nationality": "UG",
                                      "DOB": "", "HomeSchool": "SEC"}
        yield "subject", "o_level:MTC", {"SubjectCode": "MTC", "SubjectName": "Mathematics",
                                         "Level": "O-Level", "Category": "Sciences"}
        yield "assessment", "AS1", {"AssessmentID": "AS1", "SchoolCode": "SEC",
                                    "TermCode": "2026-T3", "Class": "S3", "SubjectCode": "mtc",
                                    "Kind": "BOT", "DateHeld": "30 Sep 2026"}
        yield "assessment", "AS2", {"AssessmentID": "AS2", "SchoolCode": "SEC",
                                    "TermCode": "2026-T3", "Class": "Baby", "SubjectCode": "MTC",
                                    "Kind": "BOT", "DateHeld": ""}
        for result_id, number, mark in (("R1", "A1", "67.5%"), ("R2", "A2", "ABS"),
                                        ("R3", "A3", "105")):
            yield "result", result_id, {"ResultID": result_id, "AssessmentID": "AS1",
                                        "AdmissionNo": number, "Mark": mark}
        yield "syllabus", "C1", {"CoverageID": "C1", "SchoolCode": "SEC", "TermCode": "2026-T3",
                                 "Class": "S3", "SubjectCode": "MTC", "TopicsPlanned": "10",
                                 "TopicsCovered": "12"}
        exam = {"SchoolCode": "SEC", "Year": "2025", "Aggregate": "", "PrincipalPasses": ""}
        yield "exam_result", "N1", {**exam, "ExamResultID": "N1", "AdmissionNo": "A1",
                                    "Exam": "U.C.E", "Division": "DIV II"}
        yield "exam_result", "N2", {**exam, "ExamResultID": "N2", "AdmissionNo": "A2",
                                    "Exam": "P.L.E", "Division": "1", "Aggregate": "41"}
        yield "exam_result", "N3", {**exam, "ExamResultID": "N3", "AdmissionNo": "A3",
                                    "Exam": "UACE", "PrincipalPasses": "1"}


@pytest.mark.django_db
def test_performance_records_are_cleaned_graded_or_rejected_with_a_reason():
    run = run_sync(TinySMIS(), load_smis, SMIS_NAME)
    errors = {r.external_id: " ".join(r.errors)
              for r in StagedRecord.objects.filter(run=run, status=StagedRecord.Status.REJECTED)}

    result = AssessmentResult.objects.get()
    assert (float(result.mark), result.grade, result.passed) == (67.5, "C", True)
    assert result.assessment.kind == "test_1"  # "BOT"
    assert "class 'Baby' has no graded subjects" in errors["AS2"]
    assert "absent" in errors["R2"]
    assert "outside 0 to 100" in errors["R3"]
    assert "more than the 10 planned" in errors["C1"]
    assert "PLE aggregate 41" in errors["N2"]

    uce = NationalExamResult.objects.get(exam="uce")
    assert (uce.division, uce.passed) == ("division_2", True)
    uace = NationalExamResult.objects.get(exam="uace")
    assert (uace.principal_passes, uace.passed) == (1, False)  # needs two principal passes
