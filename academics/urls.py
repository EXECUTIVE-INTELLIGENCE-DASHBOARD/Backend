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
urlpatterns=[
    path('8000/academics/', include(router.urls)),
   
]