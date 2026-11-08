from django.conf import settings
from django.core.mail import send_mail

from .tokens import make_email_verification_token, make_password_reset_params


def send_verification_email(user):
    link = f"{settings.FRONTEND_URL}/verify-email?token={make_email_verification_token(user)}"
    send_mail(
        subject="Verify your DomainVitals email address",
        message=(
            "Welcome to DomainVitals.\n\n"
            f"Confirm your email address by opening this link:\n{link}\n\n"
            "If you did not create an account, you can ignore this message."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


def send_password_reset_email(user):
    uid, token = make_password_reset_params(user)
    link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
    send_mail(
        subject="Reset your DomainVitals password",
        message=(
            "A password reset was requested for your DomainVitals account.\n\n"
            f"Choose a new password here (the link expires soon):\n{link}\n\n"
            "If you did not request this, you can ignore this message."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )
