import hashlib
import secrets
import zoneinfo
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.text import slugify

from common.models import TimestampedModel, UUIDModel


def validate_timezone(value):
    if value not in zoneinfo.available_timezones():
        raise ValidationError("Unknown time zone.")


class Role(models.TextChoices):
    OWNER = "owner", "Owner"
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Member"
    VIEWER = "viewer", "Viewer"


# Higher number = more privilege.
ROLE_RANK = {Role.VIEWER: 0, Role.MEMBER: 1, Role.ADMIN: 2, Role.OWNER: 3}
MANAGER_ROLES = {Role.OWNER, Role.ADMIN}


class Organization(TimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=80, unique=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_organizations")
    timezone = models.CharField(max_length=64, default="UTC", validators=[validate_timezone])
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    is_demo = models.BooleanField(default=False, help_text="Read-only sample workspace.")

    class Meta:
        ordering = ["is_demo", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        super().save(*args, **kwargs)

    def _unique_slug(self):
        base = slugify(self.name)[:60] or "workspace"
        slug = base
        while Organization.objects.filter(slug=slug).exists():
            slug = f"{base}-{secrets.token_hex(3)}"
        return slug

    def __str__(self):
        return self.name


class Membership(UUIDModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "user"], name="uniq_membership_org_user"),
        ]
        indexes = [models.Index(fields=["user"])]

    @property
    def rank(self) -> int:
        return ROLE_RANK[self.role]

    def __str__(self):
        return f"{self.user} @ {self.organization} ({self.role})"


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class InvitationQuerySet(models.QuerySet):
    def pending(self):
        return self.filter(accepted_at__isnull=True, revoked_at__isnull=True, expires_at__gt=timezone.now())


class Invitation(UUIDModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER)
    token_hash = models.CharField(max_length=64, unique=True)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    objects = InvitationQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # At most one open invitation per address per organization.
            models.UniqueConstraint(
                "organization",
                Lower("email"),
                condition=models.Q(accepted_at__isnull=True, revoked_at__isnull=True),
                name="uniq_open_invitation_org_email",
            ),
        ]

    @classmethod
    def issue(cls, *, organization, email, role, invited_by):
        raw = secrets.token_urlsafe(32)
        inv = cls.objects.create(
            organization=organization,
            email=email.strip().lower(),
            role=role,
            invited_by=invited_by,
            token_hash=hash_token(raw),
            expires_at=timezone.now() + timedelta(days=settings.INVITATION_MAX_AGE_DAYS),
        )
        return inv, raw

    @property
    def is_pending(self):
        return self.accepted_at is None and self.revoked_at is None and self.expires_at > timezone.now()
