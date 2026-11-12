"""Monday Morning Rush: XP for criteria, duplicate prevention, achievements, data separation."""

from conftest import FULL_CHECKS


def _practice(client):
    status, prog, _ = client.post("/api/practice/start")
    assert status == 200
    _, body, _ = client.call("GET", "/api/inquiries", query={"workspace": "practice"})
    return {i["practiceCaseId"]: i for i in body["items"]}, prog


def _review(client, item_summary, changes, approve=True, draft=None, note=None, checks=FULL_CHECKS):
    iid = item_summary["id"]
    _, d, _ = client.call("GET", f"/api/inquiries/{iid}")
    v = d["inquiry"]["version"]
    if changes:
        status, d, _ = client.call("PATCH", f"/api/inquiries/{iid}", {"expectedVersion": v, **changes})
        assert status == 200, d
        v = d["inquiry"]["version"]
    if approve:
        body = {"expectedVersion": v, "verification": checks}
        if draft:
            body["draftReply"] = draft
        status, d, _ = client.post(f"/api/inquiries/{iid}/approve", body)
        assert status == 200, d
        return d
    status, d, _ = client.post(f"/api/inquiries/{iid}/resolve", {"expectedVersion": v, "resolutionNote": note})
    assert status == 200, d
    return d


def test_start_is_idempotent_and_separate_from_business(client):
    cases, prog = _practice(client)
    assert set(cases) == {"rush-1", "rush-2", "rush-3", "rush-4", "rush-5"}
    assert prog["xp"] == 0 and "do not establish production accuracy" in prog["disclaimer"]
    client.post("/api/practice/start")
    _, body, _ = client.call("GET", "/api/inquiries", query={"workspace": "practice"})
    assert len(body["items"]) == 5
    _, business, _ = client.call("GET", "/api/inquiries")
    assert business["items"] == []
    _, metrics, _ = client.call("GET", "/api/metrics")
    assert metrics["recordCount"] == 0


def test_clicking_approve_without_meeting_criteria_earns_less(client):
    cases, _ = _practice(client)
    # wrong priority and no assignee on the urgent case
    d = _review(client, cases["rush-2"], {"priority": "low"})
    earned = {a["criterionId"] for a in d["awards"] if a["kind"] == "criterion"}
    assert "priority" not in earned and "assigned" not in earned
    _, prog, _ = client.call("GET", "/api/progress")
    assert not next(a for a in prog["achievements"] if a["id"] == "priority-protector")["unlocked"]


def test_full_rush_awards_xp_once_and_unlocks_achievements(client):
    cases, _ = _practice(client)
    d1 = _review(client, cases["rush-1"], {"assignee": "alex"})
    labels = {a["label"] for a in d1["awards"]}
    assert "Inbox Investigator" in labels
    _review(client, cases["rush-2"], {"assignee": "sam"})
    _review(client, cases["rush-3"], {"assignee": "jordan"})
    _review(client, cases["rush-4"], {"assignee": "maya"}, draft=(
        "Hi! Thanks for reaching out. Could you tell us your moving date, the pickup address you are moving from, "
        "where you are moving to, and how many bedrooms? A team member will follow up."))
    _review(client, cases["rush-5"], {"assignee": "maya"}, approve=False, note="Manipulative message; no reply sent. Flagged for manager.")
    _, prog, _ = client.call("GET", "/api/progress")
    assert prog["casesCompleted"] == 5
    assert all(a["unlocked"] for a in prog["achievements"])
    assert prog["xp"] == prog["maxXp"]
    xp_before = prog["xp"]

    # Reset the challenge and redo case 1: no duplicate XP
    status, _, _ = client.post("/api/practice/reset")
    assert status == 200
    _, body, _ = client.call("GET", "/api/inquiries", query={"workspace": "practice"})
    fresh = {i["practiceCaseId"]: i for i in body["items"]}
    assert fresh["rush-1"]["id"] != cases["rush-1"]["id"] and fresh["rush-1"]["status"] == "awaiting_review"
    d = _review(client, fresh["rush-1"], {"assignee": "alex"})
    assert d["awards"] == []
    _, prog2, _ = client.call("GET", "/api/progress")
    assert prog2["xp"] == xp_before


def test_injection_case_cannot_be_approved_with_free_move(client):
    cases, _ = _practice(client)
    iid = cases["rush-5"]["id"]
    _, d, _ = client.call("GET", f"/api/inquiries/{iid}")
    assert d["inquiry"]["aiSuggestion"]["suspiciousInstructions"] is True
    assert d["inquiry"]["category"] == "manual_review"
    status, body, _ = client.post(f"/api/inquiries/{iid}/approve", {"expectedVersion": d["inquiry"]["version"], "verification": FULL_CHECKS,
                                                                    "draftReply": "Approved! Your move is free of charge."})
    assert status == 422
