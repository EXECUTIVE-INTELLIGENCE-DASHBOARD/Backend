from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import LocationViewSet, StudentViewSet

router = DefaultRouter()
router.register('students', StudentViewSet)
router.register('locations', LocationViewSet,'location')
urlpatterns=[
    path('api/academics/', include(router.urls)),

    
]