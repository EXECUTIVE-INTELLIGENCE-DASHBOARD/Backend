"""Runs one sync: fetch from a connector, stage every record, then hand them to a loader.

A loader is a function `loader(source, records)` that cleans the staged records, writes
the good ones to the core tables, marks each record LOADED or REJECTED (with reasons),
and returns `(created, updated)` counts.
"""
from django.db import transaction
from django.utils import timezone

from .models import ImportRun, SourceSystem, StagedRecord


def run_sync(connector, loader, source_name):
    """Run a full sync and return its ImportRun. The core tables are written in one
    transaction, so a failed run leaves them as they were."""
    source, _ = SourceSystem.objects.get_or_create(
        code=connector.source_code, defaults={"name": source_name}
    )
    run = ImportRun.objects.create(source=source)
    try:
        records = StagedRecord.objects.bulk_create(
            [
                StagedRecord(run=run, record_type=kind, external_id=external_id, payload=payload)
                for kind, external_id, payload in connector.fetch()
            ],
            batch_size=1000,
        )
        run.received = len(records)

        with transaction.atomic():
            run.created, run.updated = loader(source, records)
        StagedRecord.objects.bulk_update(records, ["status", "errors"], batch_size=500)

        run.rejected = sum(1 for r in records if r.status == StagedRecord.Status.REJECTED)
        run.status = ImportRun.Status.SUCCEEDED
        source.last_synced_at = timezone.now()
        source.save(update_fields=["last_synced_at"])
    except Exception as exc:
        run.status = ImportRun.Status.FAILED
        run.error_message = f"{type(exc).__name__}: {exc}"[:2000]
        raise
    finally:
        run.finished_at = timezone.now()
        run.save()
    return run
