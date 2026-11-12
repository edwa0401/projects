"""Inquiry creation, input validation, and missing-field handling."""

from conftest import Client


def test_create_saves_and_analyzes(client):
    payload = client.create()
    inq = payload["inquiry"]
    assert inq["status"] == "awaiting_review"
    assert inq["analysisStatus"] == "succeeded"
    assert inq["category"] == "quote"
    assert inq["aiSuggestion"]["meta"]["provider"] == "demo"
    assert inq["aiSuggestion"]["meta"]["confidenceCalibrated"] is False
    types = [e["type"] for e in payload["audit"]]
    assert types[0] == "created" and "analysis_succeeded" in types
    # persisted
    status, detail, _ = client.call("GET", f"/api/inquiries/{inq['id']}")
    assert status == 200 and detail["inquiry"]["id"] == inq["id"]


def test_create_validation_errors(client):
    status, body, _ = client.post("/api/inquiries", {"message": "short"})
    assert status == 400 and "message" in body["error"]["details"]["fields"]
    status, body, _ = client.post("/api/inquiries", {"message": "A valid message here", "customerEmail": "not-an-email"})
    assert status == 400 and "customerEmail" in body["error"]["details"]["fields"]
    status, body, _ = client.post("/api/inquiries", {"message": "A valid message here", "channel": "fax"})
    assert status == 400 and "channel" in body["error"]["details"]["fields"]
    status, body, _ = client.post("/api/inquiries", {"message": "A valid message here", "isAdmin": True})
    assert status == 400 and body["error"]["details"]["fields"] == ["isAdmin"]
    status, body, _ = client.post("/api/inquiries", {"message": "x" * 5001})
    assert status == 400
    status, body, _ = client.post("/api/inquiries", raw_body="{not json")
    assert status == 400
    status, body, _ = client.post("/api/inquiries", ["not", "an", "object"])
    assert status == 400


def test_create_requires_idempotency_key(client):
    status, body, _ = client.call("POST", "/api/inquiries", {"message": "Quote please for my move"})
    assert status == 400 and body["error"]["code"] == "idempotency_key_required"


def test_control_characters_are_stripped(client):
    payload = client.create("Need a quote\x00 for a studio\x07 apartment move")
    assert "\x00" not in payload["inquiry"]["message"]


def test_missing_fields_are_null_and_listed(client):
    inq = client.create("hey do yall do moves?? thinking about moving soon")["inquiry"]
    ai = inq["aiSuggestion"]
    assert all(ai["extracted"][f] is None for f in ("movingDate", "pickupLocation", "destination", "propertySize"))
    assert set(ai["missingInformation"]) == {"movingDate", "pickupLocation", "destination", "propertySize", "contactMethod"}


def test_submitted_contact_counts_as_contact_method(client):
    inq = client.create("Please send me a quote for my move.", customerEmail="sam@example.com")["inquiry"]
    ai = inq["aiSuggestion"]
    assert ai["extracted"]["contactEmail"] == "sam@example.com"
    assert "contactMethod" not in ai["missingInformation"]


def test_list_filters_and_search(client):
    client.create("Need a quote for a 3 bedroom house from Sherman to Plano on June 2.")
    client.create("Your movers have not arrived today and we have to be out by noon!")
    status, body, _ = client.call("GET", "/api/inquiries", query={"category": "urgent_issue"})
    assert status == 200 and len(body["items"]) == 1 and body["items"][0]["priority"] == "urgent"
    _, body, _ = client.call("GET", "/api/inquiries", query={"q": "plano"})
    assert len(body["items"]) == 1
    _, body, _ = client.call("GET", "/api/inquiries", query={"assignee": "unassigned"})
    assert len(body["items"]) == 2
    assert body["counts"]["urgentOpen"] == 1 and body["counts"]["awaitingReview"] == 2
    status, _, _ = client.call("GET", "/api/inquiries", query={"status": "bogus"})
    assert status == 400


def test_refresh_persistence(app, config):
    from leadrescue.api import App
    from leadrescue.store.local import LocalStore

    c = Client(app)
    inq = c.create()["inquiry"]
    reloaded = Client(App(config, LocalStore(config.local_data_file)))  # simulates a restart / page refresh
    status, body, _ = reloaded.call("GET", f"/api/inquiries/{inq['id']}")
    assert status == 200 and body["inquiry"]["message"] == inq["message"]
    assert len(body["audit"]) >= 2
