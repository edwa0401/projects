"""File-backed store for demo mode. Persists to a single JSON file with atomic writes.

Same semantics as DynamoStore: conditional creates, optimistic version checks,
and insert-once awards. Thread-safe within one process (the local dev server).
"""

from __future__ import annotations

import copy
import json
import os
import threading
import time

from ..errors import ConflictError


class LocalStore:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self._data = {"inquiries": {}, "audit": {}, "awards": {}, "idempotency": {}}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                loaded = json.load(f)
            for key in self._data:
                self._data[key] = loaded.get(key, {})

    # -- persistence ---------------------------------------------------
    def _flush(self) -> None:
        directory = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(directory, exist_ok=True)
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=1, sort_keys=True)
        os.replace(tmp, self.path)

    def is_empty(self) -> bool:
        with self._lock:
            return not self._data["inquiries"]

    # -- inquiries -----------------------------------------------------
    def create_inquiry(self, item: dict, audit_events: list[dict]) -> None:
        with self._lock:
            if item["id"] in self._data["inquiries"]:
                raise ConflictError(item["id"])
            self._data["inquiries"][item["id"]] = copy.deepcopy(item)
            self._data["audit"].setdefault(item["id"], []).extend(copy.deepcopy(audit_events))
            self._flush()

    def get_inquiry(self, inquiry_id: str) -> dict | None:
        with self._lock:
            item = self._data["inquiries"].get(inquiry_id)
            return copy.deepcopy(item) if item else None

    def save_inquiry(self, item: dict, expected_version: int, audit_events: list[dict]) -> None:
        with self._lock:
            current = self._data["inquiries"].get(item["id"])
            if current is None or current.get("version") != expected_version:
                raise ConflictError(item["id"])
            self._data["inquiries"][item["id"]] = copy.deepcopy(item)
            self._data["audit"].setdefault(item["id"], []).extend(copy.deepcopy(audit_events))
            self._flush()

    def list_inquiries(self, workspace: str, limit: int) -> list[dict]:
        with self._lock:
            items = [copy.deepcopy(i) for i in self._data["inquiries"].values() if i.get("workspace") == workspace]
        items.sort(key=lambda i: i["createdAt"], reverse=True)
        return items[:limit]

    def list_audit(self, inquiry_id: str) -> list[dict]:
        with self._lock:
            events = copy.deepcopy(self._data["audit"].get(inquiry_id, []))
        events.sort(key=lambda e: (e["at"], e["id"]))
        return events

    # -- awards --------------------------------------------------------
    def put_award_if_absent(self, user_id: str, award_key: str, item: dict) -> bool:
        with self._lock:
            awards = self._data["awards"].setdefault(user_id, {})
            if award_key in awards:
                return False
            awards[award_key] = copy.deepcopy(item)
            self._flush()
            return True

    def list_awards(self, user_id: str) -> list[dict]:
        with self._lock:
            return copy.deepcopy(list(self._data["awards"].get(user_id, {}).values()))

    # -- idempotency ---------------------------------------------------
    def idem_reserve(self, key: str, record: dict) -> dict | None:
        with self._lock:
            existing = self._data["idempotency"].get(key)
            if existing and existing.get("expiresAt", 0) > time.time():
                return copy.deepcopy(existing)
            self._data["idempotency"][key] = copy.deepcopy(record)
            self._flush()
            return None

    def idem_complete(self, key: str, record: dict) -> None:
        with self._lock:
            self._data["idempotency"][key] = copy.deepcopy(record)
            self._flush()

    def idem_release(self, key: str) -> None:
        with self._lock:
            self._data["idempotency"].pop(key, None)
            self._flush()
