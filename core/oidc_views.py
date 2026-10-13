cat > core/oidc_views.py <<'PY'
import os

from authlib.integrations.django_client import OAuth
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

oauth = OAuth()

oauth.register(
    name="greenhill",
    client_id=os.environ.get("GREENHILL_OIDC_CLIENT_ID", ""),
    client_secret=os.environ.get("GREENHILL_OIDC_CLIENT_SECRET", ""),
    server_metadata_url=os.environ.get(
        "GREENHILL_OIDC_DISCOVERY_URL",
        "https://greenhill-auth-backend2.onrender.com/o/.well-known/openid-configuration",
    ),
    client_kwargs={"scope": "openid email profile eid"},
)


@require_GET
def greenhill_login(request):
    if not settings.GREENHILL_OIDC_CLIENT_ID:
        return JsonResponse(
            {"error": "GreenHill OIDC client ID is not configured."},
            status=503,
        )

    callback_url = request.build_absolute_uri(
        reverse("greenhill_callback")
    )
    return oauth.greenhill.authorize_redirect(request, callback_url)


@require_GET
def greenhill_callback(request):
    try:
        token = oauth.greenhill.authorize_access_token(request)
        userinfo = token.get("userinfo")

        if not userinfo:
            return JsonResponse(
                {"error": "GreenHill did not return verified user information."},
                status=401,
            )

        email = (userinfo.get("email") or "").strip().lower()
        subject = userinfo.get("sub")

        if not subject or not email.endswith("@greenhillacademy.ac.ug"):
            return JsonResponse(
                {"error": "A valid GreenHill Academy account is required."},
                status=403,
            )

        User = get_user_model()
        username = f"gh_{subject}"

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "first_name": userinfo.get("given_name", ""),
                "last_name": userinfo.get("family_name", ""),
            },
        )

        # Refresh basic identity information from the OIDC provider.
        changed_fields = []
        for field, value in (
            ("email", email),
            ("first_name", userinfo.get("given_name", "")),
            ("last_name", userinfo.get("family_name", "")),
        ):
            if getattr(user, field) != value:
                setattr(user, field, value)
                changed_fields.append(field)

        if changed_fields:
            user.save(update_fields=changed_fields)

        django_login(
            request,
            user,
            backend="django.contrib.auth.backends.ModelBackend",
        )

        return redirect(settings.FRONTEND_URL)

    except Exception:
        # Avoid returning access tokens or internal exception details.
        return JsonResponse(
            {"error": "GreenHill sign-in failed. Please try again."},
            status=401,
        )


@require_GET
def current_user(request):
    if not request.user.is_authenticated:
        return JsonResponse({"authenticated": False}, status=401)

    return JsonResponse({
        "authenticated": True,
        "user": {
            "id": request.user.pk,
            "email": request.user.email,
            "name": request.user.get_full_name(),
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
        },
    })


@require_POST
def greenhill_logout(request):
    django_logout(request)
    return JsonResponse({"authenticated": False})
PY