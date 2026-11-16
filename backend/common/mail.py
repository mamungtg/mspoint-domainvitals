"""Branded transactional email: one layout, an HTML part and a plain-text part.

Inline styles and a table layout because mail clients (Outlook above all)
ignore most CSS. Every dynamic value is HTML-escaped.
"""

from __future__ import annotations

from html import escape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

NAVY, BLUE, AMBER, INK, MUTED, LINE = "#0B2C4D", "#14508F", "#F5A623", "#1B2433", "#5A6577", "#DDE3EC"


def _html(heading: str, paragraphs: list[str], button: tuple[str, str] | None, note: str) -> str:
    body = "".join(
        f'<p style="margin:0 0 14px;font-size:15px;line-height:1.6;color:{INK}">{escape(p)}</p>' for p in paragraphs
    )
    if button:
        label, url = button
        body += (
            f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:22px 0 18px"><tr>'
            f'<td style="background:{AMBER};border-radius:6px">'
            f'<a href="{escape(url)}" style="display:inline-block;padding:12px 22px;font-size:15px;font-weight:600;'
            f'color:{NAVY};text-decoration:none">{escape(label)}</a></td></tr></table>'
            f'<p style="margin:0 0 6px;font-size:13px;color:{MUTED}">If the button does not work, copy this link into your browser:</p>'
            f'<p style="margin:0 0 14px;font-size:13px;word-break:break-all"><a href="{escape(url)}" style="color:{BLUE}">{escape(url)}</a></p>'
        )
    if note:
        body += f'<p style="margin:18px 0 0;padding-top:14px;border-top:1px solid {LINE};font-size:13px;color:{MUTED}">{escape(note)}</p>'
    return f"""<!doctype html><html><body style="margin:0;background:#F3F6FA;font-family:Inter,Segoe UI,Arial,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F3F6FA;padding:32px 12px"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px">
<tr><td style="background:{NAVY};padding:18px 28px;border-radius:10px 10px 0 0">
<span style="font-size:18px;font-weight:700;color:#ffffff">DomainVitals</span>
<span style="font-size:12px;color:#B9CCE2"> by MSPoint</span></td></tr>
<tr><td style="background:#ffffff;padding:28px;border:1px solid {LINE};border-top:0;border-radius:0 0 10px 10px">
<h1 style="margin:0 0 16px;font-size:21px;line-height:1.3;color:{NAVY}">{escape(heading)}</h1>{body}</td></tr>
<tr><td style="padding:16px 8px;font-size:12px;color:{MUTED};text-align:center">MSPoint LLC · This is an automated message, replies are not monitored.</td></tr>
</table></td></tr></table></body></html>"""


def _text(heading: str, paragraphs: list[str], button: tuple[str, str] | None, note: str) -> str:
    parts = [heading, "", *[p + "\n" for p in paragraphs]]
    if button:
        parts += [f"{button[0]}:", button[1], ""]
    if note:
        parts += [note, ""]
    parts.append("— DomainVitals by MSPoint")
    return "\n".join(parts)


def send_branded(
    to: str,
    subject: str,
    heading: str,
    paragraphs: list[str],
    button=None,
    note: str = "",
    fail_silently=False,
    attachments: list[tuple[str, bytes, str]] | None = None,
):
    msg = EmailMultiAlternatives(
        subject=subject,
        body=_text(heading, paragraphs, button, note),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to],
    )
    msg.attach_alternative(_html(heading, paragraphs, button, note), "text/html")
    for name, content, mimetype in attachments or []:
        msg.attach(name, content, mimetype)
    msg.send(fail_silently=fail_silently)
