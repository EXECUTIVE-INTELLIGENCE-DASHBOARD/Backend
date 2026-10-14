from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AcademicViewSet,
    AttendanceViewSet,
    CurricularViewSet,
    EventsViewSet,
    GradeResultViewSet,
    HomeworkViewSet,
    SectionViewSet,
    StaffViewSet,
    StudentViewSet,
)

router = DefaultRouter()
router.register('students', StudentViewSet)
router.register('academics', AcademicViewSet)
router.register('sections', SectionViewSet)
router.register('grade-results', GradeResultViewSet)
router.register('homework', HomeworkViewSet)
router.register('attendance', AttendanceViewSet)
router.register('curricular', CurricularViewSet)
router.register('events', EventsViewSet)
router.register('staff', StaffViewSet)
urlpatterns=[
    path('academics/', include(router.urls)),
                                                                  
]