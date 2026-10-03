"""What is on file for the employee, read through the tools gateway before the model runs.

A sub-agent answering "what is my home address?" used to take two model calls with a tool
call between them: the model asked for hr___get_profile, the call went through the tools
gateway (about 1.1 s, A6), and a second model call wrote the answer. Reading the record
first and sending it with the message (never in the system prompt, which traces keep
unredacted) lets the model answer in one call (docs/
latency-log.md, L15). The reads go through the same MCP session and gateway as any tool
call, so D40 holds.

A snapshot is kept per (token, thread, domain) for five minutes and dropped when the run
commits a change, so a later question sees the new value. The warm start fills it, so a
new conversation's first read pays no tool call at all.

Travel has no record; its snapshot is policy passages. The warm start runs one broad
search over the pass travel policy and caches it like a record, so a travel question needs
no search before the model (L22); without a cached search, the question itself is searched
first (L16). Either way the model may search again when the passages do not settle it.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

SNAPSHOT_SECONDS = 300
# The reads each domain's answers usually start from, without the hr___ prefix.
RECORD_READS: dict[str, tuple[tuple[str, dict[str, Any]], ...]] = {
    "profile": (("get_profile", {}),),
    "pay": (("get_direct_deposit", {}), ("list_pay_statements", {"count": 3})),
}
RETRIEVE_TOOL = "docs___Retrieve"
# The broad search a warm start caches for a domain whose answers come from policy.
WARM_SEARCHES: dict[str, str] = {
    "travel": (
        "pass travel privileges: who is eligible, enrolled pass riders, buddy passes, "
        "service charges, boarding priority, embargo dates, conduct"
    ),
}

Key = tuple[str, str, str]


class Snapshots:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._items: dict[Key, tuple[float, str]] = {}

    def get(self, key: Key) -> str | None:
        item = self._items.get(key)
        if item is None or self._clock() - item[0] > SNAPSHOT_SECONDS:
            self._items.pop(key, None)
            return None
        return item[1]

    def put(self, key: Key, text: str) -> None:
        self._items[key] = (self._clock(), text)
        # Keep the cache small: drop anything stale on each write.
        now = self._clock()
        for stale in [k for k, (taken, _) in self._items.items() if now - taken > SNAPSHOT_SECONDS]:
            del self._items[stale]

    def drop(self, key: Key) -> None:
        self._items.pop(key, None)


def tool_text(result: Any) -> str | None:
    """The text of a successful MCP tool result, or None."""
    if not isinstance(result, dict) or result.get("status") != "success":
        return None
    return "".join(part.get("text", "") for part in result.get("content", []) if isinstance(part, dict)).strip()


def read_record(client: Any, domain: str, prefix: str) -> str | None:
    """The domain's record reads as one block of text, or None when there are none or one
    failed (the model then calls the tools itself, as before)."""
    reads = RECORD_READS.get(domain, ())
    if not reads:
        return None
    parts = []
    for name, arguments in reads:
        text = tool_text(client.call_tool_sync(uuid.uuid4().hex, f"{prefix}{name}", arguments))
        if text is None:
            log.warning("snapshot read %s failed; the model reads it itself", name)
            return None
        parts.append(f"{name}: {text}")
    return "\n".join(parts)


def search_policy(client: Any, question: str) -> str | None:
    """The policy passages for the question, or None when the search failed."""
    if not question.strip():
        return None
    result = client.call_tool_sync(
        uuid.uuid4().hex, RETRIEVE_TOOL, {"retrievalQuery": {"text": question}}
    )
    return tool_text(result)


RECORD_PARAGRAPH = """
The employee's current record, read through your HR tools for this conversation:
<record>
{record}
</record>
Answer questions about these details from the record instead of calling the read tools
again. After a change is committed, the record is out of date: call the read tool for the
new value.
"""

SEARCH_PARAGRAPH = """
Policy passages for the employee's question, from a search run before you started:
<passages>
{passages}
</passages>
Answer from these passages when they settle the question; search again only when they do
not.
"""


def prompt_paragraph(record: str | None, passages: str | None) -> str:
    text = ""
    if record:
        text += RECORD_PARAGRAPH.format(record=record)
    if passages:
        text += SEARCH_PARAGRAPH.format(passages=passages)
    return text
