import pytest

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
