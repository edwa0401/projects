"""Inquiry lifecycle: create -> analyze -> staff review -> approve -> resolve.

Invariants enforced here (server side, not just in the UI):
- An inquiry is persisted before any AI call. AI failure never loses the request.
- AI output only ever fills suggestions and pre-fills editable fields. Nothing is
  sent to customers, and only a staff action can approve or resolve.
- Approval requires a complete human verification checklist and a draft that
  passes the no-commitments policy check.
- Every staff change writes a timestamped audit event in the same atomic write.
"""

from __future__ import annotations

import itertools
import secrets
import time
from datetime import datetime, timezone
from typing import Callable

from .analysis.guardrails import check_draft_policy
from .analysis.provider import run_analysis
from .auth import Principal
from .errors import AnalysisError, ApiError, ConflictError, bad_request, conflict, forbidden, not_found
from .logging_util import log_event
from .validation import VERIFICATION_KEYS

_SEQ = itertools.count()


def event_id() -> str:
    """Time-ordered id so events written in the same second keep their order."""
    return f"{time.time_ns():x}{next(_SEQ) % 4096:03x}{secrets.token_hex(2)}"


STATUSES = ["new", "analysis_failed", "awaiting_review", "in_review", "approved", "resolved"]
OPEN_STATUSES = {"new", "analysis_failed", "awaiting_review", "in_review", "approved"}
ANALYZABLE = {"new", "analysis_failed", "awaiting_review", "in_review"}
EDITABLE = {"new", "analysis_failed", "awaiting_review", "in_review", "approved"}
APPROVABLE = {"new", "analysis_failed", "awaiting_review", "in_review"}


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


