"""Signed, expiring tokens for email verification and password reset."""

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .models import User

_VERIFY_SALT = "domainvitals.verify-email"


def make_email_verification_token(user: User) -> str:
    return signing.dumps({"uid": str(user.pk), "email": user.email}, salt=_VERIFY_SALT)


def read_email_verification_token(token: str) -> User | None:
    try:
        data = signing.loads(token, salt=_VERIFY_SALT, max_age=settings.EMAIL_VERIFICATION_MAX_AGE)
    except signing.BadSignature:  # includes SignatureExpired
        return None
    user = User.objects.filter(pk=data.get("uid"), is_active=True).first()
    # Token is bound to the address it was sent to.
    if user is None or user.email != data.get("email"):
        return None
    return user


def make_password_reset_params(user: User) -> tuple[str, str]:
    return urlsafe_base64_encode(force_bytes(user.pk)), default_token_generator.make_token(user)


def read_password_reset_params(uid: str, token: str) -> User | None:
    try:
        pk = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=pk, is_active=True)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist, Exception):
        return None
    return user if default_token_generator.check_token(user, token) else None
