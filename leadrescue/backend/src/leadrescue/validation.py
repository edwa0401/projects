"""Input validation for API request bodies. Unknown fields are rejected."""

from __future__ import annotations

import re

from .analysis.contract import CATEGORIES, PRIORITIES
from .errors import bad_request

CHANNELS = ["web_form", "email", "phone_note", "sms", "chat"]
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[A-Za-z]{2,}$")
_PHONE_RE = re.compile(r"^[0-9+()\-. ]{7,32}$")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(value: str) -> str:
    return _CONTROL_RE.sub("", value).strip()


def _require_object(body) -> dict:
    if not isinstance(body, dict):
        raise bad_request("Request body must be a JSON object.")
    return body


def _reject_unknown(body: dict, allowed: set[str]) -> None:
    unknown = sorted(set(body) - allowed)
    if unknown:
        raise bad_request("Unknown fields in request.", {"fields": unknown})


def _optional_str(body: dict, key: str, max_len: int, errors: dict) -> str | None:
    value = body.get(key)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        errors[key] = "Must be text."
        return None
    value = clean_text(value)
    if len(value) > max_len:
        errors[key] = f"Must be {max_len} characters or fewer."
    return value or None


def validate_create(body) -> dict:
    body = _require_object(body)
    _reject_unknown(body, {"message", "channel", "customerName", "customerEmail", "customerPhone"})
    errors: dict = {}
    message = body.get("message")
    if not isinstance(message, str) or not clean_text(message):
        errors["message"] = "Customer message is required."
        message = ""
    else:
        message = clean_text(message)
        if len(message) < 10:
            errors["message"] = "Customer message must be at least 10 characters."
        elif len(message) > 5000:
            errors["message"] = "Customer message must be 5,000 characters or fewer."
    channel = body.get("channel", "web_form")
    if channel not in CHANNELS:
        errors["channel"] = f"Channel must be one of: {', '.join(CHANNELS)}."
    name = _optional_str(body, "customerName", 100, errors)
    email = _optional_str(body, "customerEmail", 254, errors)
    if email and "customerEmail" not in errors and not _EMAIL_RE.match(email):
        errors["customerEmail"] = "Enter a valid email address."
    phone = _optional_str(body, "customerPhone", 32, errors)
    if phone and "customerPhone" not in errors and not _PHONE_RE.match(phone):
        errors["customerPhone"] = "Enter a valid phone number."
    if errors:
        raise bad_request("Please fix the highlighted fields.", {"fields": errors})
    return {"message": message, "channel": channel, "customer": {"name": name, "email": email, "phone": phone}}


def _expected_version(body: dict) -> int:
    v = body.get("expectedVersion")
    if not isinstance(v, int) or isinstance(v, bool) or v < 1:
        raise bad_request("expectedVersion (a positive integer) is required.", {"fields": {"expectedVersion": "Required."}})
    return v


def validate_update(body, staff_ids: set[str]) -> tuple[int, dict]:
    body = _require_object(body)
    _reject_unknown(body, {"expectedVersion", "category", "priority", "assignee", "draftReply"})
    version = _expected_version(body)
    changes: dict = {}
    errors: dict = {}
    if "category" in body:
        if body["category"] not in CATEGORIES:
            errors["category"] = "Choose a valid category."
        else:
            changes["category"] = body["category"]
    if "priority" in body:
        if body["priority"] not in PRIORITIES:
            errors["priority"] = "Choose a valid priority."
        else:
            changes["priority"] = body["priority"]
    if "assignee" in body:
        if body["assignee"] is not None and body["assignee"] not in staff_ids:
            errors["assignee"] = "Choose a staff member from the list."
        else:
            changes["assignee"] = body["assignee"]
    if "draftReply" in body:
        draft = body["draftReply"]
        if not isinstance(draft, str):
            errors["draftReply"] = "Draft must be text."
        else:
            draft = clean_text(draft)
            if len(draft) > 4000:
                errors["draftReply"] = "Draft must be 4,000 characters or fewer."
            changes["draftReply"] = draft
    if errors:
        raise bad_request("Please fix the highlighted fields.", {"fields": errors})
    if not changes:
        raise bad_request("No changes were provided.")
    return version, changes


VERIFICATION_KEYS = ["factsChecked", "noCommitments", "categoryPriorityReviewed", "suspiciousReviewed"]


def validate_approve(body) -> tuple[int, dict, str | None]:
    body = _require_object(body)
    _reject_unknown(body, {"expectedVersion", "verification", "draftReply"})
    version = _expected_version(body)
    verification = body.get("verification")
    if not isinstance(verification, dict):
        raise bad_request("Human verification is required before approval.", code="verification_required")
    _reject_unknown(verification, set(VERIFICATION_KEYS))
    checks = {k: verification.get(k) is True for k in VERIFICATION_KEYS}
    draft = body.get("draftReply")
    if draft is not None:
        if not isinstance(draft, str):
            raise bad_request("Draft must be text.")
        draft = clean_text(draft)
    return version, checks, draft


def validate_resolve(body) -> tuple[int, str | None]:
    body = _require_object(body)
    _reject_unknown(body, {"expectedVersion", "resolutionNote"})
    version = _expected_version(body)
    note = body.get("resolutionNote")
    if note is not None:
        if not isinstance(note, str):
            raise bad_request("Resolution note must be text.")
        note = clean_text(note)
        if len(note) > 1000:
            raise bad_request("Resolution note must be 1,000 characters or fewer.")
    return version, note or None


def validate_expected_version_only(body) -> int | None:
    if body is None:
        return None
    body = _require_object(body)
    _reject_unknown(body, {"expectedVersion"})
    if "expectedVersion" not in body:
        return None
    return _expected_version(body)
