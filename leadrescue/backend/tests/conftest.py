import json
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from leadrescue.api import App  # noqa: E402
from leadrescue.config import Config  # noqa: E402
from leadrescue.store.local import LocalStore  # noqa: E402

STAFF_CLAIMS = {"sub": "user-maya", "username": "maya", "cognito:groups": "[staff]"}
OTHER_CLAIMS = {"sub": "user-jordan", "username": "jordan", "cognito:groups": "[staff admin]"}


class Client:
    def __init__(self, app: App, claims=STAFF_CLAIMS):
        self.app = app
        self.claims = claims

    def call(self, method, path, body=None, query=None, key=None, claims="default", raw_body=None):
        headers = {"content-type": "application/json"}
        if key is not None:
            headers["Idempotency-Key"] = key
        rc = {"http": {"method": method, "path": path}, "requestId": uuid.uuid4().hex}
        c = self.claims if claims == "default" else claims
        if c is not None:
            rc["authorizer"] = {"jwt": {"claims": c}}
        event = {
            "rawPath": path,
            "queryStringParameters": query,
            "headers": headers,
            "requestContext": rc,
            "body": raw_body if raw_body is not None else (json.dumps(body) if body is not None else None),
        }
        resp = self.app.handle(event)
        payload = json.loads(resp["body"]) if resp["body"] else None
        return resp["statusCode"], payload, resp["headers"]

    def post(self, path, body=None, key="auto", **kw):
        if key == "auto":
            key = uuid.uuid4().hex
        return self.call("POST", path, body, key=key, **kw)

    def create(self, message="I need a quote to move a two-bedroom apartment from Sherman to Denison next Saturday.", **extra):
        status, payload, _ = self.post("/api/inquiries", {"message": message, "channel": "web_form", **extra})
        assert status == 201, payload
        return payload


@pytest.fixture
def config(tmp_path):
    return Config(ai_provider="demo", store="local", local_data_file=str(tmp_path / "db.json"))


@pytest.fixture
def store(config):
    return LocalStore(config.local_data_file)


@pytest.fixture
def app(config, store):
    return App(config, store)


@pytest.fixture
def client(app):
    return Client(app)


@pytest.fixture
def other_client(app):
    return Client(app, OTHER_CLAIMS)


FULL_CHECKS = {"factsChecked": True, "noCommitments": True, "categoryPriorityReviewed": True, "suspiciousReviewed": True}
