"""Deterministic guardrails applied to every analysis, regardless of provider.

1. Prompt-injection signals: customer text that tries to steer the AI forces
   manual review, independent of what the model said.
2. Grounding: an extracted value that does not appear in the inquiry text is
   removed (set to null) and reported. This enforces "extract only explicitly
   stated facts" even if a model invents something.
3. Draft policy: replies must not quote prices or confirm availability/bookings.
"""

from __future__ import annotations

import re

from .contract import CORE_FIELDS, EXTRACTED_FIELDS, PRIORITIES

_INJECTION_PATTERNS = [
    (r"\bignore\b[^.\n]{0,40}\b(instructions?|rules|prompts?|guidelines)\b", "asks to ignore instructions"),
    (r"\bdisregard\b[^.\n]{0,40}\b(instructions?|rules|prompts?|guidelines)\b", "asks to disregard instructions"),
    (r"\bforget\b[^.\n]{0,30}\b(instructions?|rules|everything)\b", "asks to forget instructions"),
    (r"\bsystem prompt\b", "references the system prompt"),
    (r"\byou are now\b|\bact as (an?|the) (admin|administrator|manager|developer)\b", "attempts role change"),
    (r"\bdeveloper mode\b|\bjailbreak\b|\bDAN\b", "jailbreak language"),
    (r"\b(auto[- ]?)?approve\b[^.\n]{0,60}\b(free|no charge|discount|100% off|refund)\b", "asks AI to approve a concession"),
    (r"\bfree move\b|\bmove for free\b", "requests a free move"),
    (r"\b(reveal|print|show|output)\b[^.\n]{0,40}\b(secret|api key|password|credentials?|prompt|instructions)\b", "asks to reveal secrets or instructions"),
    (r"</?\s*(customer_message|system|instructions?)\s*>", "contains prompt delimiter tags"),
    (r"\b(call|invoke|run|execute)\b[^.\n]{0,20}\b(tool|function|command)\b", "asks AI to invoke tools"),
]

_POLICY_PATTERNS = [
    (r"\$\s?\d", "quotes a dollar amount"),
    (r"\b\d[\d,]*(\.\d+)?\s?(dollars|usd)\b", "quotes a price"),
    (r"\b(is|are|has been|have been)\s+(now\s+)?(confirmed|booked|reserved|guaranteed|approved)\b", "confirms a booking or approval"),
    (r"\bwe(?:'ve| have| will| 've)?\s+(confirmed|booked|reserved|guaranteed|approved)\b", "confirms a booking or approval"),
    (r"\b(we|i)\s+guarantee\b|\bguaranteed\b", "makes a guarantee"),
    (r"\bfree (move|of charge)\b|\bno charge\b|\bat no cost\b", "offers a free move or waived charge"),
    (r"\b(crew|movers|truck) (will|is going to) (arrive|be there) (at|by|in)\b", "promises arrival time or availability"),
    (r"\bwe (have|'ve got) (availability|openings?|a crew available)\b", "confirms availability"),
]

_PRIORITY_RANK = {p: i for i, p in enumerate(PRIORITIES)}  # urgent=0 ... low=3


def detect_injection(text: str) -> list[str]:
    signals = []
    for pattern, label in _INJECTION_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE) and label not in signals:
            signals.append(label)
    return signals


def check_draft_policy(draft: str) -> list[str]:
    violations = []
    for pattern, label in _POLICY_PATTERNS:
        if re.search(pattern, draft or "", flags=re.IGNORECASE) and label not in violations:
            violations.append(label)
    return violations


def _norm(text: str) -> str:
    text = text.lower().replace("’", "'")
    text = re.sub(r"[^a-z0-9@.'/#\- ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip(" .,-")


def is_grounded(value: str, source: str, field: str) -> bool:
    if not value or not value.strip():
        return False
    if field == "contactPhone":
        digits = re.sub(r"\D", "", value)
        if len(digits) < 7:
            return False
        source_digits = [re.sub(r"\D", "", m) for m in re.findall(r"[\d()+\-. ]{7,}", source)]
        return any(digits in d or (len(d) >= 10 and digits.endswith(d)) for d in source_digits)
    return _norm(value) in _norm(source)


def ground_extraction(extracted: dict, source: str) -> tuple[dict, list[str]]:
    cleaned, removed = {}, []
    for field in EXTRACTED_FIELDS:
        value = extracted.get(field)
        if isinstance(value, str) and value.strip():
            if is_grounded(value, source, field):
                cleaned[field] = value.strip()
            else:
                cleaned[field] = None
                removed.append(field)
        else:
            cleaned[field] = None
    return cleaned, removed


def compute_missing(extracted: dict) -> list[str]:
    """Missing information is computed deterministically from the grounded extraction.

    The model's own list is kept separately (rawMissingInformation) for evaluation.
    """
    missing = [f for f in CORE_FIELDS if not extracted.get(f)]
    if not extracted.get("contactPhone") and not extracted.get("contactEmail"):
        missing.append("contactMethod")
    return missing


def build_source_text(message: str, customer: dict) -> str:
    parts = [message]
    for key in ("name", "email", "phone"):
        if customer.get(key):
            parts.append(str(customer[key]))
    return "\n".join(parts)


def apply_guardrails(raw: dict, message: str, customer: dict) -> dict:
    """Return a post-processed analysis plus a `guardrails` report. `raw` must already be schema-valid."""
    source = build_source_text(message, customer)
    extracted, removed = ground_extraction(raw["extracted"], source)
    signals = detect_injection(message)
    overrides: list[str] = []

    category = raw["category"]
    priority = raw["priority"]
    suspicious = bool(raw["suspiciousInstructions"])
    suspicious_reason = raw.get("suspiciousReason")

    if signals and not suspicious:
        suspicious = True
        suspicious_reason = "Guardrail detected: " + "; ".join(signals)
        overrides.append("suspiciousInstructions set by guardrail")
    if suspicious and category != "manual_review":
        overrides.append(f"category changed from {category} to manual_review")
        category = "manual_review"
    if suspicious and _PRIORITY_RANK[priority] > _PRIORITY_RANK["normal"]:
        overrides.append(f"priority raised from {priority} to normal")
        priority = "normal"

    draft = raw["draftReply"]
    policy = check_draft_policy(draft)

    return {
        "category": category,
        "priority": priority,
        "priorityReason": raw["priorityReason"],
        "summary": raw["summary"],
        "extracted": extracted,
        "missingInformation": compute_missing(extracted),
        "rawMissingInformation": list(raw.get("missingInformation", [])),
        "draftReply": draft,
        "suspiciousInstructions": suspicious,
        "suspiciousReason": suspicious_reason if suspicious else None,
        "guardrails": {
            "removedUngroundedFields": removed,
            "injectionSignals": signals,
            "overrides": overrides,
            "draftPolicyWarnings": policy,
        },
    }
