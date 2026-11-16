"""Render report data (see data.py) as a branded A4 PDF with ReportLab.

Everything that comes from users or DNS is escaped before it goes into a
Paragraph (ReportLab paragraphs understand a small markup language).
"""

from __future__ import annotations

import io
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Line, PolyLine, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    CondPageBreak,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

INK = colors.HexColor("#1B2433")
MUTED = colors.HexColor("#5A6577")
LINE = colors.HexColor("#DDE3EC")
SUBTLE = colors.HexColor("#F3F6FA")
STATUS = {
    "pass": (colors.HexColor("#1F9D55"), colors.HexColor("#E7F6EE"), "Pass"),
    "warn": (colors.HexColor("#B45309"), colors.HexColor("#FDF3E2"), "Warning"),
    "fail": (colors.HexColor("#C62828"), colors.HexColor("#FDECEC"), "Fail"),
    "error": (MUTED, SUBTLE, "Error"),
    None: (MUTED, SUBTLE, "–"),
}
CHECK_NAMES = {"spf": "SPF", "dkim": "DKIM", "dmarc": "DMARC", "mx": "MX", "dns": "DNS"}
PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


_PUNCT = str.maketrans(
    {
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u2192": "->",
        "\u2022": "\u00b7",
        "\u00a0": " ",
    }
)


def _latin(s) -> str:
    """The built-in PDF fonts cover Latin-1: map common punctuation, replace the rest."""
    return str(s if s is not None else "").translate(_PUNCT).encode("latin-1", "replace").decode("latin-1")


def t(s) -> str:
    return escape(_latin(s))


def score_color(score) -> colors.Color:
    if score is None:
        return MUTED
    return STATUS["pass"][0] if score >= 90 else STATUS["warn"][0] if score >= 70 else STATUS["fail"][0]


class Brand:
    def __init__(self, name: str, accent: str, footer: str, logo: bytes | None):
        self.name = name
        self.accent = colors.HexColor(accent)
        self.footer = footer
        self.logo = ImageReader(io.BytesIO(logo)) if logo else None


def styles(accent):
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=9.5, leading=13.5, textColor=INK, alignment=TA_LEFT)
    return {
        "base": base,
        "muted": ParagraphStyle("muted", parent=base, textColor=MUTED, fontSize=8.5, leading=12),
        "small": ParagraphStyle("small", parent=base, fontSize=8.5, leading=11.5),
        "h1": ParagraphStyle("h1", parent=base, fontName="Helvetica-Bold", fontSize=26, leading=31, textColor=accent),
        "h2": ParagraphStyle(
            "h2",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            textColor=INK,
            spaceBefore=4,
            spaceAfter=6,
        ),
        "h3": ParagraphStyle(
            "h3",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            textColor=accent,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "cell": ParagraphStyle("cell", parent=base, fontSize=8.5, leading=11),
        "cellb": ParagraphStyle("cellb", parent=base, fontName="Helvetica-Bold", fontSize=8.5, leading=11),
        "kpi": ParagraphStyle("kpi", parent=base, fontName="Helvetica-Bold", fontSize=20, leading=24),
    }


def _table(rows, widths, header=True, zebra=True):
    tbl = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    st = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
    ]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), SUBTLE), ("TEXTCOLOR", (0, 0), (-1, 0), MUTED)]
    tbl.setStyle(TableStyle(st))
    return tbl


