import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from common.mail import send_branded

from . import data as report_data
from .branding import brand_for
from .models import ReportSchedule
from .pdf import filename, render

log = logging.getLogger(__name__)


def send_report(schedule: ReportSchedule) -> int:
    org = schedule.organization
    data = report_data.build(org, None, 30)
    pdf = render(data, brand_for(org))
    name = filename(data)
    month = timezone.now().strftime("%B %Y")
    for to in schedule.recipients:
        send_branded(
            to=to,
            subject=f"Domain health report for {org.name}: {month}",
            heading=f"Your domain health report for {month}",
            paragraphs=[
                f"Attached is the monthly report for {org.name}: {data['totals']['domains']} domains, "
                f"average score {data['totals']['average_score'] if data['totals']['average_score'] is not None else '–'}, "
                f"{data['totals']['failing'] + data['totals']['warnings']} needing attention.",
            ],
            button=("Open the dashboard", f"{settings.FRONTEND_URL}/dashboard"),
            note="You receive this because a workspace admin added your address to the monthly report.",
            attachments=[(name, pdf, "application/pdf")],
        )
    return len(schedule.recipients)


@shared_task(soft_time_limit=900, time_limit=960)
def send_monthly_reports():
    """Runs daily; sends on the 1st (or the first run after it), once per month."""
    today = timezone.now().date()
    first = today.replace(day=1)
    due = ReportSchedule.objects.filter(enabled=True, organization__is_demo=False).select_related("organization")
    for sch in due:
        if sch.last_sent_on and sch.last_sent_on >= first:
            continue
        if not sch.recipients:
            continue
        try:
            send_report(sch)
        except Exception:
            log.exception("monthly report for %s failed", sch.organization_id)
            continue
        sch.last_sent_on = today
        sch.save(update_fields=["last_sent_on", "updated_at"])
