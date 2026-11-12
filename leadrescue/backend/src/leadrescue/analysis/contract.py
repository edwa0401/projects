"""The analysis contract shared by every provider (demo and Bedrock).

The model (or the deterministic demo analyzer) must return an object matching
MODEL_OUTPUT_SCHEMA. The service then validates it, applies guardrails, and
stores the result with provider metadata.
"""

CATEGORIES = ["quote", "urgent_issue", "schedule_change", "manual_review"]
PRIORITIES = ["urgent", "high", "normal", "low"]
EXTRACTED_FIELDS = [
    "movingDate",
    "pickupLocation",
    "destination",
    "propertySize",
    "contactName",
    "contactPhone",
    "contactEmail",
]
# Fields that drive "missing information" (contact is handled as one requirement).
CORE_FIELDS = ["movingDate", "pickupLocation", "destination", "propertySize"]
PROMPT_VERSION = "2026-11-12.1"
TOOL_NAME = "record_inquiry_analysis"

_nullable_text = {"type": ["string", "null"], "maxLength": 200}

MODEL_OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "category",
        "priority",
        "priorityReason",
        "summary",
        "extracted",
        "missingInformation",
        "draftReply",
        "suspiciousInstructions",
        "suspiciousReason",
    ],
    "properties": {
        "category": {"type": "string", "enum": CATEGORIES},
        "priority": {"type": "string", "enum": PRIORITIES},
        "priorityReason": {"type": "string", "minLength": 1, "maxLength": 300},
        "summary": {"type": "string", "minLength": 1, "maxLength": 600},
        "extracted": {
            "type": "object",
            "additionalProperties": False,
            "required": EXTRACTED_FIELDS,
            "properties": {f: dict(_nullable_text) for f in EXTRACTED_FIELDS},
        },
        "missingInformation": {
            "type": "array",
            "maxItems": len(EXTRACTED_FIELDS) + 1,
            "uniqueItems": True,
            "items": {"type": "string", "enum": CORE_FIELDS + ["contactMethod"] + EXTRACTED_FIELDS[4:]},
        },
        "draftReply": {"type": "string", "minLength": 1, "maxLength": 2000},
        "suspiciousInstructions": {"type": "boolean"},
        "suspiciousReason": {"type": ["string", "null"], "maxLength": 300},
    },
}
