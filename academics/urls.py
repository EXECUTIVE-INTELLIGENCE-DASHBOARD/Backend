from django.urls import path,include
from rest_framework.routers import DefaultRouter
from academics.views import StudentViewSet
from .views import LocationViewSet, StudentViewSet


router = DefaultRouter()
router.register('students', StudentViewSet)
router.register('locations', LocationViewSet,'location')
urlpatterns=[
    path('api/academics/', include(router.urls)),

    
]