"""Deterministic, rule-based demo analyzer.

This is NOT AI. It exists so the full workflow runs without AWS credentials.
It produces output matching MODEL_OUTPUT_SCHEMA so it travels through the same
validation and guardrails as Bedrock results. Every stored result is labeled
provider="demo" and the UI shows "Simulated analysis".
"""

from __future__ import annotations

import re

from .contract import CORE_FIELDS
from .guardrails import detect_injection
from .provider import ProviderResult

_DAYS = r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
_MONTHS = r"(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)"
_NOT_PLACES = re.compile(rf"^(?:{_DAYS}|{_MONTHS}|today|tomorrow|next|this|the|a|an|my|our)\b", re.IGNORECASE)

_DATE_PATTERNS = [
    rf"\b(?:next|this|coming) {_DAYS}\b",
    rf"\b{_MONTHS}\.? \d{{1,2}}(?:st|nd|rd|th)?(?:,? \d{{4}})?\b",
    rf"\b\d{{1,2}}(?:st|nd|rd|th)? of {_MONTHS}\b",
    r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b",
    r"\b(?:next|this) (?:week|weekend|month)\b",
    r"\b(?:end|middle|beginning|first week|last week) of (?:next month|" + _MONTHS + r")\b",
    r"\btoday\b",
    r"\btomorrow\b",
    rf"\b{_DAYS}\b",
]

_PLACE = r"[A-Z][a-zA-Z.'\-]+(?: [A-Z][a-zA-Z.'\-]+){0,3}(?:,? (?:TX|OK|Texas|Oklahoma|[A-Z]{2}))?"
_STREET = r"\d{1,6} [A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+){0,3} (?:St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Blvd|Boulevard|Way|Ct|Court|Pkwy|Hwy)\b\.?(?:,? (?:Apt|Unit|#) ?\w+)?(?:,? [A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)?)?"
_SIZE_PATTERNS = [
    r"\b(?:studio|one|two|three|four|five|six|1|2|3|4|5|6)[- ](?:bed(?:room)?|br|bd)\b(?: (?:apartment|apt|house|home|condo|townhouse|townhome|duplex|unit))?",
    r"\bstudio(?: apartment)?\b",
    r"\b\d[\d,]{2,} (?:sq\.? ?ft|square feet)\b",
    r"\b(?:storage unit|single room|dorm room|office)\b",
]
_EMAIL = r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"
_PHONE = r"(?:\+?1[ .\-]?)?\(?\d{3}\)?[ .\-]?\d{3}[ .\-]?\d{4}"
_NAME_PATTERNS = [
    r"\bmy name is ([A-Z][a-z]+(?: [A-Z][a-z]+)?)",
    r"\bthis is ([A-Z][a-z]+(?: [A-Z][a-z]+)?)\b",
    r"\b(?:thanks|thank you|regards|best|sincerely|cheers)[,!.]?[ \t]*\n\s*([A-Z][a-z]+(?: [A-Z][a-z]+)?)\s*$",
    r"(?:^|\n)\s*[-–]\s*([A-Z][a-z]+(?: [A-Z][a-z]+)?)\s*$",
]

_URGENT = re.compile(
    r"(?:ha(?:ve|s)n'?t (?:shown|arrived|come)|not (?:shown|arrived|here)|no(?:body| one) (?:has )?(?:shown|arrived|come)|"
    r"no[- ]show|where are (?:the|your|my) (?:movers|crew|truck)|(?:running|are|is) (?:very )?late|"
    r"damag|broke|broken|smash|crack|scratch|injur|hurt|bleed|leak|flood|stolen|missing (?:items|boxes|furniture)|(?:are|is|went|were) missing|missing after|lost (?:my|our|a)|"
    r"truck (?:broke|has broken|won't)|locked out|stranded|emergency|urgent|stuck)",
    re.IGNORECASE,
)
_SCHEDULE = re.compile(
    r"(?:reschedul|change (?:my|our|the) (?:move|date|booking|time|appointment)|move (?:it|my move|our move|the move|the date) to|"
    r"postpone|push (?:it |my move |the move )?back|different (?:day|date)|switch (?:it |the date )?to|instead of|cancel|"
    r"move (?:it )?(?:up|earlier)|delay (?:my|our|the) move|change from)",
    re.IGNORECASE,
)
_QUOTE = re.compile(
    r"(?:quote|estimate|how much|price|pricing|cost|rates?\b|availability|available|need (?:help )?moving|need movers|looking for (?:movers|a mover|help)|"
    r"hire|book (?:a|movers)|moving (?:from|to)|move from|planning (?:a|to) move|bedroom|apartment|house|movers? for)",
    re.IGNORECASE,
)
_SOON = re.compile(r"\b(?:today|tonight|tomorrow|this (?:morning|afternoon|evening)|right now)\b", re.IGNORECASE)
_RELAXED = re.compile(r"\b(?:no rush|just curious|sometime next year|not sure when|eventually)\b", re.IGNORECASE)

