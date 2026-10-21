
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path("", RedirectView.as_view(url="/api/docs/", permanent=False)),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url="/api/schema/"), name="swagger-ui"),
    path("api/redoc/",SpectacularRedocView.as_view(url="/api/schema/"),name="redoc",),
    path("api/", include("core.urls")),
    path("api/", include("academics.urls")),
    path("api/", include("finance.urls")),
    path("api/", include("procurement.urls")),
    path("api/", include("operations.urls")),
    path("api/", include("services.urls")),
]
