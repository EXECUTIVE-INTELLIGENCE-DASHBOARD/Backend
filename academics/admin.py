from django.contrib import admin

from .models import (
    Academic,
    Attendance,
    Curricular,
    Events,
    GradeResult,
    Homework,
    Section,
    Staff,
    Student,
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
