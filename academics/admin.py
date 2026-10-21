from django.contrib import admin

from .models import (
    Academic,
    Application,
    Assessment,
    AssessmentResult,
    Attendance,
    Curricular,
    Enrolment,
    Events,
    GradeResult,
    Homework,
    NationalExamResult,
    School,
    Section,
    Staff,
    Student,
    StudentProfile,
    Subject,
    SyllabusCoverage,
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
    list_display = ("name", "campus", "level", "capacity", "minimum_enrolment")
    list_filter = ("campus", "level")


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


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "level", "category")
    list_filter = ("level", "category")
    search_fields = ("name", "code")


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ("subject", "kind", "class_level", "school", "term", "held_on")
    list_filter = ("term", "school", "kind", "subject__level")


@admin.register(AssessmentResult)
class AssessmentResultAdmin(admin.ModelAdmin):
    list_display = ("student", "assessment", "mark", "grade")
    list_filter = ("assessment__term", "assessment__kind", "grade")
    search_fields = ("student__student_number",)
    list_select_related = ("student", "assessment__subject", "assessment__term")


@admin.register(SyllabusCoverage)
class SyllabusCoverageAdmin(admin.ModelAdmin):
    list_display = ("subject", "class_level", "school", "term", "topics_covered", "topics_planned")
    list_filter = ("term", "school")


@admin.register(NationalExamResult)
class NationalExamResultAdmin(admin.ModelAdmin):
    list_display = ("student", "exam", "year", "division", "aggregate", "principal_passes",
                    "passed")
    list_filter = ("exam", "year", "division", "passed", "school")
    search_fields = ("student__student_number",)
