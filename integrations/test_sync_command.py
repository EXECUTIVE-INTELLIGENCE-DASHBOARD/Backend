from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from academics.models import StudentProfile

from .models import ImportRun, SourceSystem
from .sources import all_sources


def test_the_smis_source_is_registered():
    assert "smis" in all_sources()


@pytest.mark.django_db
def test_sync_source_runs_a_sync_and_reports_it():
    out = StringIO()

    call_command("sync_source", "smis", "--scale", "0.05", stdout=out)

    run = ImportRun.objects.get()
    assert run.status == ImportRun.Status.SUCCEEDED
    assert StudentProfile.objects.exists()
    report = out.getvalue()
    assert report.startswith(f"smis: received {run.received}, created {run.created}")
    assert "rejected" in report and "duplicate of an earlier record" in report


@pytest.mark.django_db
def test_sync_source_rejects_unknown_sources():
    with pytest.raises(CommandError, match="unknown source: sage"):
        call_command("sync_source", "sage")


@pytest.mark.django_db
def test_sync_source_refuses_live_mode_without_a_live_connector():
    SourceSystem.objects.create(code="smis", name="SMIS", mode=SourceSystem.Mode.LIVE)

    with pytest.raises(CommandError, match="no live connector yet"):
        call_command("sync_source", "smis", "--scale", "0.05")
    assert not ImportRun.objects.exists()
