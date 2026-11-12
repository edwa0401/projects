"""Storage interface implemented by LocalStore (demo) and DynamoStore (AWS)."""

from __future__ import annotations

from typing import Protocol


class Store(Protocol):
    def create_inquiry(self, item: dict, audit_events: list[dict]) -> None:
        """Insert a new inquiry and its audit events atomically. Raises ConflictError if the id exists."""

    def get_inquiry(self, inquiry_id: str) -> dict | None: ...

    def save_inquiry(self, item: dict, expected_version: int, audit_events: list[dict]) -> None:
        """Replace an inquiry only if its stored version equals expected_version, and append
        audit events, atomically. Raises ConflictError on version mismatch."""

    def list_inquiries(self, workspace: str, limit: int) -> list[dict]: ...

    def list_audit(self, inquiry_id: str) -> list[dict]: ...

    def put_award_if_absent(self, user_id: str, award_key: str, item: dict) -> bool:
        """Insert an award record once. Returns False if it already existed (duplicate prevention)."""

    def list_awards(self, user_id: str) -> list[dict]: ...

    def idem_reserve(self, key: str, record: dict) -> dict | None:
        """Reserve an idempotency key. Returns None when newly reserved, else the existing record."""

    def idem_complete(self, key: str, record: dict) -> None: ...

    def idem_release(self, key: str) -> None: ...
