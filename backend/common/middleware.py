"""Request ID propagation: accept a sane inbound X-Request-ID or generate one."""

import contextvars
import logging
import re
import uuid

_request_id = contextvars.ContextVar("request_id", default="-")
_VALID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def get_request_id() -> str:
    return _request_id.get()


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get("X-Request-ID", "")
        rid = incoming if _VALID.match(incoming) else uuid.uuid4().hex
        token = _request_id.set(rid)
        request.request_id = rid
        try:
            response = self.get_response(request)
        finally:
            _request_id.reset(token)
        response["X-Request-ID"] = rid
        return response


class RequestIDLogFilter(logging.Filter):
    def filter(self, record):
        record.request_id = get_request_id()
        return True
