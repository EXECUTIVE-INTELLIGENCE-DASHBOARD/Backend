from django.contrib import admin

from .models import (
    Academic,
    Application,
    Attendance,
    Curricular,
    Enrolment,
    Events,
    GradeResult,
    Homework,
    School,
    Section,
    Staff,
    Student,
    StudentProfile,
    Term,
)

admin.site.register([
    Student,
    Academic,
    Section,
    GradeResult,
    Homework,
    Attendance,
    Curricular,
    Events,
    Staff,
])


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "campus", "capacity", "minimum_enrolment")
    list_filter = ("campus",)


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ("__str__", "start_date", "end_date")


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("student_number", "gender", "nationality")
    list_filter = ("gender", "nationality")
    search_fields = ("student_number",)


@admin.register(Enrolment)
class EnrolmentAdmin(admin.ModelAdmin):
    list_display = ("student", "school", "term", "status", "withdrawal_reason", "at_risk")
    list_filter = ("term", "school", "status", "withdrawal_reason", "at_risk")
    search_fields = ("student__student_number",)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("reference", "school", "term", "stage", "applied_on")
    list_filter = ("term", "school", "stage")
    search_fields = ("reference",)
