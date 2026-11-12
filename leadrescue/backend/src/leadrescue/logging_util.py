"""Structured JSON logging for CloudWatch.

Rules: never log customer message bodies, draft text, contact details, or credentials.
Only identifiers, codes, counts, and timings are logged. `log_event` enforces an
allow-list of field names so a careless call cannot leak free text.
"""

from __future__ import annotations

import json
import logging
import sys
import time

_ALLOWED_FIELDS = {
    "event",
    "requestId",
    "method",
    "route",
    "status",
    "latencyMs",
    "userId",
    "inquiryId",
    "workspace",
    "provider",
    "modelId",
    "inputTokens",
    "outputTokens",
    "errorCode",
    "fromStatus",
    "toStatus",
    "awardCount",
    "count",
    "retryable",
    "guardrailFlags",
    "idempotent",
}

logger = logging.getLogger("leadrescue")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def log_event(event: str, level: int = logging.INFO, **fields) -> None:
    record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": event}
    for key, value in fields.items():
        if key in _ALLOWED_FIELDS and value is not None:
            record[key] = value
    logger.log(level, json.dumps(record, default=str))