class InquiryService:
    def __init__(self, config, store, provider_factory: Callable, clock: Callable[[], datetime] | None = None):
        self.config = config
        self.store = store
        self._provider_factory = provider_factory
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    # -- helpers ----------------------------------------------------------
    def _now(self) -> str:
        return iso(self.clock())

    def _event(self, inquiry_id: str, actor: str, kind: str, at: str, **details) -> dict:
        return {
            "id": event_id(),
            "inquiryId": inquiry_id,
            "at": at,
            "actor": actor,
            "type": kind,
            "details": details,
        }

    def _actor_name(self, principal: Principal) -> str:
        return principal.display_name

    def check_access(self, principal: Principal, item: dict) -> None:
        ws = item.get("workspace", "")
        if ws == "business":
            return
        if ws == f"practice:{principal.user_id}":
            return
        raise forbidden("This record belongs to another staff member's practice workspace.")

    def get(self, principal: Principal, inquiry_id: str) -> dict:
        item = self.store.get_inquiry(inquiry_id)
        if not item:
            raise not_found("Inquiry not found.")
        self.check_access(principal, item)
        return item

    def _save(self, item: dict, expected_version: int, events: list[dict]) -> dict:
        if item.get("version") != expected_version:
            raise conflict(
                "This inquiry changed since you opened it. Reload to see the latest version.",
                code="version_conflict",
                details={"currentVersion": item.get("version")},
            )
        updated = dict(item)
        updated["version"] = expected_version + 1
        updated["updatedAt"] = events[-1]["at"] if events else self._now()
        try:
            self.store.save_inquiry(updated, expected_version, events)
        except ConflictError:
            raise conflict(
                "This inquiry changed since you opened it. Reload to see the latest version.",
                code="version_conflict",
            ) from None
        return updated

    @staticmethod
    def _mark_reviewed(item: dict, principal: Principal, at: str) -> None:
        if not item.get("firstReviewedAt"):
            item["firstReviewedAt"] = at
            item["firstReviewedBy"] = principal.user_id

    # -- create -----------------------------------------------------------
    def create(
        self,
        principal: Principal,
        data: dict,
        workspace: str = "business",
        source: str = "staff_entry",
        extra: dict | None = None,
        analyze: bool = True,
    ) -> tuple[dict, dict | None]:
        at = self._now()
        inquiry_id = (extra or {}).get("id") or f"inq_{secrets.token_hex(6)}"
        item = {
            "id": inquiry_id,
            "workspace": workspace,
            "source": source,
            "createdAt": at,
            "updatedAt": at,
            "createdBy": principal.user_id,
            "version": 1,
            "channel": data["channel"],
            "customer": data["customer"],
            "message": data["message"],
            "status": "new",
            "category": None,
            "priority": None,
            "assignee": None,
            "draftReply": "",
            "staffEditedFields": [],
            "aiSuggestion": None,
            "analysisStatus": "not_started",
            "analysisError": None,
            "analysisAttempts": 0,
            "verification": None,
            "approvedResponse": None,
            "resolvedAt": None,
            "resolvedBy": None,
            "resolutionNote": None,
            "firstReviewedAt": None,
            "firstReviewedBy": None,
        }
        if extra:
            item.update({k: v for k, v in extra.items() if k != "id"})
        events = [self._event(inquiry_id, self._actor_name(principal), "created", at, channel=data["channel"], source=source)]
        try:
            self.store.create_inquiry(item, events)
        except ConflictError:
            raise conflict("An inquiry with this id already exists.", code="duplicate") from None
        log_event("inquiry_created", userId=principal.user_id, inquiryId=inquiry_id, workspace=workspace)
        if not analyze:
            return item, None
        return self.analyze(principal, inquiry_id, None)

    # -- analyze ----------------------------------------------------------
    def analyze(self, principal: Principal, inquiry_id: str, expected_version: int | None) -> tuple[dict, dict | None]:
        item = self.get(principal, inquiry_id)
        if expected_version is not None and item["version"] != expected_version:
            raise conflict("This inquiry changed since you opened it. Reload first.", code="version_conflict")
        if item["status"] not in ANALYZABLE:
            raise conflict("Approved or resolved inquiries cannot be re-analyzed.", code="invalid_transition")

        analysis, error = None, None
        try:
            provider = self._provider_factory()
            analysis = run_analysis(provider, item["message"], item["channel"], item["customer"])
        except AnalysisError as exc:
            error = {"code": exc.code, "message": exc.message, "retryable": exc.retryable}
            log_event("analysis_failed", userId=principal.user_id, inquiryId=inquiry_id, provider=self.config.ai_provider, errorCode=exc.code, retryable=exc.retryable)
        else:
            meta = analysis["meta"]
            log_event(
                "analysis_succeeded", userId=principal.user_id, inquiryId=inquiry_id, provider=meta["provider"], modelId=meta["modelId"],
                latencyMs=meta["latencyMs"], inputTokens=meta["inputTokens"], outputTokens=meta["outputTokens"],
                guardrailFlags=len(analysis["guardrails"]["injectionSignals"]) + len(analysis["guardrails"]["removedUngroundedFields"]),
            )

        # Apply to the latest version; retry if a staff edit landed during the model call.
        for _ in range(3):
            item = self.get(principal, inquiry_id)
            if item["status"] not in ANALYZABLE:
                raise conflict("The inquiry was approved or resolved while analysis was running.", code="invalid_transition")
            at = self._now()
            updated = dict(item)
            updated["analysisAttempts"] = item.get("analysisAttempts", 0) + 1
            if error:
                updated["analysisError"] = {**error, "at": at}
                if item.get("analysisStatus") != "succeeded":
                    updated["analysisStatus"] = "failed"
                if item["status"] == "new":
                    updated["status"] = "analysis_failed"
                events = [self._event(inquiry_id, "LeadRescue AI", "analysis_failed", at, code=error["code"], provider=self.config.ai_provider)]
            else:
                updated["aiSuggestion"] = analysis
                updated["analysisStatus"] = "succeeded"
                updated["analysisError"] = None
                edited = set(item.get("staffEditedFields", []))
                for field, source in (("category", "category"), ("priority", "priority"), ("draftReply", "draftReply")):
                    if field not in edited:
                        updated[field] = analysis[source]
                if item["status"] in ("new", "analysis_failed"):
                    updated["status"] = "awaiting_review"
                events = [
                    self._event(
                        inquiry_id, "LeadRescue AI", "analysis_succeeded", at,
                        provider=analysis["meta"]["provider"], modelId=analysis["meta"]["modelId"],
                        suggestedCategory=analysis["category"], suggestedPriority=analysis["priority"],
                        suspicious=analysis["suspiciousInstructions"],
                    )
                ]
            if updated["status"] != item["status"]:
                events.append(self._event(inquiry_id, "LeadRescue AI", "status_changed", at, fromStatus=item["status"], toStatus=updated["status"]))
            try:
                saved = self._save(updated, item["version"], events)
                return saved, error
            except ApiError as exc:
                if exc.code != "version_conflict":
                    raise
        raise conflict("Could not save the analysis because the inquiry kept changing. Retry.", code="version_conflict")

    # -- staff edits ------------------------------------------------------
    def update(self, principal: Principal, inquiry_id: str, expected_version: int, changes: dict) -> dict:
        item = self.get(principal, inquiry_id)
        if item["status"] not in EDITABLE:
            raise conflict("Resolved inquiries cannot be edited.", code="invalid_transition")
        at = self._now()
        actor = self._actor_name(principal)
        updated = dict(item)
        events = []
        edited = set(item.get("staffEditedFields", []))
        for field, value in changes.items():
            if item.get(field) == value:
                continue
            updated[field] = value
            edited.add(field)
            if field == "draftReply":
                events.append(self._event(inquiry_id, actor, "draft_saved", at, characters=len(value)))
            else:
                events.append(self._event(inquiry_id, actor, "field_changed", at, field=field, fromValue=item.get(field), toValue=value))
        if not events:
            return item
        updated["staffEditedFields"] = sorted(edited)
        self._mark_reviewed(updated, principal, at)
        if item["status"] == "approved":
            updated["approvedResponse"] = None
            updated["verification"] = None
            events.append(self._event(inquiry_id, actor, "approval_revoked", at, reason="Edited after approval"))
        new_status = "in_review"
        if new_status != item["status"]:
            updated["status"] = new_status
            events.append(self._event(inquiry_id, actor, "status_changed", at, fromStatus=item["status"], toStatus=new_status))
        saved = self._save(updated, expected_version, events)
        log_event("inquiry_updated", userId=principal.user_id, inquiryId=inquiry_id, count=len(events))
        return saved

    def approve(self, principal: Principal, inquiry_id: str, expected_version: int, checks: dict, draft: str | None) -> dict:
        item = self.get(principal, inquiry_id)
        if item["status"] not in APPROVABLE:
            raise conflict(f"An inquiry with status '{item['status']}' cannot be approved.", code="invalid_transition")
        suspicious = bool((item.get("aiSuggestion") or {}).get("suspiciousInstructions"))
        required = [k for k in VERIFICATION_KEYS if k != "suspiciousReviewed" or suspicious]
        missing = [k for k in required if not checks.get(k)]
        if missing:
            raise bad_request("Complete every human verification check before approving.", {"missingChecks": missing}, code="verification_required")
        text = draft if draft is not None else item.get("draftReply", "")
        if not text or len(text.strip()) < 20:
            raise bad_request("Write a response draft (at least 20 characters) before approving.", code="draft_required")
        if len(text) > 4000:
            raise bad_request("Draft must be 4,000 characters or fewer.")
        if not item.get("category") or not item.get("priority"):
            raise bad_request("Set a category and priority before approving.", code="classification_required")
        violations = check_draft_policy(text)
        if violations:
            raise ApiError(
                422, "draft_policy_violation",
                "The draft appears to make a commitment staff cannot make in a reply (price, availability, booking, or free service). Edit the draft and try again.",
                {"violations": violations},
            )
        at = self._now()
        actor = self._actor_name(principal)
        updated = dict(item)
        events = []
        if text != item.get("draftReply"):
            updated["draftReply"] = text
            updated["staffEditedFields"] = sorted(set(item.get("staffEditedFields", [])) | {"draftReply"})
            events.append(self._event(inquiry_id, actor, "draft_saved", at, characters=len(text)))
        updated["verification"] = {**{k: checks.get(k, False) for k in required}, "verifiedBy": principal.user_id, "verifiedAt": at}
        updated["approvedResponse"] = {"text": text, "approvedBy": principal.user_id, "approvedByName": actor, "approvedAt": at}
        updated["status"] = "approved"
        self._mark_reviewed(updated, principal, at)
        events.append(self._event(inquiry_id, actor, "approved", at, checks=required, delivery="not sent (copy only)"))
        events.append(self._event(inquiry_id, actor, "status_changed", at, fromStatus=item["status"], toStatus="approved"))
        saved = self._save(updated, expected_version, events)
        log_event("inquiry_approved", userId=principal.user_id, inquiryId=inquiry_id, fromStatus=item["status"], toStatus="approved")
        return saved

    def resolve(self, principal: Principal, inquiry_id: str, expected_version: int, note: str | None) -> dict:
        item = self.get(principal, inquiry_id)
        if item["status"] not in OPEN_STATUSES:
            raise conflict("This inquiry is already resolved.", code="invalid_transition")
        if not item.get("category"):
            raise bad_request("Set a category before resolving so results stay accurate.", code="classification_required")
        without_response = item["status"] != "approved"
        if without_response and (not note or len(note) < 5):
            raise bad_request(
                "No approved response exists. Add a resolution note (at least 5 characters) explaining how this was handled.",
                code="resolution_note_required",
            )
        at = self._now()
        actor = self._actor_name(principal)
        updated = dict(item)
        updated["status"] = "resolved"
        updated["resolvedAt"] = at
        updated["resolvedBy"] = principal.user_id
        updated["resolvedByName"] = actor
        updated["resolutionNote"] = note
        updated["resolvedWithoutResponse"] = without_response
        self._mark_reviewed(updated, principal, at)
        events = [
            self._event(inquiry_id, actor, "resolved", at, withoutApprovedResponse=without_response, note=bool(note)),
            self._event(inquiry_id, actor, "status_changed", at, fromStatus=item["status"], toStatus="resolved"),
        ]
        saved = self._save(updated, expected_version, events)
        log_event("inquiry_resolved", userId=principal.user_id, inquiryId=inquiry_id, fromStatus=item["status"], toStatus="resolved")
        return saved

    # -- listing ----------------------------------------------------------
    def list(self, principal: Principal, workspace: str, filters: dict) -> list[dict]:
        items = self.store.list_inquiries(workspace, self.config.list_limit)
        if workspace.startswith("practice:"):
            gen = max((i.get("practiceGeneration", 1) for i in items), default=1)
            items = [i for i in items if i.get("practiceGeneration", 1) == gen]
        q = (filters.get("q") or "").strip().lower()
        out = []
        for i in items:
            if filters.get("category") and i.get("category") != filters["category"]:
                continue
            if filters.get("priority") and i.get("priority") != filters["priority"]:
                continue
            if filters.get("status"):
                wanted = filters["status"]
                if wanted == "open" and i["status"] not in OPEN_STATUSES:
                    continue
                if wanted != "open" and i["status"] != wanted:
                    continue
            if filters.get("assignee"):
                if filters["assignee"] == "unassigned":
                    if i.get("assignee"):
                        continue
                elif i.get("assignee") != filters["assignee"]:
                    continue
            if q:
                hay = " ".join(
                    str(x or "")
                    for x in (i["id"], i["message"], i["customer"].get("name"), i["customer"].get("email"), (i.get("aiSuggestion") or {}).get("summary"))
                ).lower()
                if q not in hay:
                    continue
            out.append(i)
        return out


def summarize(item: dict) -> dict:
    """List-view projection (keeps payloads small)."""
    ai = item.get("aiSuggestion") or {}
    return {
        "id": item["id"],
        "createdAt": item["createdAt"],
        "updatedAt": item["updatedAt"],
        "status": item["status"],
        "category": item.get("category"),
        "priority": item.get("priority"),
        "assignee": item.get("assignee"),
        "customerName": item["customer"].get("name")
        or (ai.get("extracted") or {}).get("contactName")
        or item["customer"].get("email")
        or item["customer"].get("phone")
        or (ai.get("extracted") or {}).get("contactPhone"),
        "channel": item["channel"],
        "summary": ai.get("summary"),
        "preview": item["message"][:160],
        "analysisStatus": item.get("analysisStatus"),
        "suspicious": bool(ai.get("suspiciousInstructions")),
        "practiceCaseId": item.get("practiceCaseId"),
        "source": item.get("source"),
        "version": item["version"],
    }