def _trend_chart(points, accent, width=170 * mm, height=34 * mm):
    d = Drawing(width, height)
    d.add(Rect(0, 0, width, height, fillColor=SUBTLE, strokeColor=None))
    if len(points) < 2:
        d.add(
            String(
                8,
                height / 2 - 3,
                "Not enough scans in this period for a trend.",
                fontName="Helvetica",
                fontSize=8,
                fillColor=MUTED,
            )
        )
        return d
    pad_l, pad_b, pad_t, pad_r = 26, 14, 8, 8
    iw, ih = width - pad_l - pad_r, height - pad_b - pad_t
    for v in (0, 50, 100):
        y = pad_b + ih * v / 100
        d.add(Line(pad_l, y, width - pad_r, y, strokeColor=LINE, strokeWidth=0.5))
        d.add(String(4, y - 3, str(v), fontName="Helvetica", fontSize=7, fillColor=MUTED))
    first, last = points[0][0], points[-1][0]
    span = max(1, (last - first).days)
    coords = []
    for day, score in points:
        coords += [pad_l + iw * (day - first).days / span, pad_b + ih * score / 100]
    d.add(PolyLine(coords, strokeColor=accent, strokeWidth=1.6))
    d.add(String(pad_l, 2, first.strftime("%d %b"), fontName="Helvetica", fontSize=7, fillColor=MUTED))
    d.add(String(width - pad_r - 28, 2, last.strftime("%d %b"), fontName="Helvetica", fontSize=7, fillColor=MUTED))
    return d


def _kpis(totals, s):
    cells = [
        ("Domains", totals["domains"], INK),
        (
            "Average score",
            totals["average_score"] if totals["average_score"] is not None else "–",
            score_color(totals["average_score"]),
        ),
        ("Need attention", totals["failing"] + totals["warnings"], STATUS["fail"][0] if totals["failing"] else INK),
        ("Certificates expiring", totals["certs_expiring"], STATUS["warn"][0] if totals["certs_expiring"] else INK),
        ("Open alerts", totals["open_alerts"], STATUS["fail"][0] if totals["open_alerts"] else INK),
    ]
    row = [
        [Paragraph(f'<font color="#{c.hexval()[2:]}">{t(v)}</font>', s["kpi"]), Paragraph(t(label), s["muted"])]
        for label, v, c in cells
    ]
    tbl = Table([row], colWidths=[(PAGE_W - 2 * MARGIN) / 5] * 5)
    tbl.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, LINE),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return tbl


def _status_cell(status, s):
    fg, _, label = STATUS.get(status, STATUS[None])
    return Paragraph(f'<font color="#{fg.hexval()[2:]}"><b>{label}</b></font>', s["cell"])


