"""Deliver alerts to email, Slack, Microsoft Teams and signed webhooks."""

from __future__ import annotations

import hashlib
import hmac
import json
import socket
import ssl
import urllib.request
from urllib.parse import urlsplit

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.organizations.models import MANAGER_ROLES
from apps.ssl_monitor.scanner import is_public_ip
from common.mail import send_branded

from .models import SEVERITY_RANK, STATEFUL_KINDS, Alert, Channel, Delivery

TIMEOUT = 10
EMOJI = {"critical": "🔴", "warning": "🟠", "info": "🔵"}
EVENT_LABEL = {"opened": "", "escalated": "Now critical: ", "resolved": "Resolved: ", "notice": "", "test": ""}


class DeliveryError(Exception):
    pass


# --- which channels get what -----------------------------------------------------


def wants(channel: Channel, alert: Alert) -> bool:
    if not channel.enabled or alert.kind not in (channel.events or []):
        return False
    if alert.kind in STATEFUL_KINDS:
        return SEVERITY_RANK[alert.severity] >= SEVERITY_RANK[channel.min_severity]
    return True


def dispatch(alert: Alert, event: str) -> list[Delivery]:
    """Queue one delivery per interested channel, sent after the transaction commits."""
    from .tasks import deliver

    out = []
    for ch in Channel.objects.filter(organization_id=alert.organization_id, enabled=True):
        if wants(ch, alert):
            d = Delivery.objects.create(alert=alert, channel=ch, event=event)
            out.append(d)
            transaction.on_commit(lambda pk=d.pk: deliver.delay(str(pk)))
    return out


# --- message content -------------------------------------------------------------


def alert_url(alert: Alert | None) -> str:
    base = settings.FRONTEND_URL
    if alert and alert.domain_id:
        tab = {"certificate": "tls", "dns_change": "records", "dmarc_sender": "dmarc"}.get(alert.kind, "results")
        return f"{base}/domains/{alert.domain_id}?tab={tab}"
    return f"{base}/alerts"


def headline(alert: Alert, event: str) -> str:
    return f"{EVENT_LABEL.get(event, '')}{alert.title}"


def payload(alert: Alert, event: str, org_name: str) -> dict:
    return {
        "event": event,
        "sent_at": timezone.now().isoformat(),
        "organization": {"id": str(alert.organization_id), "name": org_name},
        "alert": {
            "id": str(alert.id),
            "kind": alert.kind,
            "severity": alert.severity,
            "status": alert.status,
            "title": alert.title,
            "detail": alert.detail,
            "domain": alert.domain.name if alert.domain_id else None,
            "opened_at": alert.opened_at.isoformat(),
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            "url": alert_url(alert),
            "data": alert.data,
        },
    }


def test_alert(channel: Channel) -> Alert:
    """An unsaved alert used for "Send test"."""
    a = Alert(
        organization=channel.organization,
        kind="check",
        key="test",
        severity="warning",
        status="open",
        title="Test notification from DomainVitals",
        detail="If you can read this, the channel is set up correctly. No action is needed.",
    )
    a.opened_at = timezone.now()
    return a


# --- transports ------------------------------------------------------------------


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def check_public_https(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise DeliveryError("The URL must start with https://.")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or 443, type=socket.SOCK_STREAM)
    except OSError as e:
        raise DeliveryError("The host name in the URL does not resolve.") from e
    if not infos or not all(is_public_ip(i[4][0]) for i in infos):
        raise DeliveryError("The URL must point to a public internet address.")


def http_post(url: str, body: bytes, headers: dict) -> None:
    check_public_https(url)
    # Scheme is checked above (https only).
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json", **headers})  # noqa: S310
    opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(req, timeout=TIMEOUT) as resp:
            if not 200 <= resp.status < 300:
                raise DeliveryError(f"The endpoint answered HTTP {resp.status}.")
    except urllib.error.HTTPError as e:
        raise DeliveryError(f"The endpoint answered HTTP {e.code}.") from e
    except (urllib.error.URLError, OSError) as e:
        raise DeliveryError(f"Could not reach the endpoint ({getattr(e, 'reason', e)}).") from e


