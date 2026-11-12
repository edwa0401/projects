"""Authentication and authorization (server side)."""

import time

import local_server
from conftest import OTHER_CLAIMS, Client

PROTECTED = [
    ("GET", "/api/config"),
    ("GET", "/api/inquiries"),
    ("POST", "/api/inquiries"),
    ("GET", "/api/inquiries/inq_abc123"),
    ("PATCH", "/api/inquiries/inq_abc123"),
    ("POST", "/api/inquiries/inq_abc123/approve"),
    ("POST", "/api/inquiries/inq_abc123/resolve"),
    ("POST", "/api/inquiries/inq_abc123/analyze"),
    ("GET", "/api/metrics"),
    ("GET", "/api/progress"),
    ("POST", "/api/practice/start"),
]


def test_every_route_requires_authentication(client):
    for method, path in PROTECTED:
        status, body, _ = client.call(method, path, {"x": 1}, key="abcdefgh1", claims=None)
        assert status == 401, (method, path)
        assert body["error"]["code"] == "unauthorized"


def test_health_is_public(client):
    assert client.call("GET", "/api/health", claims=None)[0] == 200


def test_non_staff_is_forbidden(client):
    status, body, _ = client.call("GET", "/api/inquiries", claims={"sub": "u1", "cognito:groups": "[customers]"})
    assert status == 403
    status, _, _ = client.call("GET", "/api/inquiries", claims={"sub": "u1"})
    assert status == 403


def test_group_claim_formats(client):
    for groups in ("staff", "[staff]", "[admin staff]", ["staff"]):
        assert client.call("GET", "/api/config", claims={"sub": "u1", "cognito:groups": groups})[0] == 200


def test_practice_records_are_private(client, other_client):
    client.post("/api/practice/start")
    _, body, _ = client.call("GET", "/api/inquiries", query={"workspace": "practice"})
    pid = body["items"][0]["id"]
    status, _, _ = other_client.call("GET", f"/api/inquiries/{pid}")
    assert status == 403
    _, other_list, _ = other_client.call("GET", "/api/inquiries", query={"workspace": "practice"})
    assert other_list["items"] == []


def test_unknown_route_and_method(client):
    assert client.call("GET", "/api/nope")[0] == 404
    assert client.call("DELETE", "/api/inquiries")[0] == 405


def test_demo_tokens_sign_verify_expire_and_reject_tampering():
    token, exp = local_server.issue_token({"id": "maya", "name": "Maya Chen"}, minutes=1)
    claims, err = local_server.verify_token(token)
    assert err is None and claims["sub"] == "demo-maya" and claims["cognito:groups"] == "[staff]"
    prefix, body, sig = token.split(".")
    assert local_server.verify_token(f"{prefix}.{body}.{sig[:-2]}xx")[1] == "invalid_token"
    assert local_server.verify_token("garbage")[1] == "invalid_token"
    expired, _ = local_server.issue_token({"id": "maya", "name": "Maya Chen"}, minutes=0)
    time.sleep(0.01)
    assert local_server.verify_token(expired)[1] == "session_expired"
