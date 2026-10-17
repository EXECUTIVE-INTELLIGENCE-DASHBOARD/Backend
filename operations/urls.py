from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    EmployeeViewSet,
    HRDashboardView,
    StaffAttendanceViewSet,
    WorkforceUnitViewSet,
)

router = DefaultRouter()
router.register('hr/units', WorkforceUnitViewSet)
router.register('hr/employees', EmployeeViewSet)
router.register('hr/attendance', StaffAttendanceViewSet)
urlpatterns = [
    path('operations/hr/dashboard/', HRDashboardView.as_view(), name='hr-dashboard'),
    path('operations/', include(router.urls)),
]
