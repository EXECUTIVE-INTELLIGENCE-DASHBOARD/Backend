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
class StudentViewSet(viewsets.ModelViewSet):
    serializer_class = StudentSerializer
    queryset = Student.objects.all()

class AcademicViewSet(viewsets.ModelViewSet):
    serializer_class = AcademicSerializer
    queryset = Academic.objects.all()

class SectionViewSet(viewsets.ModelViewSet):
    serializer_class = SectionSerializer
    queryset = Section.objects.all()

class GradeResultViewSet(viewsets.ModelViewSet):
    serializer_class = GradeResultSerializer
    queryset = GradeResult.objects.all()

class HomeworkViewSet(viewsets.ModelViewSet):
    serializer_class = HomeworkSerializer
    queryset = Homework.objects.all()

class AttendanceViewSet(viewsets.ModelViewSet):
    serializer_class = AttendanceSerializer
    queryset = Attendance.objects.all()

class CurricularViewSet(viewsets.ModelViewSet):
    serializer_class = CurricularSerializer
    queryset = Curricular.objects.all()

class EventsViewSet(viewsets.ModelViewSet):
    serializer_class = EventsSerializer
    queryset = Events.objects.all()

class StaffViewSet(viewsets.ModelViewSet):
    serializer_class = StaffSerializer
    queryset = Staff.objects.all()    

