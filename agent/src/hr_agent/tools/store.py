"""DynamoDB behind the HR tools (D21): employees, proposals, tickets, audit.

A write is two tool calls. `propose` stores the exact change and returns its id; `commit`
applies it in one transaction that flips the proposal from pending to committed (only
for the same user, and only once), writes the employee record, and adds the audit entry
carrying the trace id. Proposals expire after PROPOSAL_TTL_SECONDS; a DynamoDB TTL on
`expires_at` removes them later, and commit checks the time itself because TTL deletes
lag.
"""

from __future__ import annotations

import os
import secrets
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

from hr_agent.tools.identity import Caller
from hr_agent.tools.records import seed_employee

PROPOSAL_TTL_SECONDS = 15 * 60
CHANGEABLE_FIELDS = ("home_address", "emergency_contact", "direct_deposit")


class CommitRefused(Exception):
    """A commit that must not happen; nothing was written."""


@dataclass(frozen=True)
class Tables:
    employees: str
    proposals: str
    tickets: str
    audit: str

    @classmethod
    def from_environment(cls) -> Tables:
        return cls(
            employees=os.environ["EMPLOYEES_TABLE"],
            proposals=os.environ["PROPOSALS_TABLE"],
            tickets=os.environ["TICKETS_TABLE"],
            audit=os.environ["AUDIT_TABLE"],
        )


def plain(value: Any) -> Any:
    """DynamoDB numbers come back as Decimal; the tools return JSON."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [plain(v) for v in value]
    return value


class HrStore:
    def __init__(
        self,
        tables: Tables,
        region: str | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        region = region or os.environ.get("AWS_REGION", "us-east-1")
        self._resource = boto3.resource("dynamodb", region_name=region)
        self._client = boto3.client("dynamodb", region_name=region)
        self._tables = tables
        self._clock = clock
        self._serialize = TypeSerializer().serialize

    def _table(self, name: str):
        return self._resource.Table(name)

    def employee(self, sub: str) -> dict[str, Any]:
        """The caller's record, seeded on first read."""
        table = self._table(self._tables.employees)
        item = table.get_item(Key={"sub": sub}, ConsistentRead=True).get("Item")
        if item is not None:
            return plain(item)
        seeded = seed_employee(sub)
        try:
            table.put_item(Item=seeded, ConditionExpression="attribute_not_exists(#s)",
                           ExpressionAttributeNames={"#s": "sub"})
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
            return plain(table.get_item(Key={"sub": sub}, ConsistentRead=True)["Item"])
        return seeded

    def propose(
        self, caller: Caller, field: str, before: dict[str, Any], after: dict[str, Any]
    ) -> dict[str, Any]:
        if field not in CHANGEABLE_FIELDS:
            raise ValueError(f"{field} cannot be changed")
        now = int(self._clock())
        proposal = {
            "proposal_id": uuid.uuid4().hex,
            "sub": caller.sub,
            "thread_id": caller.thread_id or "",
            "field": field,
            "before": before,
            "after": after,
            "status": "pending",
            "created_at": now,
            "expires_at": now + PROPOSAL_TTL_SECONDS,
        }
        self._table(self._tables.proposals).put_item(Item=proposal)
        return proposal

    def commit(self, caller: Caller, proposal_id: str) -> dict[str, Any]:
        proposal_id = proposal_id.strip()
        if not proposal_id:
            raise CommitRefused("a commit needs the proposal id that the propose step returned")
        item = self._table(self._tables.proposals).get_item(
            Key={"proposal_id": proposal_id}, ConsistentRead=True
        ).get("Item")
        # A proposal that belongs to someone else reads as not found, so ids cannot be probed.
        if item is None or item["sub"] != caller.sub:
            raise CommitRefused(f"there is no proposal {proposal_id} for this employee")
        proposal = plain(item)
        if proposal["status"] != "pending":
            raise CommitRefused(f"proposal {proposal_id} was already {proposal['status']}")
        now = int(self._clock())
        if now >= proposal["expires_at"]:
            raise CommitRefused(f"proposal {proposal_id} expired; propose the change again")
        if proposal["thread_id"] != (caller.thread_id or ""):
            raise CommitRefused(f"proposal {proposal_id} was made in a different conversation")

        audit_id = f"{now:012d}#{proposal_id}"
        audit = {
            "sub": caller.sub,
            "audit_id": audit_id,
            "proposal_id": proposal_id,
            "field": proposal["field"],
            "before": proposal["before"],
            "after": proposal["after"],
            "committed_at": now,
            "thread_id": caller.thread_id or "",
            "trace_id": caller.trace_id or "",
        }
        s = self._serialize
        try:
            self._client.transact_write_items(
                TransactItems=[
                    {
                        "Update": {
                            "TableName": self._tables.proposals,
                            "Key": {"proposal_id": s(proposal_id)},
                            "UpdateExpression": "SET #st = :committed, committed_at = :now",
                            "ConditionExpression": "#st = :pending AND #s = :sub",
                            "ExpressionAttributeNames": {"#st": "status", "#s": "sub"},
                            "ExpressionAttributeValues": {
                                ":committed": s("committed"),
                                ":pending": s("pending"),
                                ":sub": s(caller.sub),
                                ":now": s(now),
                            },
                        }
                    },
                    {
                        "Update": {
                            "TableName": self._tables.employees,
                            "Key": {"sub": s(caller.sub)},
                            "UpdateExpression": "SET #f = :after",
                            "ConditionExpression": "attribute_exists(#s)",
                            "ExpressionAttributeNames": {"#f": proposal["field"], "#s": "sub"},
                            "ExpressionAttributeValues": {":after": s(proposal["after"])},
                        }
                    },
                    {
                        "Put": {
                            "TableName": self._tables.audit,
                            "Item": {k: s(v) for k, v in audit.items()},
                        }
                    },
                ]
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "TransactionCanceledException":
                raise
            raise CommitRefused(
                f"proposal {proposal_id} could not be committed; it may have been committed "
                "already"
            ) from exc
        return audit

    def open_ticket(self, caller: Caller, summary: str, domain: str) -> dict[str, Any]:
        summary = summary.strip()
        if not summary or len(summary) > 500:
            raise ValueError("the ticket summary must be 1 to 500 characters")
        ticket = {
            "ticket_id": f"HR-{secrets.randbelow(1_000_000):06d}",
            "sub": caller.sub,
            "domain": domain.strip().lower() or "general",
            "summary": summary,
            "status": "open",
            "created_at": int(self._clock()),
            "thread_id": caller.thread_id or "",
            "trace_id": caller.trace_id or "",
        }
        self._table(self._tables.tickets).put_item(
            Item=ticket,
            ConditionExpression="attribute_not_exists(ticket_id)",
        )
        return ticket
