"""Local development server for LeadRescue (demo mode).

- Emulates API Gateway: converts HTTP requests into HTTP API v2 events and calls
  the same handler code that runs in Lambda.
- Demo staff sign-in: issues short-lived HMAC-signed session tokens (clearly not
  Cognito) and injects verified claims exactly where API Gateway's JWT
  authorizer would. Expired or tampered tokens get 401.
- Seeds synthetic business data on first start and persists to a local JSON file.
- Optionally serves the built frontend (frontend/dist) with SPA fallback.

Usage: python backend/local_server.py [--port 8787] [--reset]
Requires no AWS credentials when AI_PROVIDER=demo (the default).
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))

from leadrescue.api import build_app  # noqa: E402
from leadrescue.auth import Principal  # noqa: E402
from leadrescue.config import Config  # noqa: E402
from leadrescue.service import InquiryService, iso  # noqa: E402
from leadrescue.store.local import LocalStore  # noqa: E402
from leadrescue.analysis.demo_provider import DemoProvider  # noqa: E402

DIST = HERE.parent / "frontend" / "dist"
SESSION_MINUTES = int(os.environ.get("DEMO_SESSION_MINUTES", "60"))
# A random per-process secret: restarting the server signs everyone out. Nothing to leak or commit.
_SECRET = os.environ.get("DEMO_TOKEN_SECRET") or secrets.token_hex(32)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def issue_token(staff: dict, minutes: int = SESSION_MINUTES) -> tuple[str, int]:
    exp = int(time.time()) + minutes * 60
    payload = {"sub": f"demo-{staff['id']}", "username": staff["id"], "name": staff["name"],
               "cognito:groups": "[staff]", "exp": exp, "token_use": "demo"}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_SECRET.encode(), body.encode(), hashlib.sha256).digest())
    return f"demo.{body}.{sig}", exp


def verify_token(token: str) -> tuple[dict | None, str | None]:
    try:
        prefix, body, sig = token.split(".")
    except ValueError:
        return None, "invalid_token"
    expected = _b64(hmac.new(_SECRET.encode(), body.encode(), hashlib.sha256).digest())
    if prefix != "demo" or not hmac.compare_digest(sig, expected):
        return None, "invalid_token"
    claims = json.loads(_unb64(body))
    if claims.get("exp", 0) < time.time():
        return None, "session_expired"
    return claims, None


def seed_if_empty(config: Config, store: LocalStore) -> None:
    if not store.is_empty():
        return
    seed = json.loads((HERE / "data" / "seed_inquiries.json").read_text())
    base = datetime.now(timezone.utc).replace(microsecond=0)
    staff = {s["id"]: s for s in config.staff_directory}
    for n, entry in enumerate(seed["inquiries"]):
        created = base - timedelta(hours=entry["ageHours"])
        clock_state = {"t": created}
        svc = InquiryService(config, store, lambda: DemoProvider(), clock=lambda: clock_state["t"])
        system = Principal("seed-system", "intake", "Web intake", ("staff",))
        data = {"message": entry["message"], "channel": entry["channel"],
                "customer": {"name": None, "email": None, "phone": None, **entry["customer"]}}
        item, _ = svc.create(system, data, source="seed", extra={"id": f"inq_seed{n:02d}"})
        h = entry.get("history", {})
        reviewer_id = h.get("assignee", "maya")
        reviewer = Principal(f"demo-{reviewer_id}", reviewer_id, staff[reviewer_id]["name"], ("staff",))
        if "reviewAfterMin" in h:
            clock_state["t"] = created + timedelta(minutes=h["reviewAfterMin"])
            changes = {"assignee": h.get("assignee", reviewer_id)}
            for k in ("category", "priority"):
                if k in h:
                    changes[k] = h[k]
            item = svc.update(reviewer, item["id"], item["version"], changes)
        if "approveAfterMin" in h:
            clock_state["t"] = created + timedelta(minutes=h["approveAfterMin"])
            checks = {"factsChecked": True, "noCommitments": True, "categoryPriorityReviewed": True, "suspiciousReviewed": True}
            item = svc.approve(reviewer, item["id"], item["version"], checks, None)
        if "resolveAfterMin" in h:
            clock_state["t"] = created + timedelta(minutes=h["resolveAfterMin"])
            item = svc.resolve(reviewer, item["id"], item["version"], None)
    print(f"[leadrescue] Seeded {len(seed['inquiries'])} synthetic business inquiries.", flush=True)


class Handler(BaseHTTPRequestHandler):
    app = None
    config: Config = None
    cors_origins: set[str] = set()
    server_version = "LeadRescueLocal/1.0"

    def log_message(self, fmt, *args):  # request logging is done by the app (no bodies)
        pass

    def _send(self, status: int, body: bytes, headers: dict) -> None:
        self.send_response(status)
        origin = self.headers.get("Origin")
        if origin and origin in self.cors_origins:
            headers = {**headers, "access-control-allow-origin": origin, "vary": "Origin",
                       "access-control-allow-headers": "authorization,content-type,idempotency-key",
                       "access-control-allow-methods": "GET,POST,PATCH,OPTIONS"}
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, payload) -> None:
        self._send(status, json.dumps(payload).encode(), {"content-type": "application/json", "cache-control": "no-store"})

    def _read_body(self) -> str | None:
        length = int(self.headers.get("content-length") or 0)
        if length > 70_000:
            return "\x00too-large"
        return self.rfile.read(length).decode("utf-8") if length else None

    def _dispatch(self):
        url = urlsplit(self.path)
        if url.path.startswith("/api/demo/"):
            return self._demo_routes(url.path)
        if url.path.startswith("/api/"):
            return self._api(url)
        return self._static(url.path)

    do_GET = do_POST = do_PATCH = do_OPTIONS = do_HEAD = lambda self: self._dispatch()  # noqa: E731

    def _demo_routes(self, path: str):
        if path == "/api/demo/staff" and self.command == "GET":
            return self._json(200, {"staff": self.config.staff_directory, "sessionMinutes": SESSION_MINUTES})
        if path == "/api/demo/session" and self.command == "POST":
            raw = self._read_body() or "{}"
            try:
                staff_id = json.loads(raw).get("staffId")
            except (json.JSONDecodeError, AttributeError):
                staff_id = None
            staff = next((s for s in self.config.staff_directory if s["id"] == staff_id), None)
            if not staff:
                return self._json(400, {"error": {"code": "validation_error", "message": "Choose a demo staff profile."}})
            minutes = SESSION_MINUTES
            try:
                minutes = max(1, min(int(json.loads(raw).get("minutes", SESSION_MINUTES)), SESSION_MINUTES))
            except (TypeError, ValueError):
                pass
            token, exp = issue_token(staff, minutes)
            return self._json(200, {"token": token, "expiresAt": exp, "user": {"id": f"demo-{staff['id']}", "name": staff["name"]}})
        if self.command == "OPTIONS":
            return self._send(204, b"", {})
        return self._json(404, {"error": {"code": "not_found", "message": "Route not found."}})

    def _api(self, url):
        body = self._read_body()
        if body == "\x00too-large":
            return self._json(413, {"error": {"code": "payload_too_large", "message": "Request body is too large."}})
        headers = {k.lower(): v for k, v in self.headers.items()}
        request_context = {"http": {"method": self.command, "path": url.path}, "requestId": uuid.uuid4().hex}
        auth = headers.get("authorization", "")
        if auth.startswith("Bearer "):
            claims, err = verify_token(auth[7:])
            if err and url.path != "/api/health":
                msg = "Your session expired. Sign in again." if err == "session_expired" else "Sign in to continue."
                return self._json(401, {"error": {"code": err, "message": msg}})
            if claims:
                request_context["authorizer"] = {"jwt": {"claims": claims}}
        event = {
            "version": "2.0",
            "rawPath": url.path,
            "rawQueryString": url.query,
            "queryStringParameters": dict(parse_qsl(url.query)) or None,
            "headers": headers,
            "requestContext": request_context,
            "body": body,
            "isBase64Encoded": False,
        }
        resp = self.app.handle(event)
        self._send(resp["statusCode"], (resp.get("body") or "").encode(), resp.get("headers", {}))

    def _static(self, path: str):
        if not DIST.exists():
            return self._send(200, b"LeadRescue API is running. Start the frontend with `npm run dev` (port 5173) or build it with `npm run build`.",
                              {"content-type": "text/plain"})
        target = (DIST / path.lstrip("/")).resolve()
        if not str(target).startswith(str(DIST.resolve())) or not target.is_file():
            target = DIST / "index.html"  # SPA fallback
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        cache = "no-cache" if target.name == "index.html" else "public, max-age=31536000, immutable"
        self._send(200, target.read_bytes(), {"content-type": ctype, "cache-control": cache})


def main():
    parser = argparse.ArgumentParser(description="LeadRescue local server (demo mode)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8787")))
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--reset", action="store_true", help="delete local data and reseed")
    args = parser.parse_args()

    os.environ.setdefault("LOCAL_DATA_FILE", str(HERE / "data" / "local" / "leadrescue-db.json"))
    config = Config.from_env()
    if config.store != "local":
        sys.exit("local_server.py only supports STORE=local.")
    if args.reset and os.path.exists(config.local_data_file):
        os.remove(config.local_data_file)
        print("[leadrescue] Local data reset.", flush=True)
    store = LocalStore(config.local_data_file)
    seed_if_empty(config, store)
    Handler.app = build_app(config, store)
    Handler.config = config
    Handler.cors_origins = {o.strip() for o in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()}
    mode = "DEMO (simulated analysis, synthetic data, local storage)" if config.ai_provider == "demo" else f"LIVE AI via Bedrock model {config.bedrock_model_id} (local storage)"
    print(f"[leadrescue] Mode: {mode}", flush=True)
    print(f"[leadrescue] Data file: {config.local_data_file}", flush=True)
    print(f"[leadrescue] Listening on http://{args.host}:{args.port}", flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
