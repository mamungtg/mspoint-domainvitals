from django.conf import settings

from common.mail import send_branded

from .tokens import make_email_verification_token, make_password_reset_params


def _hours(seconds: int) -> str:
    h = max(1, round(seconds / 3600))
    return f"{h} hour{'s' if h != 1 else ''}"


def send_verification_email(user):
    link = f"{settings.FRONTEND_URL}/verify-email?token={make_email_verification_token(user)}"
    send_branded(
        to=user.email,
        subject="Confirm your DomainVitals email address",
        heading="Confirm your email address",
        paragraphs=[
            "Welcome to DomainVitals. Confirm this address to activate your account and sign in.",
        ],
        button=("Confirm email address", link),
        note=f"This link expires in {_hours(settings.EMAIL_VERIFICATION_MAX_AGE)}. "
        "If you did not create an account, you can ignore this message.",
    )


def send_password_reset_email(user):
    uid, token = make_password_reset_params(user)
    link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
    send_branded(
        to=user.email,
        subject="Reset your DomainVitals password",
        heading="Reset your password",
        paragraphs=[
            "Someone asked to reset the password for your DomainVitals account. Choose a new one with the button below."
        ],
        button=("Choose a new password", link),
        note=f"This link expires in {_hours(settings.PASSWORD_RESET_TIMEOUT)} and works once. "
        "If you did not ask for this, ignore this message; your password stays the same.",
    )
