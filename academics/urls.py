from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AcademicViewSet,
    ApplicationViewSet,
    AssessmentResultViewSet,
    AssessmentViewSet,
    AttendanceViewSet,
    CurricularViewSet,
    EnrollmentDashboardView,
    EnrolmentViewSet,
    EventsViewSet,
    GradeResultViewSet,
    HomeworkViewSet,
    NationalExamResultViewSet,
    PerformanceDashboardView,
    RetentionDashboardView,
    SchoolViewSet,
    SectionViewSet,
    StaffViewSet,
    StudentProfileViewSet,
    StudentViewSet,
    SubjectViewSet,
    SyllabusCoverageViewSet,
    TermViewSet,
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
router.register('schools', SchoolViewSet)
router.register('terms', TermViewSet)
router.register('student-profiles', StudentProfileViewSet)
router.register('enrolments', EnrolmentViewSet)
router.register('applications', ApplicationViewSet)
router.register('subjects', SubjectViewSet)
router.register('assessments', AssessmentViewSet)
router.register('assessment-results', AssessmentResultViewSet)
router.register('syllabus-coverage', SyllabusCoverageViewSet)
router.register('national-exam-results', NationalExamResultViewSet)
urlpatterns=[
    path(
        'academics/enrollment/dashboard/',
        EnrollmentDashboardView.as_view(),
        name='enrollment-dashboard',
    ),
    path(
        'academics/retention/dashboard/',
        RetentionDashboardView.as_view(),
        name='retention-dashboard',
    ),
    path(
        'academics/performance/dashboard/',
        PerformanceDashboardView.as_view(),
        name='performance-dashboard',
    ),
    path('academics/', include(router.urls)),
                                                                  
]