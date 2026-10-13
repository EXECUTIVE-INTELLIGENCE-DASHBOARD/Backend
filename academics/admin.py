from django.contrib import admin

from .models import (
    Student,
    Academic,
    Section,
    GradeResult,
    Homework,
    Attendance,
    Curricular,
    Events,
    Staff,
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
