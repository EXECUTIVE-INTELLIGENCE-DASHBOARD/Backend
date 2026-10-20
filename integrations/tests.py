from datetime import date

import pytest

from .cleaning import (
    CleaningError,
    clean_text,
    map_choice,
    normalise_campus,
    normalise_gender,
    normalise_nationality,
    parse_date,
    parse_term_number,
)
from .models import ImportRun, SourceSystem, StagedRecord


@pytest.fixture
def smis():
    return SourceSystem.objects.create(code="smis", name="School Management Information System")


@pytest.mark.django_db
def test_source_system_starts_in_mock_mode(smis):
    assert smis.mode == SourceSystem.Mode.MOCK
    assert smis.last_synced_at is None
    assert str(smis) == "School Management Information System (Mock)"


@pytest.mark.django_db
def test_import_run_starts_running_with_zero_counts(smis):
    run = ImportRun.objects.create(source=smis)

    assert run.status == ImportRun.Status.RUNNING
    assert (run.received, run.created, run.updated, run.rejected) == (0, 0, 0, 0)


@pytest.mark.django_db
def test_staged_record_keeps_the_raw_payload_and_errors(smis):
    run = ImportRun.objects.create(source=smis)
    record = StagedRecord.objects.create(
        run=run, record_type="student", external_id="ADM-001",
        payload={"Gender": "F", "DOB": "17/10/2015"},
    )

    record.refresh_from_db()
    assert record.payload == {"Gender": "F", "DOB": "17/10/2015"}
    assert record.status == StagedRecord.Status.PENDING
    assert record.errors == []


@pytest.mark.django_db
def test_deleting_a_run_removes_its_staged_records(smis):
    run = ImportRun.objects.create(source=smis)
    StagedRecord.objects.create(run=run, record_type="student", external_id="1", payload={})

    run.delete()

    assert StagedRecord.objects.count() == 0


# --- Cleaning helpers -------------------------------------------------------------

def test_clean_text_trims_and_collapses_spaces():
    assert clean_text("  Primary   Kibuli \n") == "Primary Kibuli"
    assert clean_text(None) == ""


@pytest.mark.parametrize("raw", [
    "2015-10-17", "17/10/2015", "17-10-2015", "17.10.2015", "17 Oct 2015", "17 October 2015",
    " 17/10/2015 ", date(2015, 10, 17),
])
def test_parse_date_reads_common_formats(raw):
    assert parse_date(raw) == date(2015, 10, 17)


@pytest.mark.parametrize("raw", ["", None, "31/02/2015", "next week", "10/17/2015"])
def test_parse_date_rejects_what_it_cannot_read(raw):
    with pytest.raises(CleaningError):
        parse_date(raw, "date of birth")


@pytest.mark.parametrize("raw,expected", [
    ("M", "male"), ("male", "male"), ("Boy", "male"),
    ("f", "female"), (" FEMALE ", "female"), ("girl", "female"),
])
def test_normalise_gender(raw, expected):
    assert normalise_gender(raw) == expected


def test_normalise_gender_rejects_unknown_values():
    with pytest.raises(CleaningError, match="gender 'X' is not recognised"):
        normalise_gender("X")


@pytest.mark.parametrize("raw,expected", [
    ("KIBULI MAIN ", "kibuli"), ("Kibuli Main Campus", "kibuli"), ("kibuli", "kibuli"),
    ("Buwaate Campus", "buwaate"), ("Buwate", "buwaate"),
    ("Annex / Preschool Branch", "annex"), ("annex preschool", "annex"),
])
def test_normalise_campus(raw, expected):
    assert normalise_campus(raw) == expected


def test_normalise_campus_rejects_unknown_campus():
    with pytest.raises(CleaningError):
        normalise_campus("Entebbe")


@pytest.mark.parametrize("raw,expected", [
    ("UG", "Ugandan"), ("uganda", "Ugandan"), ("Ugandan", "Ugandan"),
    ("KE", "Kenyan"), ("Rwanda", "Rwandese"), ("South Sudan", "South Sudanese"),
    ("nigerian", "Nigerian"),  # not in the table: kept, in title case
])
def test_normalise_nationality(raw, expected):
    assert normalise_nationality(raw) == expected


def test_normalise_nationality_rejects_missing_value():
    with pytest.raises(CleaningError):
        normalise_nationality("  ")


@pytest.mark.parametrize("raw,expected", [("Term 3", 3), ("T1", 1), ("III", 3), (2, 2), ("2", 2)])
def test_parse_term_number(raw, expected):
    assert parse_term_number(raw) == expected


@pytest.mark.parametrize("raw", ["Term 4", "0", "summer", ""])
def test_parse_term_number_rejects_other_values(raw):
    with pytest.raises(CleaningError):
        parse_term_number(raw)


def test_map_choice_uses_default_for_unrecognised_values():
    reasons = {"financial": ["fees", "financial"], "transfer": ["transfer", "transferred"]}

    assert map_choice("Fees", reasons, "reason") == "financial"
    assert map_choice("Relocated abroad", reasons, "reason", default="other") == "other"
    with pytest.raises(CleaningError):
        map_choice("Relocated abroad", reasons, "reason")
