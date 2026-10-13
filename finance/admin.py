from django.contrib import admin

from .models import (
    FiscalYear,
    Department,
    DepartmentBudget,
    Creditor,
    Liability,
    RevenueRecord,
    MonthlyRevenueTarget,
)

admin.site.register([
    FiscalYear,
    Department,
    DepartmentBudget,
    Creditor,
    Liability,
    RevenueRecord,
    MonthlyRevenueTarget,
])