def _domain_section(item, s, accent):
    out = []
    score = item["score"]
    head = Table(
        [
            [
                Paragraph(t(item["name"]), s["h2"]),
                Paragraph(
                    f'<font color="#{score_color(score).hexval()[2:]}">{t(score if score is not None else "–")}</font><font size="9" color="#5A6577"> / 100</font>',
                    s["kpi"],
                ),
            ]
        ],
        colWidths=[(PAGE_W - 2 * MARGIN) - 40 * mm, 40 * mm],
    )
    head.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    out.append(head)
    checked = item["checked_at"].strftime("%d %b %Y %H:%M UTC") if item["checked_at"] else "not scanned yet"
    out.append(Paragraph(f"Last checked {t(checked)}", s["muted"]))
    out.append(Spacer(1, 6))

    checks = [
        [Paragraph(f"<b>{CHECK_NAMES[c]}</b>", s["cell"]) for c in item["checks"]],
        [_status_cell(v, s) for v in item["checks"].values()],
    ]
    tbl = Table(checks, colWidths=[(PAGE_W - 2 * MARGIN) / 5] * 5)
    tbl.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, LINE),
                ("BACKGROUND", (0, 0), (-1, 0), SUBTLE),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    out.append(tbl)

    out.append(Paragraph("Health score over the period", s["h3"]))
    out.append(_trend_chart(item["trend"], accent))

    out.append(Paragraph("What to fix", s["h3"]))
    if item["findings"]:
        rows = [
            [
                Paragraph("<b>Severity</b>", s["cell"]),
                Paragraph("<b>Problem</b>", s["cell"]),
                Paragraph("<b>How to fix</b>", s["cell"]),
            ]
        ]
        for f in item["findings"]:
            st = "fail" if f["severity"] == "critical" else "warn"
            rows.append(
                [
                    Paragraph(
                        f'<font color="#{STATUS[st][0].hexval()[2:]}"><b>{f["severity"].capitalize()}</b></font>',
                        s["cell"],
                    ),
                    Paragraph(f"<b>{CHECK_NAMES.get(f['check'], '')}</b>: {t(f['title'])}", s["cell"]),
                    Paragraph(t(f["fix"]), s["cell"]),
                ]
            )
        out.append(_table(rows, [20 * mm, 62 * mm, None]))
    else:
        out.append(Paragraph("Nothing to fix. All checks pass.", s["base"]))

    if item["certificates"]:
        out.append(Paragraph("SSL/TLS certificates", s["h3"]))
        rows = [[Paragraph(f"<b>{h}</b>", s["cell"]) for h in ("Host", "Status", "Expires in", "Issuer")]]
        for c in item["certificates"]:
            days = c["days_left"]
            when = "–" if days is None else ("expired" if days < 0 else f"{days} days")
            host = c["hostname"] + (f":{c['port']}" if c["port"] and c["port"] != 443 else "")
            rows.append(
                [
                    Paragraph(t(host), s["cell"]),
                    _status_cell(c["status"], s),
                    Paragraph(t(when), s["cell"]),
                    Paragraph(t(c["issuer"] or c["error"] or "–"), s["cell"]),
                ]
            )
        out.append(_table(rows, [60 * mm, 22 * mm, 24 * mm, None]))

    dm = item["dmarc"]
    if dm["messages"]:
        out.append(Paragraph("DMARC reports", s["h3"]))
        rate = f"{dm['pass_rate'] * 100:.1f}%" if dm["pass_rate"] is not None else "–"
        out.append(
            Paragraph(f"{dm['messages']:,} messages reported by receivers; <b>{rate}</b> passed DMARC.", s["base"])
        )
        rows = [[Paragraph(f"<b>{h}</b>", s["cell"]) for h in ("Sending service", "Messages", "Passing", "Status")]]
        labels = {"pass": "Authenticated", "warn": "Partly failing", "fail": "Not authenticated"}
        for x in dm["senders"]:
            pr = f"{x['pass_rate'] * 100:.0f}%" if x["pass_rate"] is not None else "–"
            st = x["verdict"]
            rows.append(
                [
                    Paragraph(t(x["name"]), s["cell"]),
                    Paragraph(f"{x['messages']:,}", s["cell"]),
                    Paragraph(pr, s["cell"]),
                    Paragraph(f'<font color="#{STATUS[st][0].hexval()[2:]}">{labels[st]}</font>', s["cell"]),
                ]
            )
        out.append(Spacer(1, 4))
        out.append(_table(rows, [70 * mm, 28 * mm, 24 * mm, None]))

    if item["dns_changes"]:
        out.append(Paragraph("DNS changes in this period", s["h3"]))
        rows = [[Paragraph(f"<b>{h}</b>", s["cell"]) for h in ("Date", "Record", "Change")]]
        for c in item["dns_changes"]:
            vals = ", ".join(c["new_values"] or c["old_values"] or [])
            rows.append(
                [
                    Paragraph(c["detected_at"].strftime("%d %b %Y"), s["cell"]),
                    Paragraph(t(f"{c['name']} {c['rtype']}"), s["cell"]),
                    Paragraph(t(f"{c['kind']}: {vals}"[:220]), s["cell"]),
                ]
            )
        out.append(_table(rows, [24 * mm, 56 * mm, None]))

    if item["alerts"]:
        out.append(Paragraph("Open alerts", s["h3"]))
        rows = [[Paragraph(f"<b>{h}</b>", s["cell"]) for h in ("Severity", "Alert", "Since")]]
        for a in item["alerts"]:
            st = "fail" if a["severity"] == "critical" else "warn"
            rows.append(
                [
                    Paragraph(
                        f'<font color="#{STATUS[st][0].hexval()[2:]}">{a["severity"].capitalize()}</font>', s["cell"]
                    ),
                    Paragraph(t(a["title"]), s["cell"]),
                    Paragraph(a["opened_at"].strftime("%d %b %Y"), s["cell"]),
                ]
            )
        out.append(_table(rows, [22 * mm, None, 26 * mm]))
    return out


