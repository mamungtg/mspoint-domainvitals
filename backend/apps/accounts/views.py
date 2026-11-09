import logging

from django.contrib.auth import authenticate, login, logout, password_validation, update_session_auth_hash
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import client_ip, record
from common.authentication import enforce_csrf

from . import serializers as s
from .models import User
from .tasks import send_password_reset_email_task, send_verification_email_task
from .tokens import read_email_verification_token, read_password_reset_params

security_log = logging.getLogger("domainvitals.security")


class AnonymousPostView(APIView):
    """Base for anonymous, state-changing endpoints: no session auth, CSRF enforced."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            enforce_csrf(request)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """GET sets the CSRF cookie the SPA must echo in X-CSRFToken."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(responses={204: None}, tags=["auth"])
    def get(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegisterView(AnonymousPostView):
    throttle_scope = "register"

    @extend_schema(request=s.RegisterSerializer, responses={201: s.UserSerializer}, tags=["auth"])
    def post(self, request):
        ser = s.RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        if User.objects.filter(email=data["email"]).exists():
            # Do not reveal more than necessary; a clear message is still needed for UX.
            raise ValidationError({"email": ["An account with this email already exists."]})
        user = User.objects.create_user(
            email=data["email"], password=data["password"], full_name=data.get("full_name", "")
        )
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        record(request, "user.registered", obj=user)
        from apps.domains.demo import ensure_demo_workspace

        ensure_demo_workspace(user)  # read-only sample data to explore before adding real domains
        transaction.on_commit(lambda: send_verification_email_task.delay(str(user.pk)))
        return Response(s.UserSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(AnonymousPostView):
    throttle_scope = "login"

    @extend_schema(request=s.LoginSerializer, responses={200: s.UserSerializer}, tags=["auth"])
    def post(self, request):
        ser = s.LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = authenticate(request, username=ser.validated_data["email"], password=ser.validated_data["password"])
        if user is None or not user.is_active:
            # Not written to the audit table: DRF rolls back the request transaction
            # on errors. Security log line instead (ship to log aggregation).
            security_log.warning("login_failed email=%s ip=%s", ser.validated_data["email"].lower(), client_ip(request))
            raise AuthenticationFailed("Invalid email or password.")
        login(request, user)  # rotates the session key
        record(request, "user.logged_in", obj=user, user=user)
        return Response(s.UserSerializer(user).data)


class LogoutView(APIView):
    @extend_schema(request=None, responses={204: None}, tags=["auth"])
    def post(self, request):
        record(request, "user.logged_out", obj=request.user)
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    @extend_schema(responses={200: s.UserSerializer}, tags=["auth"])
    def get(self, request):
        return Response(s.UserSerializer(request.user).data)

    @extend_schema(request=s.UserSerializer, responses={200: s.UserSerializer}, tags=["auth"])
    def patch(self, request):
        ser = s.UserSerializer(request.user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class VerifyEmailView(AnonymousPostView):
    throttle_scope = "verify_email"

    @extend_schema(request=s.TokenSerializer, responses={200: dict}, tags=["auth"])
    def post(self, request):
        ser = s.TokenSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = read_email_verification_token(ser.validated_data["token"])
        if user is None:
            raise ValidationError({"token": ["This verification link is invalid or has expired."]})
        user.mark_email_verified()
        record(request, "user.email_verified", obj=user, user=user)
        return Response({"email_verified": True})


class ResendVerificationView(APIView):
    throttle_scope = "verify_email"

    @extend_schema(request=None, responses={202: None}, tags=["auth"])
    def post(self, request):
        user = request.user
        if not user.email_verified:
            transaction.on_commit(lambda: send_verification_email_task.delay(str(user.pk)))
        return Response(status=status.HTTP_202_ACCEPTED)


class PasswordResetRequestView(AnonymousPostView):
    throttle_scope = "password_reset"

    @extend_schema(request=s.EmailOnlySerializer, responses={202: None}, tags=["auth"])
    def post(self, request):
        ser = s.EmailOnlySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = User.objects.filter(email=ser.validated_data["email"].lower(), is_active=True).first()
        if user:
            record(request, "user.password_reset_requested", obj=user, user=user)
            transaction.on_commit(lambda: send_password_reset_email_task.delay(str(user.pk)))
        # Same response whether or not the account exists (no enumeration).
        return Response(status=status.HTTP_202_ACCEPTED)


class PasswordResetConfirmView(AnonymousPostView):
    throttle_scope = "password_reset"

    @extend_schema(request=s.PasswordResetConfirmSerializer, responses={204: None}, tags=["auth"])
    def post(self, request):
        ser = s.PasswordResetConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = read_password_reset_params(ser.validated_data["uid"], ser.validated_data["token"])
        if user is None:
            raise ValidationError({"token": ["This reset link is invalid or has expired."]})
        try:
            password_validation.validate_password(ser.validated_data["new_password"], user=user)
        except Exception as exc:  # django ValidationError -> DRF
            raise ValidationError({"new_password": list(getattr(exc, "messages", [str(exc)]))}) from exc
        user.set_password(ser.validated_data["new_password"])
        user.save(update_fields=["password"])  # invalidates the reset token and other sessions' hash
        record(request, "user.password_reset", obj=user, user=user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=s.PasswordChangeSerializer, responses={204: None}, tags=["auth"])
    def post(self, request):
        ser = s.PasswordChangeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(ser.validated_data["current_password"]):
            raise ValidationError({"current_password": ["Current password is incorrect."]})
        try:
            password_validation.validate_password(ser.validated_data["new_password"], user=user)
        except Exception as exc:
            raise ValidationError({"new_password": list(getattr(exc, "messages", [str(exc)]))}) from exc
        user.set_password(ser.validated_data["new_password"])
        user.save(update_fields=["password"])
        update_session_auth_hash(request, user)  # keep this session, drop the others
        record(request, "user.password_changed", obj=user)
        return Response(status=status.HTTP_204_NO_CONTENT)
