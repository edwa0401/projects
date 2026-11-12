"""DynamoDB store. Four on-demand tables (see infra/template.yaml):

- Inquiries   PK id;               GSI byWorkspace (workspace, createdAt)
- AuditEvents PK inquiryId, SK sk  (sk = "<iso timestamp>#<event id>")
- Achievements PK userId, SK awardKey  (insert-once awards prevent duplicate XP)
- Idempotency PK key, TTL expiresAt
"""

from __future__ import annotations

import json
import time
from decimal import Decimal

from ..errors import ConflictError


def _to_dynamo(value):
    return json.loads(json.dumps(value), parse_float=Decimal)


def _from_dynamo(value):
    if isinstance(value, list):
        return [_from_dynamo(v) for v in value]
    if isinstance(value, dict):
        return {k: _from_dynamo(v) for k, v in value.items()}
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


class DynamoStore:
    def __init__(self, config, resource=None):
        import boto3

        self._resource = resource or boto3.resource("dynamodb")
        # The resource's client applies DynamoDB type serialization automatically.
        self._client = self._resource.meta.client
        self.inquiries = self._resource.Table(config.table_inquiries)
        self.audit = self._resource.Table(config.table_audit)
        self.achievements = self._resource.Table(config.table_achievements)
        self.idempotency = self._resource.Table(config.table_idempotency)

    def _ser_item(self, item: dict) -> dict:
        return _to_dynamo(item)

    def _audit_puts(self, events: list[dict]) -> list[dict]:
        return [
            {
                "Put": {
                    "TableName": self.audit.name,
                    "Item": self._ser_item({**e, "sk": f"{e['at']}#{e['id']}"}),
                    "ConditionExpression": "attribute_not_exists(sk)",
                }
            }
            for e in events
        ]

    def _transact(self, items: list[dict]) -> None:
        from botocore.exceptions import ClientError

        try:
            self._client.transact_write_items(TransactItems=items)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("TransactionCanceledException", "ConditionalCheckFailedException"):
                raise ConflictError("transaction") from None
            raise

    def create_inquiry(self, item: dict, audit_events: list[dict]) -> None:
        put = {
            "Put": {
                "TableName": self.inquiries.name,
                "Item": self._ser_item(item),
                "ConditionExpression": "attribute_not_exists(id)",
            }
        }
        self._transact([put] + self._audit_puts(audit_events))

    def get_inquiry(self, inquiry_id: str) -> dict | None:
        resp = self.inquiries.get_item(Key={"id": inquiry_id}, ConsistentRead=True)
        item = resp.get("Item")
        return _from_dynamo(item) if item else None

    def save_inquiry(self, item: dict, expected_version: int, audit_events: list[dict]) -> None:
        put = {
            "Put": {
                "TableName": self.inquiries.name,
                "Item": self._ser_item(item),
                "ConditionExpression": "attribute_exists(id) AND #v = :expected",
                "ExpressionAttributeNames": {"#v": "version"},
                "ExpressionAttributeValues": {":expected": expected_version},
            }
        }
        self._transact([put] + self._audit_puts(audit_events))

    def list_inquiries(self, workspace: str, limit: int) -> list[dict]:
        from boto3.dynamodb.conditions import Key

        items, kwargs = [], {
            "IndexName": "byWorkspace",
            "KeyConditionExpression": Key("workspace").eq(workspace),
            "ScanIndexForward": False,
        }
        while len(items) < limit:
            resp = self.inquiries.query(**kwargs)
            items.extend(resp.get("Items", []))
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        # GSI reads are eventually consistent; re-read is unnecessary for list views.
        return [_from_dynamo(i) for i in items[:limit]]

    def list_audit(self, inquiry_id: str) -> list[dict]:
        from boto3.dynamodb.conditions import Key

        items, kwargs = [], {"KeyConditionExpression": Key("inquiryId").eq(inquiry_id), "ConsistentRead": True}
        while True:
            resp = self.audit.query(**kwargs)
            items.extend(resp.get("Items", []))
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        out = []
        for i in items:
            i = _from_dynamo(i)
            i.pop("sk", None)
            out.append(i)
        return out

    def put_award_if_absent(self, user_id: str, award_key: str, item: dict) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.achievements.put_item(
                Item=_to_dynamo({**item, "userId": user_id, "awardKey": award_key}),
                ConditionExpression="attribute_not_exists(awardKey)",
            )
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return False
            raise

    def list_awards(self, user_id: str) -> list[dict]:
        from boto3.dynamodb.conditions import Key

        items, kwargs = [], {"KeyConditionExpression": Key("userId").eq(user_id), "ConsistentRead": True}
        while True:
            resp = self.achievements.query(**kwargs)
            items.extend(resp.get("Items", []))
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        return [_from_dynamo(i) for i in items]

    def idem_reserve(self, key: str, record: dict) -> dict | None:
        from botocore.exceptions import ClientError

        try:
            self.idempotency.put_item(
                Item=_to_dynamo({**record, "key": key}),
                ConditionExpression="attribute_not_exists(#k) OR expiresAt < :now",
                ExpressionAttributeNames={"#k": "key"},
                ExpressionAttributeValues={":now": int(time.time())},
            )
            return None
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise
        existing = self.idempotency.get_item(Key={"key": key}, ConsistentRead=True).get("Item")
        return _from_dynamo(existing) if existing else {"state": "in_progress"}

    def idem_complete(self, key: str, record: dict) -> None:
        self.idempotency.put_item(Item=_to_dynamo({**record, "key": key}))

    def idem_release(self, key: str) -> None:
        self.idempotency.delete_item(Key={"key": key})
