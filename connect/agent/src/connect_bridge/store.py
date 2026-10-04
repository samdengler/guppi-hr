"""Where a thread's Connect contact lives between runs.

The runtime keeps nothing in memory between requests (a new microVM can take any run), so
each AG-UI thread's chat contact is a DynamoDB item keyed by the caller's hashed subject and
the thread id: the contact id, the participant token (for a WebSocket per run), the
participant connection token and its expiry, the expiry
of the employee token the contact was started with, the transcript items already relayed,
and whether the conversation has ended. Items expire a day after their last use.

While a run starts a contact, the item is a claim instead (`startingUntil`), written only
when no other run holds a live one, so a warm start and a first message that arrive
together open one contact between them (guppi-hr D39).
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any

from botocore.exceptions import ClientError

SEEN_LIMIT = 200
ITEM_TTL_SECONDS = 24 * 3600


@dataclass
class Session:
    key: str
    contact_id: str
    connection_token: str
    connection_expires_at: float
    token_expires_at: float
    seen: list[str] = field(default_factory=list)
    token_cleared: bool = False
    closed: bool = False
    # Empty for a contact stored before change 5; that contact's runs poll the transcript.
    participant_token: str = ""
    # Epoch seconds; 0 for a contact stored before Connect chats got a 60-minute duration.
    started_at: float = 0.0
    # The Okta token's expiry when the contact started (guppi-hr D47); token_expires_at is the
    # hop tokens'. 0 for a contact stored before; token_expires_at stands in for it.
    sign_in_expires_at: float = 0.0

    def remember(self, ids: list[str]) -> None:
        for item_id in ids:
            if item_id not in self.seen:
                self.seen.append(item_id)
        del self.seen[:-SEEN_LIMIT]


@dataclass
class Pending:
    """Another run is starting this thread's contact until `until` (epoch seconds)."""

    until: float


class DynamoSessionStore:
    def __init__(self, table: Any) -> None:
        self.table = table

    def get(self, key: str) -> Session | Pending | None:
        item = self.table.get_item(Key={"pk": key}, ConsistentRead=True).get("Item")
        if not item:
            return None
        if "contactId" not in item:
            return Pending(float(item.get("startingUntil", 0)))
        return Session(
            key=key,
            contact_id=item["contactId"],
            connection_token=item["connectionToken"],
            connection_expires_at=float(item["connectionExpiresAt"]),
            token_expires_at=float(item["tokenExpiresAt"]),
            seen=list(item.get("seen", [])),
            token_cleared=bool(item.get("tokenCleared", False)),
            closed=bool(item.get("closed", False)),
            participant_token=str(item.get("participantToken", "")),
            started_at=float(item.get("startedAt", 0)),
            sign_in_expires_at=float(item.get("signInExpiresAt", 0)),
        )

    def put(self, session: Session) -> None:
        self.table.put_item(
            Item={
                "pk": session.key,
                "contactId": session.contact_id,
                "connectionToken": session.connection_token,
                "connectionExpiresAt": int(session.connection_expires_at),
                "tokenExpiresAt": int(session.token_expires_at),
                "seen": session.seen,
                "tokenCleared": session.token_cleared,
                "closed": session.closed,
                "participantToken": session.participant_token,
                "startedAt": int(session.started_at),
                "signInExpiresAt": int(session.sign_in_expires_at),
                "ttl": int(time.time()) + ITEM_TTL_SECONDS,
            }
        )


    def claim(self, key: str, until: float, now: float) -> bool:
        """Marks the thread as starting a contact, unless another run's claim is live."""
        try:
            self.table.put_item(
                Item={"pk": key, "startingUntil": int(until) + 1, "ttl": int(now) + ITEM_TTL_SECONDS},
                ConditionExpression="attribute_not_exists(startingUntil) OR startingUntil < :now",
                ExpressionAttributeValues={":now": int(now)},
            )
            return True
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return False
            raise

    def release(self, key: str) -> None:
        """Drops this thread's claim after a failed start; a stored contact stays."""
        try:
            self.table.delete_item(Key={"pk": key}, ConditionExpression="attribute_exists(startingUntil)")
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise


class MemorySessionStore:
    """For tests and local runs. Copies on every read and write, as DynamoDB does, so a
    change a run forgets to save is lost here too (critique finding 13)."""

    def __init__(self) -> None:
        self.items: dict[str, Session | Pending] = {}

    def get(self, key: str) -> Session | Pending | None:
        return copy.deepcopy(self.items.get(key))

    def put(self, session: Session) -> None:
        self.items[session.key] = copy.deepcopy(session)

    def claim(self, key: str, until: float, now: float) -> bool:
        current = self.items.get(key)
        if isinstance(current, Pending) and current.until >= now:
            return False
        self.items[key] = Pending(until)
        return True

    def release(self, key: str) -> None:
        if isinstance(self.items.get(key), Pending):
            del self.items[key]
