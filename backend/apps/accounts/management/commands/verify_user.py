from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Mark a user's email address as confirmed (for support, when mail delivery is not available)."

    def add_arguments(self, parser):
        parser.add_argument("email")

    def handle(self, email, **options):
        user = User.objects.filter(email=email.strip().lower()).first()
        if user is None:
            raise CommandError(f"No user with email {email}.")
        if user.email_verified:
            self.stdout.write(f"{user.email} is already confirmed.")
            return
        user.mark_email_verified()
        self.stdout.write(self.style.SUCCESS(f"{user.email} is now confirmed and can sign in."))
