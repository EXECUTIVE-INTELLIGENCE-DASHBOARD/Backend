from django.contrib import admin

from .models import ImportRun, SourceSystem, StagedRecord


@admin.register(SourceSystem)
class SourceSystemAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "mode", "last_synced_at")


@admin.register(ImportRun)
class ImportRunAdmin(admin.ModelAdmin):
    list_display = ("source", "status", "started_at", "received", "created", "updated", "rejected")
    list_filter = ("source", "status")


@admin.register(StagedRecord)
class StagedRecordAdmin(admin.ModelAdmin):
    list_display = ("record_type", "external_id", "status", "run")
    list_filter = ("status", "record_type", "run__source")
    search_fields = ("external_id",)
