"""Business results computed from business-workspace records only (never practice data)."""

from __future__ import annotations

from statistics import median

from .analysis.contract import CATEGORIES
from .service import STATUSES, parse_iso

TARGETS = {
    "medianMinutesToFirstReview": {"value": 15, "label": "Median time to first review", "unit": "minutes", "direction": "at most"},
    "medianHoursToResolution": {"value": 24, "label": "Median time to resolution", "unit": "hours", "direction": "at most"},
    "classificationAccuracy": {"value": 0.9, "label": "Classification accuracy on the evaluation set", "unit": "ratio", "direction": "at least"},
    "urgentRecall": {"value": 1.0, "label": "Urgent cases flagged on the evaluation set", "unit": "ratio", "direction": "at least"},
}


def _minutes(a: str, b: str) -> float:
    return (parse_iso(b) - parse_iso(a)).total_seconds() / 60.0


def _stats(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "median": None, "mean": None}
    return {"count": len(values), "median": round(median(values), 1), "mean": round(sum(values) / len(values), 1)}


def compute(items: list[dict]) -> dict:
    by_category = {c: 0 for c in CATEGORIES}
    by_category["uncategorized"] = 0
    by_status = {s: 0 for s in STATUSES}
    first_review, resolution = [], []
    reviewed_with_ai = cat_corrections = pri_corrections = 0
    for i in items:
        by_category[i.get("category") or "uncategorized"] += 1
        by_status[i["status"]] += 1
        if i.get("firstReviewedAt"):
            first_review.append(_minutes(i["createdAt"], i["firstReviewedAt"]))
        if i.get("resolvedAt"):
            resolution.append(_minutes(i["createdAt"], i["resolvedAt"]) / 60.0)
        ai = i.get("aiSuggestion")
        if ai and i["status"] in ("approved", "resolved") and i.get("category"):
            reviewed_with_ai += 1
            cat_corrections += int(ai["category"] != i["category"])
            pri_corrections += int(ai["priority"] != i.get("priority"))
    sources = sorted({i.get("source", "unknown") for i in items})
    synthetic = sum(1 for i in items if i.get("source") == "seed")
    providers = sorted({(i.get("aiSuggestion") or {}).get("meta", {}).get("provider") for i in items if i.get("aiSuggestion")})
    return {
        "recordCount": len(items),
        "syntheticRecordCount": synthetic,
        "sources": sources,
        "analysisProviders": providers,
        "byCategory": by_category,
        "byStatus": by_status,
        "minutesToFirstReview": _stats(first_review),
        "hoursToResolution": _stats(resolution),
        "aiCorrection": {
            "reviewedCount": reviewed_with_ai,
            "categoryCorrections": cat_corrections,
            "categoryCorrectionRate": round(cat_corrections / reviewed_with_ai, 3) if reviewed_with_ai else None,
            "priorityCorrections": pri_corrections,
            "priorityCorrectionRate": round(pri_corrections / reviewed_with_ai, 3) if reviewed_with_ai else None,
        },
        "targets": TARGETS,
        "dataNote": (
            f"Measured from {len(items)} business records. {synthetic} are synthetic seed records with simulated history, "
            "so these numbers demonstrate the calculations, not real business performance."
            if synthetic
            else f"Measured from {len(items)} business records entered in this environment."
        ),
    }
