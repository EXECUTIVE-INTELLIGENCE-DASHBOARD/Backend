from django.urls import include, path

from core.oidc_views import (
    current_user,
    greenhill_callback,
    greenhill_login,
    greenhill_logout,
)
from core.views import health

urlpatterns = [
    path("health/", health, name="health"),
    path("auth/login/", greenhill_login, name="greenhill_login"),
    path("auth/callback/", greenhill_callback, name="greenhill_callback"),
    path("auth/me/", current_user, name="current_user"),
    path("auth/logout/", greenhill_logout, name="greenhill_logout"),
    path("api/", include("academics.urls")),
]
