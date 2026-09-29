"""The change awaiting the employee's confirmation (D6, D7, D23).

A propose tool's result becomes a pending change; a successful commit clears it. The
orchestrator carries it in AG-UI state between turns and hands it to the sub-agent that
made it; each side parses tool results the same way, here. The value always comes back
from a client, so it is only a hint to the model: the tools server still checks the
proposal's owner, conversation, status, and expiry on commit.
"""

from __future__ import annotations

import json
from typing import Any

PENDING_KEY = "pendingAction"
PENDING_FIELDS = ("home_address", "emergency_contact", "direct_deposit")
PENDING_TEXT_LIMIT = 300

PENDING_PARAGRAPH = """
A change is waiting for the employee's confirmation from your previous reply: proposal_id
{proposal_id}, {field} from "{before}" to "{after}". If the employee's message clearly
confirms this change, call commit_change with this proposal_id. If they decline or alter
any detail, do not commit; propose again with the new details when needed.
"""


def clean(value: object) -> str:
    return " ".join(str(value).split())[:PENDING_TEXT_LIMIT]


def parse_pending(pending: object) -> dict[str, str] | None:
    """A well-formed pending change, or None."""
    if not isinstance(pending, dict):
        return None
    proposal_id = str(pending.get("proposalId", ""))
    field = pending.get("field")
    if len(proposal_id) != 32 or not proposal_id.isalnum() or field not in PENDING_FIELDS:
        return None
    return {
        "proposalId": proposal_id,
        "field": field,
        "from": clean(pending.get("from", "")),
        "to": clean(pending.get("to", "")),
    }


def pending_action_from(state: object) -> dict[str, str] | None:
    """The pending change inside an AG-UI state object."""
    return parse_pending(state.get(PENDING_KEY)) if isinstance(state, dict) else None


def pending_paragraph(pending: dict[str, str] | None) -> str:
    if not pending:
        return ""
    return PENDING_PARAGRAPH.format(
        proposal_id=pending["proposalId"],
        field=pending["field"].replace("_", " "),
        before=pending["from"],
        after=pending["to"],
    )


def result_dict(result_data: object) -> dict | None:
    """A tool result as a dict, whether it arrives parsed or as JSON text."""
    if isinstance(result_data, str):
        try:
            result_data = json.loads(result_data)
        except ValueError:
            return None
    return result_data if isinstance(result_data, dict) else None


def pending_from_result(result_data: object) -> dict[str, Any] | None:
    """The pending change a propose tool's result describes, or None."""
    data = result_dict(result_data)
    change = data.get("change") if data else None
    if not data or "proposal_id" not in data or not isinstance(change, dict):
        return None
    return {
        "proposalId": data["proposal_id"],
        "field": change.get("field"),
        "from": change.get("from", ""),
        "to": change.get("to", ""),
        "expiresAt": data.get("expires_at", ""),
    }


def committed(result_data: object) -> bool:
    data = result_dict(result_data)
    return bool(data) and data.get("committed") is True


def _tool_result_payload(result: dict) -> object:
    """A Strands toolResult's content: a json block when present, else the first text."""
    for block in result.get("content", []):
        if "json" in block:
            return block["json"]
    for block in result.get("content", []):
        if "text" in block:
            return block["text"]
    return None


def pending_after_messages(messages: list[dict], prefix: str) -> dict[str, Any] | None:
    """The pending change after one agent run, from the Strands messages that run added:
    the last successful proposal unless a commit followed it. A run that did neither
    leaves nothing pending (one turn lifetime)."""
    names: dict[str, str] = {}
    pending: dict[str, Any] | None = None
    for message in messages:
        for block in message.get("content", []):
            if "toolUse" in block:
                names[block["toolUse"]["toolUseId"]] = block["toolUse"]["name"]
            elif "toolResult" in block:
                result = block["toolResult"]
                if result.get("status") == "error":
                    continue
                name = names.get(result.get("toolUseId", ""), "")
                payload = _tool_result_payload(result)
                if name.startswith(f"{prefix}propose_"):
                    pending = pending_from_result(payload) or pending
                elif name == f"{prefix}commit_change" and committed(payload):
                    pending = None
    return pending


def committed_in_messages(messages: list[dict], prefix: str) -> bool:
    """Whether a run's messages include a successful commit_change."""
    names: dict[str, str] = {}
    for message in messages:
        for block in message.get("content", []):
            if "toolUse" in block:
                names[block["toolUse"]["toolUseId"]] = block["toolUse"]["name"]
            elif "toolResult" in block:
                result = block["toolResult"]
                name = names.get(result.get("toolUseId", ""), "")
                if (
                    name == f"{prefix}commit_change"
                    and result.get("status") != "error"
                    and committed(_tool_result_payload(result))
                ):
                    return True
    return False
