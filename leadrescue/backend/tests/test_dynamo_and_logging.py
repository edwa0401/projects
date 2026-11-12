"""DynamoDB store integration (moto) and log hygiene."""

import io
import logging

import boto3
import pytest
from moto import mock_aws

from conftest import FULL_CHECKS, Client
from leadrescue.api import App
from leadrescue.config import Config
from leadrescue.errors import ConflictError
from leadrescue.logging_util import logger


def _tables(ddb):
    ddb.create_table(TableName="inq", BillingMode="PAY_PER_REQUEST",
                     AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}, {"AttributeName": "workspace", "AttributeType": "S"},
                                           {"AttributeName": "createdAt", "AttributeType": "S"}],
                     KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                     GlobalSecondaryIndexes=[{"IndexName": "byWorkspace", "KeySchema": [{"AttributeName": "workspace", "KeyType": "HASH"},
                                                                                       {"AttributeName": "createdAt", "KeyType": "RANGE"}],
                                              "Projection": {"ProjectionType": "ALL"}}])
    ddb.create_table(TableName="audit", BillingMode="PAY_PER_REQUEST",
                     AttributeDefinitions=[{"AttributeName": "inquiryId", "AttributeType": "S"}, {"AttributeName": "sk", "AttributeType": "S"}],
                     KeySchema=[{"AttributeName": "inquiryId", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}])
    ddb.create_table(TableName="ach", BillingMode="PAY_PER_REQUEST",
                     AttributeDefinitions=[{"AttributeName": "userId", "AttributeType": "S"}, {"AttributeName": "awardKey", "AttributeType": "S"}],
                     KeySchema=[{"AttributeName": "userId", "KeyType": "HASH"}, {"AttributeName": "awardKey", "KeyType": "RANGE"}])
    ddb.create_table(TableName="idem", BillingMode="PAY_PER_REQUEST",
                     AttributeDefinitions=[{"AttributeName": "key", "AttributeType": "S"}],
                     KeySchema=[{"AttributeName": "key", "KeyType": "HASH"}])


@pytest.fixture
def dynamo_client(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        _tables(ddb)
        from leadrescue.store.dynamo import DynamoStore

        cfg = Config(ai_provider="demo", store="dynamodb", table_inquiries="inq", table_audit="audit",
                     table_achievements="ach", table_idempotency="idem")
        store = DynamoStore(cfg, resource=ddb)
        yield Client(App(cfg, store)), store


def test_dynamo_full_workflow(dynamo_client):
    client, store = dynamo_client
    inq = client.create()["inquiry"]
    assert inq["aiSuggestion"]["meta"]["latencyMs"] >= 0
    _, body, _ = client.post(f"/api/inquiries/{inq['id']}/approve", {"expectedVersion": inq["version"], "verification": FULL_CHECKS})
    assert body["inquiry"]["status"] == "approved"
    assert [e["type"] for e in body["audit"]][:2] == ["created", "analysis_succeeded"]
    _, listing, _ = client.call("GET", "/api/inquiries")
    assert listing["items"][0]["id"] == inq["id"]
    # optimistic locking
    with pytest.raises(ConflictError):
        store.save_inquiry({**body["inquiry"], "version": 99}, 1, [])


def test_dynamo_idempotency_and_awards(dynamo_client):
    client, store = dynamo_client
    req = {"message": "Need a quote for a studio from Sherman to Denison"}
    a = client.post("/api/inquiries", req, key="dyn-key-001")
    b = client.post("/api/inquiries", req, key="dyn-key-001")
    assert a[1]["inquiry"]["id"] == b[1]["inquiry"]["id"]
    assert store.put_award_if_absent("u1", "XP#rush-1#category", {"awardKey": "XP#rush-1#category", "xp": 15}) is True
    assert store.put_award_if_absent("u1", "XP#rush-1#category", {"awardKey": "XP#rush-1#category", "xp": 15}) is False
    assert len(store.list_awards("u1")) == 1
    client.post("/api/practice/start")
    _, prog, _ = client.call("GET", "/api/progress")
    assert len([c for c in prog["cases"] if c["inquiryId"]]) == 5


def test_logs_never_contain_message_bodies_or_tokens(client):
    stream = io.StringIO()
    h = logging.StreamHandler(stream)
    logger.addHandler(h)
    try:
        secret_text = "Zanzibar-unique-phrase 742 Evergreen Terrace"
        status, body, _ = client.post("/api/inquiries", {"message": f"Need a quote, {secret_text}", "customerEmail": "private.person@example.com"})
        assert status == 201
        iid = body["inquiry"]["id"]
        client.call("PATCH", f"/api/inquiries/{iid}", {"expectedVersion": body["inquiry"]["version"], "draftReply": "Private draft content xyz"})
        client.call("GET", "/api/inquiries", claims={"sub": "x", "cognito:groups": "staff", "token": "eyJsecret"})
    finally:
        logger.removeHandler(h)
    logs = stream.getvalue()
    assert iid in logs
    for forbidden in ("Zanzibar", "Evergreen", "private.person", "Private draft", "eyJsecret"):
        assert forbidden not in logs
