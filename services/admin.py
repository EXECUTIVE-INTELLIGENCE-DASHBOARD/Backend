from django.contrib import admin

from .models import DailySales, Outlet, OutletBudget, OutletExpense, StockItem


@admin.register(Outlet)
class OutletAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "business_type")


@admin.register(DailySales)
class DailySalesAdmin(admin.ModelAdmin):
    list_display = ("outlet", "date", "revenue", "cost_of_sales", "transactions")
    list_filter = ("outlet",)
    date_hierarchy = "date"


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = ("name", "outlet", "on_hand", "minimum_level", "unit_cost")
    list_filter = ("outlet",)
    search_fields = ("name",)


@admin.register(OutletBudget)
class OutletBudgetAdmin(admin.ModelAdmin):
    list_display = ("outlet", "financial_year", "allocated")
    list_filter = ("financial_year", "outlet")


@admin.register(OutletExpense)
class OutletExpenseAdmin(admin.ModelAdmin):
    list_display = ("outlet", "date", "amount", "description")
    list_filter = ("outlet",)
    date_hierarchy = "date"
