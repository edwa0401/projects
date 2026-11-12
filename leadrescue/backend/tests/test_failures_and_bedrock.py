"""Failed model calls preserve requests; Bedrock provider parsing and error mapping; no silent fallback."""

import copy

from botocore.exceptions import ClientError

from conftest import Client
from leadrescue.analysis.bedrock_provider import BedrockProvider
from leadrescue.analysis.contract import TOOL_NAME
from leadrescue.analysis.demo_provider import DemoProvider
from leadrescue.api import App
from leadrescue.config import Config
from leadrescue.errors import AnalysisError

from test_analysis_guardrails import VALID


class FailingProvider:
    name = "bedrock"

    def analyze(self, *a):
        raise AnalysisError("model_throttled", "The AI service is busy. Retry in a minute or handle manually.", True)


def test_failed_analysis_preserves_request_and_allows_retry(config, store):
    state = {"fail": True}

    def factory():
        return FailingProvider() if state["fail"] else DemoProvider()

    c = Client(App(config, store, provider_factory=factory))
    status, body, _ = c.post("/api/inquiries", {"message": "Need a quote from Sherman to Denison next Saturday"})
    assert status == 201
    inq = body["inquiry"]
    assert inq["status"] == "analysis_failed"
    assert inq["aiSuggestion"] is None
    assert body["analysisError"]["code"] == "model_throttled"
    assert inq["message"].startswith("Need a quote")
    assert [e["type"] for e in body["audit"]][-2:] == ["analysis_failed", "status_changed"]

    # Manual handling is possible without AI
    status, body2, _ = c.call("PATCH", f"/api/inquiries/{inq['id']}", {"expectedVersion": inq["version"], "category": "quote", "priority": "normal",
                                                                      "draftReply": "Thanks for reaching out. A team member will follow up with next steps."})
    assert status == 200 and body2["inquiry"]["status"] == "in_review"

    # Retry succeeds and does not overwrite staff-edited fields
    state["fail"] = False
    status, body3, _ = c.post(f"/api/inquiries/{inq['id']}/analyze", {"expectedVersion": body2["inquiry"]["version"]})
    assert status == 200, body3
    after = body3["inquiry"]
    assert after["analysisStatus"] == "succeeded" and after["aiSuggestion"]["category"] == "quote"
    assert after["draftReply"].startswith("Thanks for reaching out.")
    assert after["status"] == "in_review"


def test_live_mode_never_falls_back_to_demo(tmp_path):
    cfg = Config(ai_provider="bedrock", store="local", local_data_file=str(tmp_path / "db.json"), bedrock_model_id=None)
    from leadrescue.store.local import LocalStore

    c = Client(App(cfg, LocalStore(cfg.local_data_file)))
    status, body, _ = c.post("/api/inquiries", {"message": "Need a quote from Sherman to Denison"})
    assert status == 201
    assert body["inquiry"]["aiSuggestion"] is None
    assert body["analysisError"]["code"] == "not_configured"


class StubBedrock:
    def __init__(self, response=None, exc=None):
        self.response, self.exc, self.calls = response, exc, []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc:
            raise self.exc
        return self.response


def _cfg(**kw):
    return Config(ai_provider="bedrock", bedrock_model_id="us.example.model-v1:0", **kw)


def test_bedrock_parses_tool_use_and_usage():
    stub = StubBedrock({
        "output": {"message": {"role": "assistant", "content": [{"text": "ok"}, {"toolUse": {"toolUseId": "t1", "name": TOOL_NAME, "input": copy.deepcopy(VALID)}}]}},
        "usage": {"inputTokens": 900, "outputTokens": 210},
        "stopReason": "tool_use",
    })
    result = BedrockProvider(_cfg(), client=stub).analyze("Moving from Sherman to Denison next Saturday", "web_form", {})
    assert result.raw["category"] == "quote" and result.input_tokens == 900 and result.output_tokens == 210
    req = stub.calls[0]
    assert req["modelId"] == "us.example.model-v1:0"
    assert req["toolConfig"]["toolChoice"] == {"auto": {}}
    assert "<customer_message>" in req["messages"][0]["content"][0]["text"]
    assert "untrusted" in req["system"][0]["text"]
    assert len(req["toolConfig"]["tools"]) == 1


def test_bedrock_forced_tool_choice_option():
    stub = StubBedrock({"output": {"message": {"content": [{"toolUse": {"name": TOOL_NAME, "input": VALID}}]}}, "usage": {}})
    BedrockProvider(_cfg(bedrock_tool_choice="tool"), client=stub).analyze("x" * 20, "web_form", {})
    assert stub.calls[0]["toolConfig"]["toolChoice"] == {"tool": {"name": TOOL_NAME}}


def test_bedrock_text_only_response_is_a_failure():
    stub = StubBedrock({"output": {"message": {"content": [{"text": "{\"category\": \"quote\"}"}]}}, "stopReason": "end_turn"})
    try:
        BedrockProvider(_cfg(), client=stub).analyze("hello there", "web_form", {})
        raise AssertionError("expected failure")
    except AnalysisError as exc:
        assert exc.code == "invalid_model_output"


def test_bedrock_error_mapping_hides_raw_messages():
    err = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "secret internal detail arn:aws:..."}}, "Converse")
    try:
        BedrockProvider(_cfg(), client=StubBedrock(exc=err)).analyze("hello there", "web_form", {})
        raise AssertionError("expected failure")
    except AnalysisError as exc:
        assert exc.code == "model_access_denied" and exc.retryable is False
        assert "arn:aws" not in exc.message
    try:
        BedrockProvider(_cfg(), client=StubBedrock(exc=RuntimeError("boom"))).analyze("hello there", "web_form", {})
    except AnalysisError as exc:
        assert exc.code == "model_error"
