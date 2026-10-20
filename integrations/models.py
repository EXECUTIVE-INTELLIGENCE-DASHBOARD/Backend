from django.db import models


class SourceSystem(models.Model):
    """An outside system data comes from (SMIS, Sage, the HR system) or manual entry.
    Each one runs as a mock until its real connection is available."""

    class Mode(models.TextChoices):
        MOCK = "mock", "Mock"  # realistic generated data, for building and demos
        LIVE = "live", "Live"  # the real system

    code = models.SlugField(max_length=30, unique=True)  # e.g. "smis", "sage"
    name = models.CharField(max_length=100)  # e.g. "School Management Information System"
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.MOCK)
    last_synced_at = models.DateTimeField(null=True, blank=True)  # end of the last successful run

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_mode_display()})"


class ImportRun(models.Model):
    """One sync from a source system, with counts of what happened to its records."""

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"  # finished; some records may still be rejected
        FAILED = "failed", "Failed"  # stopped part-way; see error_message

    source = models.ForeignKey(SourceSystem, on_delete=models.PROTECT, related_name="runs")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    received = models.PositiveIntegerField(default=0)  # records the source sent
    created = models.PositiveIntegerField(default=0)  # new rows written to the core tables
    updated = models.PositiveIntegerField(default=0)  # existing rows changed
    rejected = models.PositiveIntegerField(default=0)  # records that failed cleaning
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.source.code} run {self.pk} ({self.get_status_display()})"


class StagedRecord(models.Model):
    """A record exactly as the source sent it, kept so nothing is lost: loaded records
    can be traced back, and rejected ones keep their reasons until they are fixed."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"  # received, not cleaned yet
        LOADED = "loaded", "Loaded"  # cleaned and written to the core tables
        REJECTED = "rejected", "Rejected"  # failed cleaning; see errors

    run = models.ForeignKey(ImportRun, on_delete=models.CASCADE, related_name="records")
    record_type = models.CharField(max_length=50)  # what the record is, e.g. "student"
    external_id = models.CharField(max_length=100)  # the record's ID in the source system
    payload = models.JSONField()  # the raw record, untouched
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    errors = models.JSONField(default=list, blank=True)  # reasons, if rejected
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["run", "id"]
        indexes = [models.Index(fields=["run", "status"])]

    def __str__(self):
        return f"{self.record_type} {self.external_id} ({self.get_status_display()})"
