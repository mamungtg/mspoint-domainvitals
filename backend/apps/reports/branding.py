"""Which branding a report gets, and safe handling of uploaded logos."""

from __future__ import annotations

import io

from PIL import Image, UnidentifiedImageError

from .models import ReportBranding
from .pdf import Brand

WHITE_LABEL_PLANS = ("agency", "msp", "enterprise")
MAX_UPLOAD = 1024 * 1024
MAX_PIXELS = 4000 * 4000
DEFAULT = {
    "name": "DomainVitals by MSPoint",
    "accent": "#14508F",
    "footer": "Prepared with DomainVitals · app.mspointit.com",
}


class LogoError(ValueError):
    pass


def white_label_allowed(org) -> bool:
    if org.is_demo:
        return False
    from apps.billing.limits import account_for

    acc = account_for(org)
    return bool(acc) and acc.effective_plan in WHITE_LABEL_PLANS


def brand_for(org) -> Brand:
    b = ReportBranding.objects.filter(organization=org).first()
    if b and white_label_allowed(org):
        return Brand(
            name=b.company_name or org.name,
            accent=b.accent_color or DEFAULT["accent"],
            footer=b.footer_text or (b.company_name or org.name),
            logo=bytes(b.logo) if b.logo else None,
        )
    return Brand(DEFAULT["name"], DEFAULT["accent"], DEFAULT["footer"], None)


def process_logo(data: bytes) -> bytes:
    """Accept PNG or JPEG, reject anything else, and re-encode as a small PNG
    (drops metadata and anything hidden in the original file)."""
    if len(data) > MAX_UPLOAD:
        raise LogoError("The logo must be 1 MB or smaller.")
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with Image.open(io.BytesIO(data)) as probe:
            fmt = probe.format
            probe.verify()
        if fmt not in ("PNG", "JPEG"):
            raise LogoError("Upload a PNG or JPEG image.")
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            img = img.convert("RGBA")
            img.thumbnail((600, 200))
            out = io.BytesIO()
            img.save(out, format="PNG", optimize=True)
            return out.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise LogoError("This file is not a readable PNG or JPEG image.") from e
