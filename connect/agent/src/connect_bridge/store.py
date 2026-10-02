"""Where a thread's Connect contact lives between runs.

The runtime keeps nothing in memory between requests (a new microVM can take any run), so
each AG-UI thread's chat contact is a DynamoDB item keyed by the caller's hashed subject and
the thread id: the contact id, the participant connection token and its expiry, the expiry
of the employee token the contact was started with, the transcript items already relayed,
and whether the conversation has ended. Items expire a day after their last use.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

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

    def remember(self, ids: list[str]) -> None:
        for item_id in ids:
            if item_id not in self.seen:
                self.seen.append(item_id)
        del self.seen[:-SEEN_LIMIT]


class DynamoSessionStore:
    def __init__(self, table: Any) -> None:
        self.table = table

    def get(self, key: str) -> Session | None:
        item = self.table.get_item(Key={"pk": key}).get("Item")
        if not item:
            return None
        return Session(
            key=key,
            contact_id=item["contactId"],
            connection_token=item["connectionToken"],
            connection_expires_at=float(item["connectionExpiresAt"]),
            token_expires_at=float(item["tokenExpiresAt"]),
            seen=list(item.get("seen", [])),
            token_cleared=bool(item.get("tokenCleared", False)),
            closed=bool(item.get("closed", False)),
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
                "ttl": int(time.time()) + ITEM_TTL_SECONDS,
            }
        )


class MemorySessionStore:
    """For tests and local runs."""

    def __init__(self) -> None:
        self.items: dict[str, Session] = {}

    def get(self, key: str) -> Session | None:
        return self.items.get(key)

    def put(self, session: Session) -> None:
        self.items[session.key] = session
