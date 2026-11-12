"""Environment-based configuration. No secrets are embedded here."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

DEFAULT_STAFF = [
    {"id": "maya", "name": "Maya Chen", "role": "Customer care lead"},
    {"id": "jordan", "name": "Jordan Reyes", "role": "Move coordinator"},
    {"id": "sam", "name": "Sam Patel", "role": "Dispatch"},
    {"id": "alex", "name": "Alex Brooks", "role": "Sales estimator"},
]


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


@dataclass(frozen=True)
class Config:
    ai_provider: str = "demo"  # demo | bedrock
    store: str = "local"  # local | dynamodb
    auth_mode: str = "jwt"  # claims are always read from requestContext; see auth.py
    staff_group: str = "staff"
    staff_directory: list = field(default_factory=lambda: list(DEFAULT_STAFF))

    bedrock_model_id: str | None = None
    bedrock_region: str | None = None
    bedrock_max_tokens: int = 1500
    bedrock_tool_choice: str = "auto"  # auto | tool (forced tool choice is rejected by some newer models)
    bedrock_read_timeout: int = 20

    table_inquiries: str | None = None
    table_audit: str | None = None
    table_achievements: str | None = None
    table_idempotency: str | None = None

    local_data_file: str = "data/local/leadrescue-db.json"
    idempotency_ttl_seconds: int = 24 * 3600
    list_limit: int = 500

    @property
    def mode(self) -> str:
        return "live" if self.ai_provider == "bedrock" else "demo"

    @staticmethod
    def from_env() -> "Config":
        staff_raw = _env("STAFF_DIRECTORY")
        staff = DEFAULT_STAFF
        if staff_raw:
            parsed = json.loads(staff_raw)
            if not isinstance(parsed, list) or not all(
                isinstance(s, dict) and isinstance(s.get("id"), str) and isinstance(s.get("name"), str)
                for s in parsed
            ):
                raise ValueError("STAFF_DIRECTORY must be a JSON list of {id, name} objects")
            staff = parsed
        provider = (_env("AI_PROVIDER", "demo") or "demo").lower()
        if provider not in ("demo", "bedrock"):
            raise ValueError("AI_PROVIDER must be 'demo' or 'bedrock'")
        store = (_env("STORE", "local") or "local").lower()
        if store not in ("local", "dynamodb"):
            raise ValueError("STORE must be 'local' or 'dynamodb'")
        tool_choice = (_env("BEDROCK_TOOL_CHOICE", "auto") or "auto").lower()
        if tool_choice not in ("auto", "tool"):
            raise ValueError("BEDROCK_TOOL_CHOICE must be 'auto' or 'tool'")
        return Config(
            ai_provider=provider,
            store=store,
            staff_group=_env("STAFF_GROUP", "staff") or "staff",
            staff_directory=list(staff),
            bedrock_model_id=_env("BEDROCK_MODEL_ID"),
            bedrock_region=_env("BEDROCK_REGION") or _env("AWS_REGION"),
            bedrock_max_tokens=int(_env("BEDROCK_MAX_TOKENS", "1500") or 1500),
            bedrock_tool_choice=tool_choice,
            bedrock_read_timeout=int(_env("BEDROCK_READ_TIMEOUT", "20") or 20),
            table_inquiries=_env("TABLE_INQUIRIES"),
            table_audit=_env("TABLE_AUDIT"),
            table_achievements=_env("TABLE_ACHIEVEMENTS"),
            table_idempotency=_env("TABLE_IDEMPOTENCY"),
            local_data_file=_env("LOCAL_DATA_FILE", "data/local/leadrescue-db.json")
            or "data/local/leadrescue-db.json",
        )

    def staff_ids(self) -> set[str]:
        return {s["id"] for s in self.staff_directory}
