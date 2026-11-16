from celery import shared_task

from .health import mark


@shared_task(ignore_result=True)
def heartbeat():
    """Scheduled by beat, run by a worker: proves both are alive."""
    mark("scheduler")
