"""HTTP API router for API Gateway HTTP API (payload format 2.0) and the local dev server.

Routes (all require a staff JWT except /api/health):
  GET   /api/health
  GET   /api/config
  GET   /api/inquiries                 ?workspace=business|practice &q &category &priority &status &assignee
  POST  /api/inquiries                 Idempotency-Key required
  GET   /api/inquiries/{id}
  POST  /api/inquiries/{id}/analyze    Idempotency-Key required
  PATCH /api/inquiries/{id}            save draft / staff corrections (expectedVersion)
  POST  /api/inquiries/{id}/approve    Idempotency-Key required
  POST  /api/inquiries/{id}/resolve    Idempotency-Key required
  GET   /api/metrics
  GET   /api/progress
  POST  /api/practice/start            idempotent by design (creates cases once)
  POST  /api/practice/reset            Idempotency-Key required
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import time
import uuid

from . import metrics as metrics_mod
from . import practice
from .analysis.contract import CATEGORIES, EXTRACTED_FIELDS, PRIORITIES
from .analysis.provider import get_provider
from .auth import Principal, principal_from_event
from .config import Config
from .errors import ApiError, ConflictError, bad_request, conflict, not_found
from .logging_util import log_event
from .service import STATUSES, InquiryService, summarize
from .validation import (
    CHANNELS,
    validate_approve,
    validate_create,
    validate_expected_version_only,
    validate_resolve,
    validate_update,
)

_ID = r"(?P<id>[A-Za-z0-9_\-]{3,80})"
_IDEM_KEY_RE = re.compile(r"^[A-Za-z0-9_\-]{8,100}$")


class App:
    def __init__(self, config: Config, store, provider_factory=None, clock=None):
        self.config = config
        self.store = store
        self.service = InquiryService(config, store, provider_factory or (lambda: get_provider(config)), clock)
        self.routes = [
            ("GET", r"^/api/health$", self.health, False, False),
            ("GET", r"^/api/config$", self.get_config, True, False),
            ("GET", r"^/api/inquiries$", self.list_inquiries, True, False),
            ("POST", r"^/api/inquiries$", self.create_inquiry, True, True),
            ("GET", rf"^/api/inquiries/{_ID}$", self.get_inquiry, True, False),
            ("PATCH", rf"^/api/inquiries/{_ID}$", self.update_inquiry, True, False),
            ("POST", rf"^/api/inquiries/{_ID}/analyze$", self.analyze_inquiry, True, True),
            ("POST", rf"^/api/inquiries/{_ID}/approve$", self.approve_inquiry, True, True),
            ("POST", rf"^/api/inquiries/{_ID}/resolve$", self.resolve_inquiry, True, True),
            ("GET", r"^/api/metrics$", self.get_metrics, True, False),
            ("GET", r"^/api/progress$", self.get_progress, True, False),
            ("POST", r"^/api/practice/start$", self.practice_start, True, False),
            ("POST", r"^/api/practice/reset$", self.practice_reset, True, True),
        ]

    # -- entry -----------------------------------------------------------
    def handle(self, event: dict) -> dict:
        started = time.perf_counter()
        http = (event.get("requestContext") or {}).get("http") or {}
        method = (http.get("method") or "GET").upper()
        path = event.get("rawPath") or http.get("path") or "/"
        request_id = (event.get("requestContext") or {}).get("requestId") or uuid.uuid4().hex
        route_name, user_id, status = "unmatched", None, 500
        try:
            if method == "OPTIONS":
                status = 204
                return _response(204, None)
            matched = None
            path_allowed = False
            for r_method, pattern, fn, needs_auth, needs_idem in self.routes:
                m = re.match(pattern, path)
                if m:
                    path_allowed = True
                    if r_method == method:
                        matched = (fn, m.groupdict(), needs_auth, needs_idem, f"{method} {fn.__name__}")
                        break
            if not matched:
                raise ApiError(405, "method_not_allowed", "Method not allowed.") if path_allowed else not_found("Route not found.")
            fn, params, needs_auth, needs_idem, route_name = matched
            principal = principal_from_event(event, self.config) if needs_auth else None
            user_id = principal.user_id if principal else None
            body = _parse_body(event)
            query = event.get("queryStringParameters") or {}
            if needs_idem:
                status, payload, replay = self._idempotent(principal, method, path, event, body, lambda: fn(principal, params, body, query))
                resp = _response(status, payload)
                if replay:
                    resp["headers"]["idempotent-replay"] = "true"
                return resp
            status, payload = fn(principal, params, body, query)
            return _response(status, payload)
        except ApiError as exc:
            status = exc.status
            return _response(exc.status, exc.to_body())
        except Exception as exc:  # never leak internals
            status = 500
            log_event("unhandled_error", level=40, requestId=request_id, errorCode=type(exc).__name__, route=route_name)
            return _response(500, {"error": {"code": "internal_error", "message": "Something went wrong. Your data was not changed unless shown otherwise. Try again."}})
        finally:
            log_event("request", requestId=request_id, method=method, route=route_name, status=status,
                      latencyMs=int((time.perf_counter() - started) * 1000), userId=user_id)

    def _idempotent(self, principal: Principal, method, path, event, body, run):
        headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
        key = headers.get("idempotency-key")
        if not key or not _IDEM_KEY_RE.match(key):
            raise bad_request("An Idempotency-Key header (8-100 letters, digits, '-' or '_') is required.", code="idempotency_key_required")
        scoped = f"{principal.user_id}:{method}:{path}:{key}"
        fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        now = int(time.time())
        existing = self.store.idem_reserve(scoped, {"state": "in_progress", "fingerprint": fingerprint, "expiresAt": now + 90})
        if existing is not None:
            if existing.get("fingerprint") and existing["fingerprint"] != fingerprint:
                raise ApiError(422, "idempotency_key_reused", "This Idempotency-Key was already used with a different request.")
            if existing.get("state") == "completed":
                log_event("idempotent_replay", userId=principal.user_id, route=path, idempotent=True)
                return existing["status"], existing["response"], True
            raise conflict("The same request is already being processed. Wait a moment and refresh.", code="request_in_progress")
        try:
            status, payload = run()
        except BaseException:
            self.store.idem_release(scoped)  # failed requests can be retried with the same key
            raise
        self.store.idem_complete(scoped, {"state": "completed", "fingerprint": fingerprint, "status": status, "response": payload,
                                          "expiresAt": now + self.config.idempotency_ttl_seconds})
        return status, payload, False

    # -- handlers --------------------------------------------------------
    def health(self, *_):
        return 200, {"ok": True}

    def get_config(self, principal, *_):
        return 200, {
            "mode": self.config.mode,
            "aiProvider": self.config.ai_provider,
            "modelId": self.config.bedrock_model_id if self.config.ai_provider == "bedrock" else "demo-rules-v1",
            "store": self.config.store,
            "staff": self.config.staff_directory,
            "categories": CATEGORIES,
            "priorities": PRIORITIES,
            "statuses": STATUSES,
            "channels": CHANNELS,
            "extractedFields": EXTRACTED_FIELDS,
            "user": {"id": principal.user_id, "username": principal.username, "name": principal.display_name},
        }

    def _workspace(self, principal, query) -> str:
        ws = (query.get("workspace") or "business").lower()
        if ws == "business":
            return "business"
        if ws == "practice":
            return practice.workspace_for(principal.user_id)
        raise bad_request("workspace must be 'business' or 'practice'.")

    def list_inquiries(self, principal, params, body, query):
        ws = self._workspace(principal, query)
        filters = {k: query.get(k) for k in ("q", "category", "priority", "status", "assignee") if query.get(k)}
        if filters.get("category") and filters["category"] not in CATEGORIES:
            raise bad_request("Unknown category filter.")
        if filters.get("priority") and filters["priority"] not in PRIORITIES:
            raise bad_request("Unknown priority filter.")
        if filters.get("status") and filters["status"] not in STATUSES + ["open"]:
            raise bad_request("Unknown status filter.")
        if filters.get("q") and len(filters["q"]) > 200:
            raise bad_request("Search text is too long.")
        items = self.service.list(principal, ws, filters)
        all_items = self.service.list(principal, ws, {}) if filters else items
        counts = {
            "awaitingReview": sum(1 for i in all_items if i["status"] in ("new", "analysis_failed", "awaiting_review", "in_review")),
            "urgentOpen": sum(1 for i in all_items if i.get("priority") == "urgent" and i["status"] not in ("resolved",)),
            "approvedDrafts": sum(1 for i in all_items if i["status"] == "approved"),
            "total": len(all_items),
        }
        return 200, {"items": [summarize(i) for i in items], "counts": counts, "workspace": "practice" if ws != "business" else "business"}

    def _detail(self, principal, item, extra=None):
        payload = {"inquiry": item, "audit": self.store.list_audit(item["id"])}
        if extra:
            payload.update(extra)
        return payload

    def create_inquiry(self, principal, params, body, query):
        data = validate_create(body)
        item, error = self.service.create(principal, data)
        return 201, self._detail(principal, item, {"analysisError": error})

    def get_inquiry(self, principal, params, body, query):
        item = self.service.get(principal, params["id"])
        return 200, self._detail(principal, item)

    def analyze_inquiry(self, principal, params, body, query):
        expected = validate_expected_version_only(body)
        item, error = self.service.analyze(principal, params["id"], expected)
        return 200, self._detail(principal, item, {"analysisError": error})

    def update_inquiry(self, principal, params, body, query):
        version, changes = validate_update(body, self.config.staff_ids())
        item = self.service.update(principal, params["id"], version, changes)
        return 200, self._detail(principal, item)

    def _awards_for(self, principal, item):
        if item.get("workspace") == practice.workspace_for(principal.user_id):
            granted = practice.evaluate_and_award(self.store, principal.user_id, item, item["updatedAt"])
            if granted:
                log_event("xp_awarded", userId=principal.user_id, inquiryId=item["id"], awardCount=len(granted))
            return granted
        return []

    def approve_inquiry(self, principal, params, body, query):
        version, checks, draft = validate_approve(body)
        item = self.service.approve(principal, params["id"], version, checks, draft)
        return 200, self._detail(principal, item, {"awards": self._awards_for(principal, item)})

    def resolve_inquiry(self, principal, params, body, query):
        version, note = validate_resolve(body)
        item = self.service.resolve(principal, params["id"], version, note)
        return 200, self._detail(principal, item, {"awards": self._awards_for(principal, item)})

    def get_metrics(self, principal, params, body, query):
        items = self.store.list_inquiries("business", self.config.list_limit)
        return 200, metrics_mod.compute(items)

    def _practice_records(self, principal):
        return self.service.list(principal, practice.workspace_for(principal.user_id), {})

    def get_progress(self, principal, params, body, query):
        return 200, practice.progress(self.store, principal.user_id, self._practice_records(principal))

    def _create_practice_cases(self, principal, generation: int):
        ws = practice.workspace_for(principal.user_id)
        for case in practice.CASES:
            data = {"message": case["message"], "channel": case["channel"], "customer": dict(case["customer"])}
            extra = {"id": practice.practice_inquiry_id(principal.user_id, generation, case["caseId"]),
                     "practiceCaseId": case["caseId"], "practiceGeneration": generation, "practiceTitle": case["title"]}
            try:
                self.service.create(principal, data, workspace=ws, source="practice", extra=extra)
            except ApiError as exc:
                if exc.code != "duplicate":  # already created by a concurrent/duplicate start
                    raise

    def practice_start(self, principal, params, body, query):
        records = self.store.list_inquiries(practice.workspace_for(principal.user_id), self.config.list_limit)
        generation = max((r.get("practiceGeneration", 1) for r in records), default=1)
        existing = {r.get("practiceCaseId") for r in records if r.get("practiceGeneration", 1) == generation}
        if not set(practice.CASE_IDS) <= existing:
            self._create_practice_cases(principal, generation)
        return 200, practice.progress(self.store, principal.user_id, self._practice_records(principal))

    def practice_reset(self, principal, params, body, query):
        records = self.store.list_inquiries(practice.workspace_for(principal.user_id), self.config.list_limit)
        generation = max((r.get("practiceGeneration", 0) for r in records), default=0) + 1
        self._create_practice_cases(principal, generation)
        return 200, practice.progress(self.store, principal.user_id, self._practice_records(principal))


def _parse_body(event: dict):
    raw = event.get("body")
    if raw is None or raw == "":
        return None
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    if len(raw) > 64_000:
        raise ApiError(413, "payload_too_large", "Request body is too large.")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise bad_request("Request body must be valid JSON.") from None


def _response(status: int, payload) -> dict:
    headers = {"content-type": "application/json", "cache-control": "no-store", "x-content-type-options": "nosniff"}
    return {"statusCode": status, "headers": headers, "body": "" if payload is None else json.dumps(payload)}


# -- Lambda entry --------------------------------------------------------
_APP: App | None = None


def build_app(config: Config | None = None, store=None, provider_factory=None, clock=None) -> App:
    config = config or Config.from_env()
    if store is None:
        if config.store == "dynamodb":
            from .store.dynamo import DynamoStore

            store = DynamoStore(config)
        else:
            from .store.local import LocalStore

            store = LocalStore(config.local_data_file)
    return App(config, store, provider_factory, clock)


def lambda_handler(event, context):
    global _APP
    if _APP is None:
        _APP = build_app()
    return _APP.handle(event)


__all__ = ["App", "build_app", "lambda_handler", "ConflictError"]
