
import os
import base64
import hashlib
import logging
import secrets

from authlib.integrations.django_client import OAuth
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

logger = logging.getLogger(__name__)

oauth = OAuth()

oauth.register(
    name="greenhill",
    client_id=os.environ.get("GREENHILL_OIDC_CLIENT_ID", ""),
    client_secret=os.environ.get("GREENHILL_OIDC_CLIENT_SECRET", ""),
    server_metadata_url=os.environ.get(
        "GREENHILL_OIDC_DISCOVERY_URL",
        "https://greenhill-auth-backend2.onrender.com/o/.well-known/openid-configuration",
    ),
    client_kwargs={
        "scope": "openid email profile eid",
    },
)


@require_GET
def greenhill_login(request):
    try:
        if not settings.GREENHILL_OIDC_CLIENT_ID:
            return JsonResponse(
                {"error": "GreenHill OIDC client ID is not configured."},
                status=503,
            )

        callback_url = request.build_absolute_uri(
            reverse("greenhill_callback")
        )

        # Generate the PKCE verifier and S256 challenge.
        code_verifier = secrets.token_urlsafe(64)

        challenge_digest = hashlib.sha256(
            code_verifier.encode("ascii")
        ).digest()

        code_challenge = (
            base64.urlsafe_b64encode(challenge_digest)
            .rstrip(b"=")
            .decode("ascii")
        )

        # Store the verifier for the token exchange.
        request.session["greenhill_code_verifier"] = code_verifier

        return oauth.greenhill.authorize_redirect(
            request,
            callback_url,
            code_challenge=code_challenge,
            code_challenge_method="S256",
        )

    except Exception:
        logger.exception("GreenHill OIDC login initiation failed")
        return JsonResponse(
            {"error": "Sign-in could not be started. Please try again."},
            status=500,
        )


@require_GET
def greenhill_callback(request):
    try:
        # Retrieve the PKCE verifier saved during login.
        code_verifier = request.session.get(
            "greenhill_code_verifier"
        )

        if not code_verifier:
            return JsonResponse(
                {
                    "error": (
                        "PKCE verifier is missing. "
                        "Please start sign-in again."
                    )
                },
                status=400,
            )

        # Exchange the authorization code for tokens.
        token = oauth.greenhill.authorize_access_token(
            request,
            code_verifier=code_verifier,
        )

        request.session.pop("greenhill_code_verifier", None)

        userinfo = token.get("userinfo")

        if not userinfo:
            return JsonResponse(
                {
                    "error": (
                        "GreenHill did not return verified "
                        "user information."
                    )
                },
                status=401,
            )

        email = (userinfo.get("email") or "").strip().lower()
        subject = userinfo.get("sub")

        # Allow only GreenHill Academy accounts.
        if (
            not subject
            or not email.endswith("@greenhillacademy.ac.ug")
        ):
            return JsonResponse(
                {
                    "error": (
                        "A valid GreenHill Academy account is required."
                    )
                },
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

        # Update the user's basic identity information.
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

        # Create the EID application session.
        django_login(
            request,
            user,
            backend="django.contrib.auth.backends.ModelBackend",
        )

        return redirect(settings.FRONTEND_URL)

    except Exception:
        logger.exception("GreenHill OIDC callback failed")
        return JsonResponse(
            {
                "error": (
                    "GreenHill sign-in failed. Please try again."
                )
            },
            status=401,
        )


@require_GET
def current_user(request):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"authenticated": False},
            status=401,
        )

    return JsonResponse(
        {
            "authenticated": True,
            "user": {
                "id": request.user.pk,
                "email": request.user.email,
                "name": request.user.get_full_name(),
                "first_name": request.user.first_name,
                "last_name": request.user.last_name,
            },
        }
    )


@require_POST
def greenhill_logout(request):
    django_logout(request)

    return JsonResponse({"authenticated": False})
