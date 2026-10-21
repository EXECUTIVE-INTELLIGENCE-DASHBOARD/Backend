from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BudgetDashboardView,
    DailySalesViewSet,
    InventoryDashboardView,
    OutletBudgetViewSet,
    OutletExpenseViewSet,
    OutletViewSet,
    SalesDashboardView,
    StockItemViewSet,
)

router = DefaultRouter()
router.register('outlets', OutletViewSet)
router.register('daily-sales', DailySalesViewSet)
router.register('stock-items', StockItemViewSet)
router.register('budgets', OutletBudgetViewSet)
router.register('expenses', OutletExpenseViewSet)
urlpatterns = [
    path('services/sales/dashboard/', SalesDashboardView.as_view(), name='sales-dashboard'),
    path(
        'services/inventory/dashboard/',
        InventoryDashboardView.as_view(),
        name='inventory-dashboard',
    ),
    path('services/budget/dashboard/', BudgetDashboardView.as_view(), name='budget-dashboard'),
    path('services/', include(router.urls)),
]
