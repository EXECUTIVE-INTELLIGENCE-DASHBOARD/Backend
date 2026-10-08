from rest_framework import viewsets

from .models import Student
from .serializers import LocationSerializer, StudentSerializer


# Create your views here.
class StudentViewSet(viewsets.ModelViewSet):
    serializer_class = StudentSerializer
    queryset = Student.objects.all()

class LocationViewSet(viewsets.ModelViewSet):
    serializer_class = LocationSerializer
    queryset = Student.objects.all()



