from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Give a user access to the staff console (or remove it with --remove). Lists staff without arguments."

    def add_arguments(self, parser):
        parser.add_argument("email", nargs="?")
        parser.add_argument("--remove", action="store_true")

    def handle(self, email=None, remove=False, **opts):
        if not email:
            for u in User.objects.filter(is_staff=True).order_by("email"):
                self.stdout.write(u.email)
            return
        user = User.objects.filter(email__iexact=email.strip()).first()
        if not user:
            raise CommandError(f"No user with email {email}")
        user.is_staff = not remove
        user.save(update_fields=["is_staff"])
        self.stdout.write(self.style.SUCCESS(f"{user.email}: staff console {'removed' if remove else 'enabled'}"))
