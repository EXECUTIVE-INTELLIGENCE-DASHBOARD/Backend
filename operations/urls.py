from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AssetDashboardView,
    AssetViewSet,
    EmployeeViewSet,
    FacilityViewSet,
    HRDashboardView,
    StaffAttendanceViewSet,
    WorkforceUnitViewSet,
)

router = DefaultRouter()
router.register('hr/units', WorkforceUnitViewSet)
router.register('hr/employees', EmployeeViewSet)
router.register('hr/attendance', StaffAttendanceViewSet)
router.register('facilities', FacilityViewSet)
router.register('assets', AssetViewSet)
urlpatterns = [
    path('operations/hr/dashboard/', HRDashboardView.as_view(), name='hr-dashboard'),
    # listed before the router so "dashboard" is not read as an asset id
    path('operations/assets/dashboard/', AssetDashboardView.as_view(), name='asset-dashboard'),
    path('operations/', include(router.urls)),
]
