"""Bookkeeping shared by every loader: grouping staged records by type, marking them
loaded or rejected, skipping duplicates, and writing rows in bulk."""
from collections import defaultdict

from django.utils import timezone

from ..models import StagedRecord

BATCH = 500


class BaseLoad:
    record_order = []  # record types the loader understands, in the order to load them

    def __init__(self, source, records):
        self.source = source
        self.now = timezone.now()
        self.created = 0
        self.updated = 0
        self.by_type = defaultdict(list)
        for record in records:
            self.by_type[record.record_type].append(record)
        for record_type in set(self.by_type) - set(self.record_order):
            for record in self.by_type[record_type]:
                self.reject(record, f"unknown record type '{record_type}'")

    def reject(self, record, *reasons):
        record.status = StagedRecord.Status.REJECTED
        record.errors = list(reasons)

    def loaded(self, record):
        record.status = StagedRecord.Status.LOADED
        record.errors = []

    def unique(self, records):
        """Yield records once per external ID; later copies are rejected as duplicates."""
        seen = set()
        for record in records:
            if record.external_id in seen:
                self.reject(record, "duplicate of an earlier record in this sync")
                continue
            seen.add(record.external_id)
            yield record

    def track(self, row):
        """Stamp a source-tracked row with where it came from."""
        row.source_system = self.source
        row.last_synced_at = self.now

    def save(self, model, to_create, to_update, fields):
        model.objects.bulk_create(to_create, batch_size=BATCH)
        if to_update:
            model.objects.bulk_update(to_update, fields, batch_size=BATCH)
        self.created += len(to_create)
        self.updated += len(to_update)
