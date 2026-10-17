from drf_spectacular.utils import extend_schema
from rest_framework import viewsets

from .models import (
    Academic,
    Attendance,
    Curricular,
    Events,
    GradeResult,
    Homework,
    Section,
    Staff,
    Student,
)
from .serializers import (
    AcademicSerializer,
    AttendanceSerializer,
    CurricularSerializer,
    EventsSerializer,
    GradeResultSerializer,
    HomeworkSerializer,
    SectionSerializer,
    StaffSerializer,
    StudentSerializer,
)


# Create your views here.
@extend_schema(tags=["Academics - Students"])
class StudentViewSet(viewsets.ModelViewSet):
    serializer_class = StudentSerializer
    queryset = Student.objects.all()

@extend_schema(tags=["Academics - Performance"])
class AcademicViewSet(viewsets.ModelViewSet):
    serializer_class = AcademicSerializer
    queryset = Academic.objects.all()

@extend_schema(tags=["Academics - Students"])
class SectionViewSet(viewsets.ModelViewSet):
    serializer_class = SectionSerializer
    queryset = Section.objects.all()

@extend_schema(tags=["Academics - Performance"])
class GradeResultViewSet(viewsets.ModelViewSet):
    serializer_class = GradeResultSerializer
    queryset = GradeResult.objects.all()

@extend_schema(tags=["Academics - Performance"])
class HomeworkViewSet(viewsets.ModelViewSet):
    serializer_class = HomeworkSerializer
    queryset = Homework.objects.all()

@extend_schema(tags=["Academics - Students"])
class AttendanceViewSet(viewsets.ModelViewSet):
    serializer_class = AttendanceSerializer
    queryset = Attendance.objects.all()

@extend_schema(tags=["Academics - Co-Curricular"])
class CurricularViewSet(viewsets.ModelViewSet):
    serializer_class = CurricularSerializer
    queryset = Curricular.objects.all()

@extend_schema(tags=["Academics - Co-Curricular"])
class EventsViewSet(viewsets.ModelViewSet):
    serializer_class = EventsSerializer
    queryset = Events.objects.all()

@extend_schema(tags=["Academics - Staff"])
class StaffViewSet(viewsets.ModelViewSet):
    serializer_class = StaffSerializer
    queryset = Staff.objects.all()    