_LABEL = {
    "movingDate": "your preferred moving date",
    "pickupLocation": "the pickup address or city",
    "destination": "the destination address or city",
    "propertySize": "the size of the home (for example, number of bedrooms)",
    "contactMethod": "the best phone number or email to reach you",
}


def _first(patterns, text, flags=re.IGNORECASE):
    best = None
    for p in patterns:
        m = re.search(p, text, flags)
        if m and (best is None or m.start() < best.start()):
            best = m
    return best.group(0).strip() if best else None


def _extract_date(text: str, category: str) -> str | None:
    if category == "schedule_change":
        m = re.search(rf"\bto (?:next |this )?({_DAYS}|{_MONTHS}\.? \d{{1,2}}(?:st|nd|rd|th)?)\b", text, re.IGNORECASE)
        if m:
            return m.group(0)[3:].strip()
    for p in _DATE_PATTERNS:  # ordered by specificity
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return None


def _clean_place(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip(" .,")
    if _NOT_PLACES.match(value):
        return None
    return value or None


def _extract_locations(text: str) -> tuple[str | None, str | None]:
    pickup = dest = None
    m = re.search(rf"\bfrom ({_STREET}|{_PLACE}) (?:to|into|over to) ({_STREET}|{_PLACE})", text)
    if m:
        pickup, dest = _clean_place(m.group(1)), _clean_place(m.group(2))
    if not pickup:
        m = re.search(rf"\b(?:pick ?up|pickup|moving out of|leaving|currently (?:live|living) (?:in|at)|from) (?:is |at |address is |in )?({_STREET}|{_PLACE})", text)
        if m:
            pickup = _clean_place(m.group(1))
    if not dest:
        m = re.search(rf"\b(?:to|into|destination is|delivery (?:is |to |at )?|going to|moving to|relocating to) (?:a new place in |a place in |our new home in |the )?({_STREET}|{_PLACE})", text)
        if m:
            candidate = _clean_place(m.group(1))
            if candidate and candidate != pickup:
                dest = candidate
    return pickup, dest


def _extract_name(text: str, customer: dict) -> str | None:
    if customer.get("name"):
        return customer["name"]
    for p in _NAME_PATTERNS:
        m = re.search(p, text, re.MULTILINE)
        if m:
            return m.group(1)
    return None


def classify(text: str) -> tuple[str, list[str]]:
    signals = detect_injection(text)
    if signals:
        return "manual_review", signals
    if _URGENT.search(text) and not re.search(r"\b(?:quote|estimate)\b", text, re.IGNORECASE):
        return "urgent_issue", []
    if _SCHEDULE.search(text):
        return "schedule_change", []
    if _URGENT.search(text):
        return "urgent_issue", []
    if _QUOTE.search(text):
        return "quote", []
    return "manual_review", []


class DemoProvider:
    name = "demo"
    model_id = "demo-rules-v1"

    def analyze(self, message: str, channel: str, customer: dict) -> ProviderResult:
        text = message or ""
        category, signals = classify(text)
        pickup, dest = _extract_locations(text)
        extracted = {
            "movingDate": _extract_date(text, category),
            "pickupLocation": pickup,
            "destination": dest,
            "propertySize": _first(_SIZE_PATTERNS, text),
            "contactName": _extract_name(text, customer),
            "contactPhone": customer.get("phone") or _first([_PHONE], text, 0),
            "contactEmail": customer.get("email") or _first([_EMAIL], text, 0),
        }
        missing = [f for f in CORE_FIELDS if not extracted[f]]
        if not extracted["contactPhone"] and not extracted["contactEmail"]:
            missing.append("contactMethod")

        if category == "urgent_issue":
            priority, reason = "urgent", "Describes an active problem with a move that needs immediate attention."
        elif category == "schedule_change":
            soon = bool(_SOON.search(text))
            priority = "high" if soon else "normal"
            reason = "Date change affects crew scheduling" + (" and the move is imminent." if soon else "; respond before the original date.")
        elif category == "quote":
            if _RELAXED.search(text):
                priority, reason = "low", "Early-stage inquiry with no firm timeline."
            elif _SOON.search(text):
                priority, reason = "high", "New lead with a near-term move date."
            else:
                priority, reason = "normal", "New quote request; respond within one business day."
        else:
            priority = "normal"
            reason = "Unclear or unusual request; a staff member should decide next steps."

        summary = _summary(category, extracted, missing, signals)
        draft = _draft(category, extracted, missing)
        return ProviderResult(
            raw={
                "category": category,
                "priority": priority,
                "priorityReason": reason,
                "summary": summary,
                "extracted": extracted,
                "missingInformation": missing,
                "draftReply": draft,
                "suspiciousInstructions": bool(signals),
                "suspiciousReason": ("Message contains instructions aimed at the AI: " + "; ".join(signals)) if signals else None,
            },
            model_id=self.model_id,
            input_tokens=None,
            output_tokens=None,
        )


def _summary(category, ex, missing, signals) -> str:
    if signals:
        return "Message contains instructions directed at the AI system and needs manual review."
    parts = {
        "quote": "Customer is asking for a moving quote",
        "urgent_issue": "Customer reports an active problem with their move",
        "schedule_change": "Customer wants to change the date of a booked move",
        "manual_review": "General inquiry that does not clearly match a category",
    }[category]
    details = []
    if ex["propertySize"]:
        details.append(f"for a {ex['propertySize']}")
    if ex["pickupLocation"] and ex["destination"]:
        details.append(f"from {ex['pickupLocation']} to {ex['destination']}")
    elif ex["pickupLocation"]:
        details.append(f"from {ex['pickupLocation']}")
    elif ex["destination"]:
        details.append(f"to {ex['destination']}")
    if ex["movingDate"]:
        details.append(f"({ex['movingDate']})")
    s = parts + (" " + " ".join(details) if details else "") + "."
    if missing:
        s += f" {len(missing)} detail(s) not provided."
    return s[:600]


def _draft(category, ex, missing) -> str:
    greeting = f"Hi {ex['contactName'].split()[0]}," if ex.get("contactName") else "Hello,"
    asks = [_LABEL[m] for m in missing if m in _LABEL]
    ask_text = ""
    if asks:
        ask_text = "\n\nTo help us prepare, could you share " + (", ".join(asks[:-1]) + " and " + asks[-1] if len(asks) > 1 else asks[0]) + "?"
    if category == "urgent_issue":
        body = ("Thank you for letting us know, and I'm sorry for the trouble with your move today. "
                "I've flagged this as urgent and a member of our dispatch team is looking into it now. "
                "We will contact you as soon as we have an update.")
    elif category == "schedule_change":
        body = ("Thanks for reaching out about changing your move date. "
                "I've passed your request to our scheduling team, who will check options and follow up with you. "
                "Your current booking stays in place until a team member contacts you.")
    elif category == "quote":
        body = ("Thanks for considering us for your move. "
                "A member of our team will review your details and follow up with an estimate and next steps.")
    else:
        body = ("Thanks for contacting us. A member of our team will review your message and follow up with you directly.")
        ask_text = ""
    return f"{greeting}\n\n{body}{ask_text}\n\nBest regards,\nCustomer Care Team"
