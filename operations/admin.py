from django.contrib import admin

from .models import Employee, StaffAttendance, WorkforceUnit


@admin.register(WorkforceUnit)
class WorkforceUnitAdmin(admin.ModelAdmin):
    list_display = ("name", "staff_category", "campus", "location")
    list_filter = ("staff_category", "campus")
    search_fields = ("name",)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("full_name", "staff_number", "unit", "employment_type", "is_active")
    list_filter = ("unit", "employment_type", "is_active")
    search_fields = ("full_name", "staff_number")


@admin.register(StaffAttendance)
class StaffAttendanceAdmin(admin.ModelAdmin):
    list_display = ("employee", "date", "status")
    list_filter = ("status", "date")
    search_fields = ("employee__full_name", "employee__staff_number")
