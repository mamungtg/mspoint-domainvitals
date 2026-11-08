"""Consistent JSON error envelope for every API error.

{"error": {"code": "...", "message": "...", "details": {...}}, "request_id": "..."}
"""

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.views import exception_handler

from .middleware import get_request_id


def envelope_exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, context)
    if response is None:
        return None  # unhandled -> Django 500 handler; never leak internals

    code = getattr(exc, "default_code", "error")
    if isinstance(exc, exceptions.ValidationError):
        message = "Validation failed."
        details = response.data
        code = "validation_error"
    else:
        detail = response.data.get("detail") if isinstance(response.data, dict) else response.data
        message = str(detail) if detail is not None else "Request failed."
        details = None
        codes = exc.get_codes() if hasattr(exc, "get_codes") else None
        if isinstance(codes, str):
            code = codes

    body = {"error": {"code": code, "message": message}, "request_id": get_request_id()}
    if details is not None:
        body["error"]["details"] = details
    if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS and getattr(exc, "wait", None):
        body["error"]["retry_after_seconds"] = int(exc.wait)
    response.data = body
    return response
