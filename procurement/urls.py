from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ProcurementTransactionViewSet, VendorViewSet

router = DefaultRouter()
router.register('vendors', VendorViewSet)
router.register('procurement-transactions', ProcurementTransactionViewSet)

urlpatterns = [
    path('procurement/', include(router.urls)),
]