def render(data: dict, brand: Brand) -> bytes:
    buf = io.BytesIO()
    s = styles(brand.accent)
    period = f"{data['since'].strftime('%d %b %Y')} – {data['until'].strftime('%d %b %Y')}"

    def chrome(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(brand.accent)
        canvas.rect(0, PAGE_H - 6, PAGE_W, 6, stroke=0, fill=1)
        y = PAGE_H - 14 * mm
        if brand.logo:
            iw, ih = brand.logo.getSize()
            h = 9 * mm
            w = min(45 * mm, iw * h / ih)
            canvas.drawImage(brand.logo, MARGIN, y - 2 * mm, width=w, height=w * ih / iw, mask="auto")
        else:
            canvas.setFont("Helvetica-Bold", 11)
            canvas.setFillColor(brand.accent)
            canvas.drawString(MARGIN, y, _latin(brand.name))
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(PAGE_W - MARGIN, y, _latin(f"Domain health report · {period}"))
        canvas.setStrokeColor(LINE)
        canvas.line(MARGIN, 14 * mm, PAGE_W - MARGIN, 14 * mm)
        canvas.drawString(MARGIN, 9 * mm, _latin(brand.footer or brand.name)[:120])
        canvas.drawRightString(PAGE_W - MARGIN, 9 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=24 * mm,
        bottomMargin=20 * mm,
        title=_latin(f"Domain health report – {data['organization']}"),
        author=_latin(brand.name),
        creator="DomainVitals",
    )
    story = [
        Spacer(1, 18 * mm),
        Paragraph("Domain health report", s["h1"]),
        Spacer(1, 4),
        Paragraph(
            f"<b>{t(data['domains'][0]['name'] if data['single'] else data['organization'])}</b>",
            ParagraphStyle("c", parent=s["base"], fontSize=14, leading=18),
        ),
        Paragraph(f"{t(period)} · prepared {data['generated_at'].strftime('%d %b %Y')} by {t(brand.name)}", s["muted"]),
        Spacer(1, 10 * mm),
        _kpis(data["totals"], s),
        Spacer(1, 8 * mm),
        Paragraph(
            "This report covers mail authentication (SPF, DKIM, DMARC), mail servers (MX), DNS health and SSL/TLS "
            "certificates. Scores start at 100; each critical problem costs 25 points and each warning 10.",
            s["muted"],
        ),
    ]
    if not data["domains"]:
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph("There are no verified domains to report on yet.", s["base"]))
    elif not data["single"]:
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph("All domains", s["h2"]))
        rows = [[Paragraph(f"<b>{h}</b>", s["cell"]) for h in ("Domain", "Score", *CHECK_NAMES.values())]]
        for i in data["domains"]:
            rows.append(
                [
                    Paragraph(t(i["name"]), s["cell"]),
                    Paragraph(
                        f'<font color="#{score_color(i["score"]).hexval()[2:]}"><b>{t(i["score"] if i["score"] is not None else "–")}</b></font>',
                        s["cell"],
                    ),
                    *[_status_cell(v, s) for v in i["checks"].values()],
                ]
            )
        story.append(_table(rows, [None, 16 * mm] + [17 * mm] * 5))
    for i in data["domains"]:
        story.append(PageBreak())
        section = _domain_section(i, s, brand.accent)
        story.append(KeepTogether(section[:4]))
        story += section[4:]
        story.append(CondPageBreak(30 * mm))

    doc.build(story, onFirstPage=chrome, onLaterPages=chrome)
    return buf.getvalue()


def filename(data: dict) -> str:
    base = data["domains"][0]["name"] if data["single"] else "domains"
    return f"domainvitals-report-{base}-{datetime.now().strftime('%Y-%m-%d')}.pdf"