def email_recipients(channel: Channel) -> list[str]:
    emails = set(channel.recipients or [])
    if channel.notify_managers:
        emails.update(
            channel.organization.memberships.filter(
                role__in=MANAGER_ROLES, user__is_active=True, user__email_verified=True
            ).values_list("user__email", flat=True)
        )
    return sorted(emails)


def send_email(channel: Channel, alert: Alert, event: str, org_name: str) -> None:
    to = email_recipients(channel)
    if not to:
        raise DeliveryError("This email channel has no recipients.")
    subject = f"[{alert.get_severity_display() if event != 'resolved' else 'Resolved'}] {alert.title}"
    paragraphs = [alert.detail] if alert.detail else []
    if event == "resolved":
        paragraphs = ["The problem below is no longer detected.", alert.title]
    for addr in to:  # one message per person: addresses are not exposed to each other
        send_branded(
            to=addr,
            subject=subject[:200],
            heading=headline(alert, event),
            paragraphs=paragraphs,
            button=("Open in DomainVitals", alert_url(alert)),
            note=f'You receive this because of the "{channel.name}" alert channel in the {org_name} workspace.',
        )


def send_slack(channel: Channel, alert: Alert, event: str, org_name: str) -> None:
    title = f"{EMOJI.get(alert.severity, '') if event != 'resolved' else '✅'} *{headline(alert, event)}*"
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": title + (f"\n{alert.detail}" if alert.detail else "")}}
    ]
    blocks.append(
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"{org_name} · <{alert_url(alert)}|Open in DomainVitals>"}],
        }
    )
    body = {"text": headline(alert, event), "blocks": blocks}
    http_post(channel.url, json.dumps(body).encode(), {})


def send_teams(channel: Channel, alert: Alert, event: str, org_name: str) -> None:
    color = (
        "Good"
        if event == "resolved"
        else {"critical": "Attention", "warning": "Warning"}.get(alert.severity, "Default")
    )
    card = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": headline(alert, event),
                "weight": "Bolder",
                "size": "Medium",
                "color": color,
                "wrap": True,
            },
            *([{"type": "TextBlock", "text": alert.detail, "wrap": True}] if alert.detail else []),
            {"type": "TextBlock", "text": org_name, "isSubtle": True, "spacing": "Small", "size": "Small"},
        ],
        "actions": [{"type": "Action.OpenUrl", "title": "Open in DomainVitals", "url": alert_url(alert)}],
    }
    body = {
        "type": "message",
        "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": card}],
    }
    http_post(channel.url, json.dumps(body).encode(), {})


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def send_webhook(channel: Channel, alert: Alert, event: str, org_name: str) -> None:
    body = json.dumps(payload(alert, event, org_name), separators=(",", ":")).encode()
    http_post(
        channel.url,
        body,
        {
            "X-DomainVitals-Event": event,
            "X-DomainVitals-Signature": sign(channel.secret, body),
            "User-Agent": "DomainVitals-Webhook/1",
        },
    )


SENDERS = {"email": send_email, "slack": send_slack, "teams": send_teams, "webhook": send_webhook}


def send(channel: Channel, alert: Alert, event: str) -> None:
    SENDERS[channel.type](channel, alert, event, channel.organization.name)


def deliver_now(delivery: Delivery) -> Delivery:
    ch = delivery.channel
    try:
        send(ch, delivery.alert or test_alert(ch), delivery.event)
    except Exception as e:  # recorded on the delivery and the channel, never raised to the caller
        msg = str(e)[:250] if isinstance(e, DeliveryError) else f"Delivery failed ({type(e).__name__})."
        delivery.status, delivery.error = Delivery.Status.FAILED, msg
        Channel.objects.filter(pk=ch.pk).update(last_error=msg)
    else:
        delivery.status, delivery.error, delivery.sent_at = Delivery.Status.SENT, "", timezone.now()
        Channel.objects.filter(pk=ch.pk).update(last_error="", last_sent_at=delivery.sent_at)
    delivery.save(update_fields=["status", "error", "sent_at"])
    return delivery
