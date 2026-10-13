from django.contrib import admin

from .models import (
    Creditor,
    Department,
    DepartmentBudget,
    FiscalYear,
    Liability,
    MonthlyRevenueTarget,
    RevenueRecord,
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
