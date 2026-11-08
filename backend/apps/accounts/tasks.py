from celery import shared_task

from .models import User


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_verification_email_task(self, user_id):
    from .emails import send_verification_email

    user = User.objects.filter(pk=user_id, is_active=True).first()
    if user and not user.email_verified:
        try:
            send_verification_email(user)
        except Exception as exc:  # SMTP hiccup -> retry
            raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_password_reset_email_task(self, user_id):
    from .emails import send_password_reset_email

    user = User.objects.filter(pk=user_id, is_active=True).first()
    if user:
        try:
            send_password_reset_email(user)
        except Exception as exc:
            raise self.retry(exc=exc) from exc
